from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from confluent_kafka import KafkaError, Message, Producer
import uuid
import logging
import json

import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# ---- KAFKA CONNECTION ----
try:
    producer = Producer(config.PRODUCER_CONFIG)
    logger.info("Successfully initialized Kafka Producer")
except Exception as e:
    logger.error(f"Failed to initialize Kafka Producer: {e}")
    producer = None


# ---- MODELS ----
class Request(BaseModel):
    start: str
    destination: str


# ---- ROUTES ----
@app.get("/health")
async def health_check():
    kafka_status = "connected" if producer else "not_initialized"
    return {
        "status": "ok", 
        "service": "request-service",
        "kafka_status": kafka_status
    }

@app.post("/create_request")
async def create_ride_request(request: Request) -> RedirectResponse:
    if producer is None:
        raise HTTPException(status_code=500, detail="Kafka Producer not initialized")

    ride_id = str(uuid.uuid4())
    
    payload = {
        "ride_id": ride_id,
        "start": request.start,
        "destination": request.destination
    }

    delivery_error = None
    # callback function
    def delivery_report(err: KafkaError | None, _: Message):
        nonlocal delivery_error
        if err is not None:
            delivery_error = err
    try:
        producer.produce(
            config.KAFKA_TOPIC, 
            key=ride_id.encode('utf-8'), 
            value=json.dumps(payload).encode('utf-8'),
            on_delivery=delivery_report
        )
        
        producer.flush()
        
        if delivery_error:
            logger.error(f"Kafka delivery error for ride {ride_id}: {delivery_error}")
            raise HTTPException(status_code=500, detail=f"Failed to queue ride request: {str(delivery_error)}")
            
        logger.info(f"Ride request {ride_id} successfully sent to Kafka topic {config.KAFKA_TOPIC}")
        
        redirect_url = f"{config.RIDE_STATUS_URL}/status/{ride_id}"
        return RedirectResponse(url=redirect_url, status_code=303) # redirect after posting

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating ride request: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
