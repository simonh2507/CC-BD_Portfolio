import logging
import sys
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel
from uvicorn.logging import DefaultFormatter

import httpx

from . import config
from .kafka_client import kafka_manager

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(
    DefaultFormatter("%(levelprefix)s %(name)s | %(message)s")
)

logging.root.handlers = [console_handler]
logging.root.setLevel(logging.INFO)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    kafka_manager.start()
    yield
    kafka_manager.stop()


app = FastAPI(lifespan=lifespan)


# ---- MODELS ----
class RideRequest(BaseModel):
    start: str
    destination: str


# ---- HELPER ----
async def _fetch_ride_info(start: str, destination: str) -> tuple[int, float]:
    """
    Ruft GPS- und Pricing-Service auf und gibt (ride_time_seconds, fare_euro) zurück.
    Wird von /ride-info (Vorschau) und /ride-requests (Buchung) gemeinsam genutzt.
    """
    async with httpx.AsyncClient(timeout=5.0) as client:
        # 1. Fahrtdauer vom GPS-Service
        try:
            gps_resp = await client.get(
                f"{config.GPS_SERVICE_URL}/estimated-driving-time",
                params={"origin": start, "destination": destination},
            )
            gps_resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"GPS service returned HTTP error: {e}")
            raise HTTPException(
                status_code=e.response.status_code,
                detail="Error from GPS service",
            )
        except httpx.RequestError as e:
            logger.error(f"Could not connect to GPS service: {e}")
            raise HTTPException(
                status_code=503,
                detail="GPS service unavailable",
            )

        ride_time: int = gps_resp.json().get("estimated_seconds", 600)

        # 2. Preis vom Pricing-Service
        try:
            price_resp = await client.get(
                f"{config.PRICING_SERVICE_URL}/calculate-price",
                params={"ride_time_seconds": ride_time},
            )
            price_resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"Pricing service returned HTTP error: {e}")
            raise HTTPException(
                status_code=e.response.status_code,
                detail="Error from Pricing service",
            )
        except httpx.RequestError as e:
            logger.error(f"Could not connect to Pricing service: {e}")
            raise HTTPException(
                status_code=503,
                detail="Pricing service unavailable",
            )

        fare: float = price_resp.json().get("price_euro", 0.0)

    return ride_time, fare


# ---- ROUTES ----
@app.get("/ping")
def ping():
    return {"status": "ok"}


@app.get("/health")
def health_check(response: Response):
    kafka_up = kafka_manager.is_connected()
    if not kafka_up:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if kafka_up else "degraded",
        "service": "request-service",
        "dependencies": {"kafka": "up" if kafka_up else "down"},
    }


@app.get("/ride-info", status_code=status.HTTP_200_OK)
async def get_ride_info(start: str, destination: str):
    """Gibt Fahrzeit und Preis zurück, ohne eine Buchung anzulegen (Vorschau für den User)."""
    ride_time, fare = await _fetch_ride_info(start, destination)
    return {
        "start": start,
        "destination": destination,
        "ride_time_seconds": ride_time,
        "price": fare,
    }


@app.post("/ride-requests", status_code=status.HTTP_202_ACCEPTED)
async def create_ride_request(request: RideRequest):
    """Legt eine neue Fahrtanfrage an, berechnet Preis und sendet alles per Kafka."""
    ride_id = str(uuid.uuid4())

    ride_time, fare = await _fetch_ride_info(request.start, request.destination)

    payload = {
        "ride_id": ride_id,
        "start": request.start,
        "destination": request.destination,
        "ride_time_seconds": ride_time,
        "fare_amount": fare,
    }

    try:
        kafka_manager.produce_message(
            config.KAFKA_TOPIC,
            key=ride_id,
            payload=payload,
        )
        logger.info(
            f"Ride request {ride_id} successfully queued "
            f"(fare={fare:.2f}€, time={ride_time}s)"
        )
    except BufferError:
        logger.error("Kafka local queue is full.")
        raise HTTPException(
            status_code=503,
            detail="Service temporarily overloaded.",
        )
    except Exception as e:
        logger.error(f"Unexpected error creating ride request: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}",
        )

    return {
        "message": "Ride request accepted and queued.",
        "ride_id": ride_id,
        "_links": {
            "status": {
                "href": f"{config.RIDE_STATUS_URL}/status/{ride_id}",
            }
        },
    }