import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from uvicorn.logging import DefaultFormatter

from .kafka_worker import ride_worker 

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(
    DefaultFormatter("%(levelprefix)s %(name)s | %(message)s")
)
logging.root.handlers = [console_handler]
logging.root.setLevel(logging.INFO)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    ride_worker.start()
    yield
    ride_worker.stop()


app = FastAPI(lifespan=lifespan)


@app.get("/ping")
def ping():
    return {"status": "ok"}


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "ride-service"
    }
