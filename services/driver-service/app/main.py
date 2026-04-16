import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response, status
from uvicorn.logging import DefaultFormatter

from .config import config, state
from .kafka_consumer import kafka_consumer
from .kafka_producer import kafka_producer

# ---- Logging (identical setup to other services) ----
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(
    DefaultFormatter("%(levelprefix)s %(name)s | %(message)s")
)
logging.root.handlers = [console_handler]
logging.root.setLevel(logging.INFO)

logger = logging.getLogger(__name__)


# ---- Lifespan ----

@asynccontextmanager
async def lifespan(_: FastAPI):
    kafka_producer.start()
    kafka_consumer.start()
    yield
    kafka_consumer.stop()
    kafka_producer.stop()


# ---- App ----

app = FastAPI(title="Driver Service", lifespan=lifespan)


# ---- Routes ----

@app.get("/ping")
def ping():
    return {"status": "ok"}


@app.get("/health")
def health_check(response: Response):
    """
    Reports health of Kafka producer connectivity.
    The consumer is a daemon thread — its liveness is implicitly covered by the process.
    """
    kafka_up = kafka_producer.is_connected()
    if not kafka_up:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if kafka_up else "degraded",
        "service": "driver-service",
        "dependencies": {"kafka": "up" if kafka_up else "down"},
    }


@app.get("/drivers")
def list_drivers():
    """Return the current status of all drivers (for observability/debugging)."""
    return {"drivers": state.get_all_drivers()}


@app.get("/drivers/{driver_id}")
def get_driver(driver_id: str):
    driver = state.get_driver(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail=f"Driver '{driver_id}' not found.")
    return driver


@app.get("/rides/pending")
def list_pending_rides():
    """Return all pending ride requests awaiting driver acceptance."""
    return {"pending_rides": state.get_all_pending_requests()}


@app.post("/rides/{ride_id}/accept", status_code=status.HTTP_200_OK)
def accept_ride(ride_id: str, driver_id: str):
    """
    A driver accepts a pending ride request.

    Steps:
      1. Validate the ride exists in pending requests.
      2. Atomically assign the driver (guard against race conditions).
      3. Publish a 'ride accepted' event to the Ride topic.
      4. Remove from pending requests.

    Query param `driver_id` identifies which driver is accepting.
    In a real system this would come from an authenticated JWT claim.
    """
    # 1. Validate ride exists
    ride_data = state.get_pending_request(ride_id)
    if not ride_data:
        raise HTTPException(
            status_code=404,
            detail=f"Ride '{ride_id}' not found or already accepted.",
        )

    # 2. Validate driver exists and assign atomically
    driver = state.get_driver(driver_id)
    if not driver:
        raise HTTPException(
            status_code=404, detail=f"Driver '{driver_id}' not found."
        )

    assigned = state.assign_driver(driver_id, ride_id)
    if not assigned:
        raise HTTPException(
            status_code=409,
            detail=f"Driver '{driver_id}' is currently unavailable (already on a ride).",
        )

    # 3. Publish ride accepted event
    event_payload = {
        "ride_id": ride_id,
        "driver_id": driver_id,
        "driver_name": driver["name"],
        "start": ride_data.get("start"),
        "destination": ride_data.get("destination"),
    }

    try:
        kafka_producer.produce(
            topic=config.KAFKA_TOPIC_RIDE_ACCEPTED,
            key=ride_id,
            payload=event_payload,
        )
        logger.info(
            f"Driver '{driver_id}' accepted ride '{ride_id}'. "
            f"Event published to '{config.KAFKA_TOPIC_RIDE_ACCEPTED}'."
        )
    except Exception as e:
        # Rollback driver assignment on Kafka failure
        state.release_driver_by_ride(ride_id)
        logger.error(f"Kafka publish failed for ride '{ride_id}': {e}")
        raise HTTPException(
            status_code=503,
            detail="Failed to publish ride acceptance event. Please retry.",
        )

    # 4. Remove from pending
    state.remove_pending_request(ride_id)

    return {
        "message": f"Ride '{ride_id}' accepted by driver '{driver_id}'.",
        "ride_id": ride_id,
        "driver_id": driver_id,
        "driver_name": driver["name"],
    }