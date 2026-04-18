import logging
from typing import Optional

from . import database

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Driver helpers
# ---------------------------------------------------------------------------

async def get_first_available_driver() -> Optional[str]:
    """Return the driver_id of the first available driver, or None."""
    doc = await database.db.drivers.find_one({"status": "available"})
    return doc["driver_id"] if doc else None


async def assign_driver(driver_id: str, ride_id: str) -> bool:
    """
    Atomically transition a driver from 'available' → 'on_ride'.

    The filter includes status='available', so if two concurrent requests
    race, only one will match and the second will receive None → returns False.
    No application-level lock required.
    """
    result = await database.db.drivers.find_one_and_update(
        {"driver_id": driver_id, "status": "available"},
        {"$set": {"status": "on_ride", "current_ride_id": ride_id}},
    )
    return result is not None


async def release_driver_by_ride(ride_id: str) -> Optional[str]:
    """
    Free whichever driver is currently assigned to ride_id.
    Called both on the SAGA happy-path (payment completed) and on the
    compensating transaction (payment failed).
    Returns the released driver_id, or None if no match found.
    """
    result = await database.db.drivers.find_one_and_update(
        {"current_ride_id": ride_id},
        {"$set": {"status": "available", "current_ride_id": None}},
    )
    if result:
        released_id = result["driver_id"]
        logger.info(
            f"Driver '{released_id}' released from ride '{ride_id}' "
            f"→ status set to 'available'."
        )
        return released_id
    return None


async def get_driver(driver_id: str) -> Optional[dict]:
    """Return a single driver document (without Mongo _id), or None."""
    return await database.db.drivers.find_one(
        {"driver_id": driver_id}, {"_id": 0}
    )


async def get_all_drivers() -> dict[str, dict]:
    """Return all driver documents keyed by driver_id."""
    cursor = database.db.drivers.find({}, {"_id": 0})
    return {d["driver_id"]: d async for d in cursor}


# ---------------------------------------------------------------------------
# Pending request helpers
# ---------------------------------------------------------------------------

async def add_pending_request(ride_id: str, payload: dict) -> None:
    """
    Persist a new pending ride request. Uses $setOnInsert so duplicate
    Kafka deliveries (at-least-once) do not overwrite the existing document.
    """
    await database.db.pending_requests.update_one(
        {"ride_id": ride_id},
        {"$setOnInsert": payload},
        upsert=True,
    )


async def get_pending_request(ride_id: str) -> Optional[dict]:
    return await database.db.pending_requests.find_one(
        {"ride_id": ride_id}, {"_id": 0}
    )


async def remove_pending_request(ride_id: str) -> None:
    await database.db.pending_requests.delete_one({"ride_id": ride_id})


async def get_all_pending_requests() -> dict[str, dict]:
    cursor = database.db.pending_requests.find({}, {"_id": 0})
    return {r["ride_id"]: r async for r in cursor}