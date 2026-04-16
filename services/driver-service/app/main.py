import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from uvicorn.logging import DefaultFormatter

from .kafka_worker import driver_worker 

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(
    DefaultFormatter("%(levelprefix)s %(name)s | %(message)s")
)
logging.root.handlers = [console_handler]
logging.root.setLevel(logging.INFO)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    driver_worker.start()
    yield
    driver_worker.stop()


app = FastAPI(lifespan=lifespan)


@app.get("/ping")
def ping():
    return {"status": "ok"}


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "driver-service"
    }
