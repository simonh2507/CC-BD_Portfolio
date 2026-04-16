from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
import logging
from .kafka_worker import payment_worker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Payment Service and Kafka Worker...")
    payment_worker.start()
    yield
    logger.info("Shutting down Kafka Worker...")
    payment_worker.stop()

app = FastAPI(lifespan=lifespan)

@app.get("/payments/{ride_id}")
def get_payment_status(ride_id: str):
    record = payment_worker.collection.find_one({"ride_id": ride_id})
    if not record:
        raise HTTPException(status_code=404, detail="Payment not found or still processing")
    
    record.pop("_id", None)
    return record

@app.get("/health")
def health():
    return {"status": "ok", "db_connected": payment_worker.db_client.admin.command('ping')['ok'] == 1.0}
