import json
import logging
import threading
import time
from confluent_kafka import Consumer, KafkaException, KafkaError
from . import config
from .database import db_manager
from .kafka_producer import kafka_producer

logger = logging.getLogger(__name__)

class KafkaConsumerManager:
    def __init__(self, conf: dict) -> None:
        self._conf = conf
        self._consumer = None
        self.running = False
        self._thread = threading.Thread(target=self._consume_loop, daemon=True)

    def start(self) -> None:
        self._consumer = Consumer(self._conf)
        self._consumer.subscribe([
            config.KAFKA_TOPIC_RIDE_ACCEPTED,
            config.KAFKA_TOPIC_PAYMENT_FAILED,
        ])
        self.running = True
        self._thread.start()
        logger.info(f"Ride Service subscribed to [{config.KAFKA_TOPIC_RIDE_ACCEPTED}]")

    def stop(self) -> None:
        self.running = False
        self._thread.join()
        if self._consumer: self._consumer.close()

    def _consume_loop(self) -> None:
        while self.running:
            try:
                msg = self._consumer.poll(1.0)
                if msg is None:continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF: continue
                    raise KafkaException(msg.error())

                raw_value = msg.value()
                if raw_value is None: continue

                payload = json.loads(raw_value.decode("utf-8"))
                topic = msg.topic()
                
                if topic == config.KAFKA_TOPIC_RIDE_ACCEPTED:
                    threading.Thread(target=self._simulate_ride, args=(payload,), daemon=True).start()

                elif topic == config.KAFKA_TOPIC_PAYMENT_FAILED:
                    self._handle_payment_failed(payload)

            except Exception as e:
                logger.error(f"Consumer Error: {e}")

    def _simulate_ride(self, payload: dict):
        ride_id = payload.get("ride_id")
        driver_id = payload.get("driver_id")
        
        logger.info(f"Ride {ride_id} ACTIVE with driver {driver_id}.")
        db_manager.update_ride_status(ride_id, "ACTIVE", driver_id)
        fare = payload.get("fare_amount", 0.0)
        kafka_producer.produce(
            topic=config.KAFKA_TOPIC_RIDE_COMPLETED,
            key=str(ride_id),
            payload={"ride_id": ride_id, "driver_id": driver_id,
                 "fare_amount": fare}
        )
        try:
            kafka_producer.produce(
            topic=config.KAFKA_TOPIC_RIDE_COMPLETED,
            key=str(ride_id),
            payload={"ride_id": ride_id, "driver_id": driver_id, "fare_amount": 15.50}
        )
        except Exception as e:
            logger.error(f"Kafka publish failed for ride '{ride_id}': {e}. "
                f"Setting status to PAYMENT_ERROR.")
            db_manager.update_ride_status(ride_id, "PAYMENT_ERROR")

    def _handle_payment_failed(self, payload: dict) -> None:
        ride_id = payload.get("ride_id")
        if not ride_id:
            return
        db_manager.update_ride_status(ride_id, "CANCELLED")
        logger.warning(f"[SAGA compensation] Ride '{ride_id}' set to CANCELLED.")

kafka_consumer = KafkaConsumerManager(config.CONSUMER_CONFIG)
