import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from . import config

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.client = MongoClient(config.MONGO_URL, serverSelectionTimeoutMS=5000)
        self.db = self.client["db_ride"] # Eigene logische DB!
        self.collection = self.db["rides"]

    def is_connected(self) -> bool:
        try:
            self.client.admin.command('ping')
            return True
        except ConnectionFailure:
            return False

    def update_ride_status(self, ride_id: str, status: str, driver_id: str = None) -> dict:
        update_fields = {"status": status}
        if driver_id:
            update_fields["driver_id"] = driver_id
            
        self.collection.update_one(
            {"ride_id": ride_id}, 
            {"$set": update_fields}, 
            upsert=True
        )
        return self.get_ride(ride_id)

    def get_ride(self, ride_id: str) -> dict | None:
        record = self.collection.find_one({"ride_id": ride_id})
        if record:
            record.pop("_id", None)
        return record

db_manager = DatabaseManager()
