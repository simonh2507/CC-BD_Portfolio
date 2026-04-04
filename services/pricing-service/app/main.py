import logging
import sys
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

app = FastAPI(title="Pricing Service")

# ---- MODELS ----
class PriceResponse(BaseModel):
    ride_time_seconds: int
    price_euro: float

# ---- CONSTANTS ----
BASE_FARE = 2.50
PRICE_PER_SECOND = 0.005 # 18€ per hour

# ---- ROUTES ----
@app.get("/ping")
def ping():
    return {"status": "ok"}

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "pricing-service",
        "dependencies": {}
    }

@app.get("/calculate-price", response_model=PriceResponse)
def calculate_price(ride_time_seconds: int):
    logger.info(f"Calculating price for ride time: {ride_time_seconds} seconds")
    
    # simple mock pricing
    price = BASE_FARE + (PRICE_PER_SECOND * ride_time_seconds)
    
    return PriceResponse(
        ride_time_seconds=ride_time_seconds,
        price_euro=round(price, 2)
    )
