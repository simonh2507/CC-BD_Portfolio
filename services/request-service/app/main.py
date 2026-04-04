import logging
import sys
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel
from uvicorn.logging import DefaultFormatter

from . import config
from .kafka_client import kafka_manager

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(
    DefaultFormatter("%(levelprefix)s %(name)s | %(message)s")
)  # like uvicorn

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
class Request(BaseModel):
    start: str
    destination: str


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


@app.post("/ride-requests", status_code=status.HTTP_202_ACCEPTED)
def create_ride_request(request: Request):
    ride_id = str(uuid.uuid4())

    payload = {
        "ride_id": ride_id,
        "start": request.start,
        "destination": request.destination,
    }

    try:
        kafka_manager.produce_message(
            config.KAFKA_TOPIC,
            key=ride_id,
            payload=payload,
        )
        logger.info(
            f"Ride request {ride_id} successfully queued for Kafka topic {config.KAFKA_TOPIC}"
        )

    except BufferError:
        logger.error("Kafka local queue is full.")
        raise HTTPException(status_code=503, detail="Service temporarily overloaded.")
    except Exception as e:
        logger.error(f"Unexpected error creating ride request: {e}")
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
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
