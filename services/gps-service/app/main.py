import logging
import sys
import random
from fastapi import FastAPI
from pydantic import BaseModel
from uvicorn.logging import DefaultFormatter

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(
    DefaultFormatter("%(levelprefix)s %(name)s | %(message)s")
)

logging.root.handlers = [console_handler]
logging.root.setLevel(logging.INFO)

logger = logging.getLogger(__name__)

app = FastAPI(title="GPS Service")

# ---- MODELS ----
class DrivingTimeEstimation(BaseModel):
    origin: str
    destination: str
    estimated_seconds: int

# ---- ROUTES ----
@app.get("/ping")
def ping():
    return {"status": "ok"}

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "gps-service",
        "dependencies": {}
    }

@app.get("/estimated-driving-time", response_model=DrivingTimeEstimation)
def estimate_driving_time(origin: str, destination: str):
    logger.info(f"Estimating driving time from {origin} to {destination}")
    
    # Deterministic based on origin and destination
    seed_str = f"{origin}-{destination}"
    rng = random.Random(seed_str)
    estimated_seconds = rng.randint(300, 1800)
    
    return DrivingTimeEstimation(
        origin=origin, 
        destination=destination, 
        estimated_seconds=estimated_seconds
    )
