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

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_: FastAPI):
    kafka_producer.start()
    kafka_consumer.start()
    yield
    kafka_consumer.stop()
    kafka_producer.stop()

app = FastAPI(title="Payment Service", lifespan=lifespan)

@app.get("/ping")
def ping():
    return {"status": "ok"}

@app.get("/health")
def health_check(response: Response):
    kafka_up = kafka_producer.is_connected()
    db_up = db_manager.is_connected()
    
    if not (kafka_up and db_up):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        
    return {
        "status": "ok" if (kafka_up and db_up) else "degraded",
        "service": "payment-service",
        "dependencies": {
            "kafka": "up" if kafka_up else "down",
            "mongodb": "up" if db_up else "down"
        },
    }

@app.get("/payments/{ride_id}")
def get_payment(ride_id: str):
    payment = db_manager.get_payment(ride_id)
    if not payment:
        raise HTTPException(status_code=404, detail=f"Payment for ride '{ride_id}' not found.")
    return payment