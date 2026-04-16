import json
import logging
import threading
import time
import random
from pymongo import MongoClient
from confluent_kafka import Consumer, Producer
from . import config

logger = logging.getLogger(__name__)

class PaymentWorker:
    def __init__(self):
        self.producer = Producer({"bootstrap.servers": config.KAFKA_BOOTSTRAP_SERVERS})
        self.consumer = Consumer({
            "bootstrap.servers": config.KAFKA_BOOTSTRAP_SERVERS,
            "group.id": config.GROUP_ID,
            "auto.offset.reset": "earliest"
        })
        # MongoDB Verbindung
        self.db_client = MongoClient(config.MONGO_URL)
        self.db = self.db_client["mobility_db"]
        self.collection = self.db["payments"]
        
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.consumer.subscribe([config.CONSUME_TOPIC])
        self.thread.start()
        logger.info(f"Payment Worker (DB-Hub) started.")

    def stop(self):
        self.running = False
        self.thread.join()
        self.consumer.close()

    def _run(self):
        while self.running:
            msg = self.consumer.poll(1.0)
            if msg is None: continue
            if msg.error(): continue

            try:
                raw_value = msg.value()
                if raw_value is None: continue
                
                payload = json.loads(raw_value.decode("utf-8"))
                ride_id = payload.get("ride_id")
                
                if random.random() < 0.2:
                    logger.warning(f"SAGA: Payment failed for ride {ride_id}! Initiating rollback.")
                    
                    self.collection.update_one(
                        {"ride_id": ride_id}, 
                        {"$set": {"status": "FAILED", "timestamp": time.time()}}, 
                        upsert=True
                    )
                    
                    self.producer.produce(
                        config.PRODUCE_FAILED_TOPIC,
                        key=str(ride_id).encode("utf-8"),
                        value=json.dumps({"ride_id": ride_id, "reason": "Credit card declined"}).encode("utf-8")
                    )
                else:
                    self.collection.update_one(
                        {"ride_id": ride_id}, 
                        {"$set": {"amount": payload.get("fare_amount", 0), "status": "SUCCESS", "timestamp": time.time()}}, 
                        upsert=True
                    )
                    self.producer.produce(
                        config.PRODUCE_TOPIC,
                        key=str(ride_id).encode("utf-8"),
                        value=json.dumps({"ride_id": ride_id, "status": "PAID"}).encode("utf-8")
                    )
                
                self.producer.flush()

            except Exception as e:
                logger.error(f"Worker Error: {e}")

payment_worker = PaymentWorker()
