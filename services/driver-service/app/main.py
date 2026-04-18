import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response, status
from uvicorn.logging import DefaultFormatter

from . import config, state
from .database import close_db, init_db, is_connected
from .kafka_consumer import kafka_consumer
from .kafka_producer import kafka_producer

# ---- Logging — identical setup to all other services ----
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
    await init_db()
    kafka_producer.start()
    kafka_consumer.start()
    yield
    kafka_consumer.stop()
    kafka_producer.stop()
    await close_db()


# ---- App ----

app = FastAPI(title="Driver Service", lifespan=lifespan)


# ---- Routes ----

@app.get("/ping")
def ping():
    return {"status": "ok"}


@app.get("/health")
async def health_check(response: Response):
    """
    Reports connectivity to Kafka (producer ping) and MongoDB (client presence).
    Returns 503 if either dependency is unavailable.
    """
    kafka_up = kafka_producer.is_connected()
    mongo_up = is_connected()
    overall_ok = kafka_up and mongo_up

    if not overall_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if overall_ok else "degraded",
        "service": "driver-service",
        "dependencies": {
            "kafka":   "up" if kafka_up else "down",
            "mongodb": "up" if mongo_up else "down",
        },
    }


@app.get("/drivers")
async def list_drivers():
    """Return the current status of all drivers (observability)."""
    return {"drivers": await state.get_all_drivers()}


@app.get("/drivers/{driver_id}")
async def get_driver(driver_id: str):
    driver = await state.get_driver(driver_id)
    if not driver:
        raise HTTPException(
            status_code=404, detail=f"Driver '{driver_id}' not found."
        )
    return driver


@app.get("/rides/pending")
async def list_pending_rides():
    """Return all ride requests currently awaiting driver acceptance."""
    return {"pending_rides": await state.get_all_pending_requests()}


@app.post("/rides/{ride_id}/accept", status_code=status.HTTP_200_OK)
async def accept_ride(ride_id: str, driver_id: str):

    # 1. Verify ride is pending
    ride_data = await state.get_pending_request(ride_id)
    if not ride_data:
        raise HTTPException(
            status_code=404,
            detail=f"Ride '{ride_id}' not found or already accepted.",
        )

    # 2. Verify driver exists
    driver = await state.get_driver(driver_id)
    if not driver:
        raise HTTPException(
            status_code=404, detail=f"Driver '{driver_id}' not found."
        )

    # 3. Atomic assignment — returns False if driver is already on_ride
    assigned = await state.assign_driver(driver_id, ride_id)
    if not assigned:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Driver '{driver_id}' is currently unavailable "
                f"(status is not 'available')."
            ),
        )

    # 4. Publish ride accepted event to Kafka
    event_payload = {
        "ride_id":     ride_id,
        "driver_id":   driver_id,
        "driver_name": driver["name"],
        "start":       ride_data.get("start"),
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
        # Roll back the MongoDB assignment so the driver is not stuck
        await state.release_driver_by_ride(ride_id)
        logger.error(
            f"Kafka publish failed for ride '{ride_id}': {e}. "
            f"Driver assignment rolled back."
        )
        raise HTTPException(
            status_code=503,
            detail="Failed to publish ride acceptance event. Please retry.",
        )

    # 5. Remove from pending requests
    await state.remove_pending_request(ride_id)

    return {
        "message":     f"Ride '{ride_id}' accepted by driver '{driver_id}'.",
        "ride_id":     ride_id,
        "driver_id":   driver_id,
        "driver_name": driver["name"],
    }