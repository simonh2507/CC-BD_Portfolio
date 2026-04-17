import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Response, status
from uvicorn.logging import DefaultFormatter

from .kafka_consumer import kafka_consumer
from .kafka_producer import kafka_producer
from .database import db_manager

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(DefaultFormatter("%(levelprefix)s %(name)s | %(message)s"))
logging.root.handlers = [console_handler]
logging.root.setLevel(logging.INFO)

@asynccontextmanager
async def lifespan(_: FastAPI):
    kafka_producer.start()
    kafka_consumer.start()
    yield
    kafka_consumer.stop()
    kafka_producer.stop()

app = FastAPI(title="Ride Service", lifespan=lifespan)

@app.get("/ping")
def ping():
    return {"status": "ok"}

@app.get("/health")
def health_check(response: Response):
    kafka_up = kafka_producer.is_connected()
    db_up = db_manager.is_connected()
    if not (kafka_up and db_up):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if (kafka_up and db_up) else "degraded"}

@app.get("/status/{ride_id}")
def get_ride_status(ride_id: str):
    """Gibt das aktuelle Tracking der Fahrt zurück (UI/User)"""
    ride = db_manager.get_ride(ride_id)
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    return ride
