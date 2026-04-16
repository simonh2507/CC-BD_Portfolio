import threading
from typing import Optional

_lock = threading.Lock()

# Pre-seeded mock driver fleet
_drivers: dict[str, dict] = {
    "driver-1": {"name": "Anna Müller",  "status": "available", "current_ride_id": None},
    "driver-2": {"name": "Ben Schmidt",  "status": "available", "current_ride_id": None},
    "driver-3": {"name": "Clara Weber",  "status": "available", "current_ride_id": None},
}

# ride_id -> original ride-request payload (set when request arrives via Kafka)
_pending_requests: dict[str, dict] = {}


# ---- Driver helpers ----

def get_first_available_driver() -> Optional[str]:
    """Return the driver_id of the first available driver, or None."""
    with _lock:
        for driver_id, info in _drivers.items():
            if info["status"] == "available":
                return driver_id
    return None


def assign_driver(driver_id: str, ride_id: str) -> bool:
    """
    Mark a driver as on-ride atomically.
    Returns False if the driver is no longer available (race condition guard).
    """
    with _lock:
        if _drivers[driver_id]["status"] != "available":
            return False
        _drivers[driver_id]["status"] = "on_ride"
        _drivers[driver_id]["current_ride_id"] = ride_id
        return True


def release_driver_by_ride(ride_id: str) -> Optional[str]:
    """
    Free whichever driver is currently assigned to ride_id.
    Returns the released driver_id, or None if not found.
    """
    with _lock:
        for driver_id, info in _drivers.items():
            if info["current_ride_id"] == ride_id:
                info["status"] = "available"
                info["current_ride_id"] = None
                return driver_id
    return None


def get_driver(driver_id: str) -> Optional[dict]:
    with _lock:
        return dict(_drivers.get(driver_id, {})) or None


def get_all_drivers() -> dict[str, dict]:
    with _lock:
        return {k: dict(v) for k, v in _drivers.items()}


# ---- Pending request helpers ----

def add_pending_request(ride_id: str, payload: dict) -> None:
    with _lock:
        _pending_requests[ride_id] = payload


def get_pending_request(ride_id: str) -> Optional[dict]:
    with _lock:
        return _pending_requests.get(ride_id)


def remove_pending_request(ride_id: str) -> None:
    with _lock:
        _pending_requests.pop(ride_id, None)


def get_all_pending_requests() -> dict[str, dict]:
    with _lock:
        return dict(_pending_requests)