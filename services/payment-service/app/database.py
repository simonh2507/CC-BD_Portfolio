import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from . import config

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.client = MongoClient(config.MONGO_URL, serverSelectionTimeoutMS=5000)
        self.db = self.client["db_payment"]
        self.collection = self.db["payments"]

    def is_connected(self) -> bool:
        try:
            self.client.admin.command('ping')
            return True
        except ConnectionFailure:
            return False

    def save_payment(self, ride_id: str, amount: float, status: str) -> dict:
        record = {
            "ride_id": ride_id,
            "amount": amount,
            "status": status
        }
        self.collection.update_one({"ride_id": ride_id}, {"$set": record}, upsert=True)
        return record

    def get_payment(self, ride_id: str) -> dict | None:
        record = self.collection.find_one({"ride_id": ride_id})
        if record:
            record.pop("_id", None)  # Remove internal MongoDB ID for JSON serialization
        return record

db_manager = DatabaseManager()
