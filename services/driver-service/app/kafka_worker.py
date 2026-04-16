import json
import logging
import threading
import time

from confluent_kafka import Consumer, Producer

from . import config

logger = logging.getLogger(__name__)

class DriverWorker:
    def __init__(self):
        self.producer = Producer({"bootstrap.servers": config.KAFKA_BOOTSTRAP_SERVERS})
        self.consumer = Consumer({
            "bootstrap.servers": config.KAFKA_BOOTSTRAP_SERVERS,
            "group.id": config.GROUP_ID,
            "auto.offset.reset": "earliest"
        })
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.consumer.subscribe([config.CONSUME_TOPIC])
        self.thread.start()
        logger.info(f"Driver Worker started, listening on {config.CONSUME_TOPIC}")

    def stop(self):
        self.running = False
        self.thread.join()
        self.consumer.close()
        self.producer.flush()
        logger.info("Driver Worker stopped.")

    def _run(self):
        while self.running:
            msg = self.consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                logger.error(f"Kafka error: {msg.error()}")
                continue

            try:
                payload = json.loads(msg.value().decode("utf-8"))
                ride_id = payload.get("ride_id")
                logger.info(f"Processing driver assignment for ride_id: {ride_id}")

                time.sleep(1)
                driver_id = "Driver_42_Mock"
                
                result_payload = {
                    "ride_id": ride_id,
                    "driver_assigned": driver_id,
                    "status": "ACCEPTED"
                }
                
                self.producer.produce(
                    config.PRODUCE_TOPIC,
                    key=str(ride_id).encode("utf-8"),
                    value=json.dumps(result_payload).encode("utf-8")
                )
                self.producer.poll(0)
                logger.info(f"Driver {driver_id} assigned! Event sent to {config.PRODUCE_TOPIC}")

            except Exception as e:
                logger.error(f"Error processing message: {e}")

driver_worker = DriverWorker()
