import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from . import config

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None
db: AsyncIOMotorDatabase | None = None


async def init_db() -> None:
    """
    Connect to MongoDB, ensure indexes, and seed the driver fleet.
    Safe to call on every startup — all writes are idempotent.
    """
    global _client, db

    _client = AsyncIOMotorClient(config.MONGODB_URL)
    db = _client[config.MONGODB_DB_NAME]

    # Unique indexes (idempotent)
    await db.drivers.create_index("driver_id", unique=True)
    await db.pending_requests.create_index("ride_id", unique=True)

    # Seed mock driver fleet — $setOnInsert only writes on actual insert,
    # so existing documents are never overwritten on restart.
    seed_drivers = [
        {
            "driver_id": "driver-1",
            "name": "Anna Müller",
            "status": "available",
            "current_ride_id": None,
        },
        {
            "driver_id": "driver-2",
            "name": "Ben Schmidt",
            "status": "available",
            "current_ride_id": None,
        },
        {
            "driver_id": "driver-3",
            "name": "Clara Weber",
            "status": "available",
            "current_ride_id": None,
        },
    ]
    for driver in seed_drivers:
        await db.drivers.update_one(
            {"driver_id": driver["driver_id"]},
            {"$setOnInsert": driver},
            upsert=True,
        )

    logger.info(
        f"MongoDB connected: {config.MONGODB_URL} / db={config.MONGODB_DB_NAME}"
    )


async def close_db() -> None:
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB connection closed.")


def is_connected() -> bool:
    """Used by the health-check endpoint."""
    return _client is not None and db is not None