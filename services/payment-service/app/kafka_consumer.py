import json
import logging
import threading
import random
from confluent_kafka import Consumer, KafkaError, KafkaException
from . import config
from .database import db_manager
from .kafka_producer import kafka_producer

logger = logging.getLogger(__name__)

class KafkaConsumerManager:
    def __init__(self, conf: dict) -> None:
        self._conf = conf
        self._consumer: Consumer | None = None
        self.running = False
        self._thread = threading.Thread(target=self._consume_loop, daemon=True)

    def start(self) -> None:
        self._consumer = Consumer(self._conf)
        self._consumer.subscribe([config.KAFKA_TOPIC_RIDE_COMPLETED])
        self.running = True
        self._thread.start()
        logger.info(f"Kafka consumer started, subscribed to: [{config.KAFKA_TOPIC_RIDE_COMPLETED}]")

    def stop(self) -> None:
        self.running = False
        self._thread.join()
        if self._consumer:
            self._consumer.close()
        logger.info("Kafka consumer stopped.")

    def _consume_loop(self) -> None:
        while self.running:
            try:
                msg = self._consumer.poll(timeout=1.0)
                if msg is None: continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF: continue
                    raise KafkaException(msg.error())

                topic = msg.topic()
                raw_value = msg.value()
                if raw_value is None: continue

                payload = json.loads(raw_value.decode("utf-8"))
                logger.info(f"Received message on topic '{topic}': {payload}")

                if topic == config.KAFKA_TOPIC_RIDE_COMPLETED:
                    self._process_payment(payload)

            except Exception as e:
                logger.error(f"Error in consumer loop: {e}")

    def _process_payment(self, payload: dict) -> None:
        ride_id = payload.get("ride_id")
        amount = payload.get("fare_amount", 0.0)

        # SAGA: 20% chance of payment failure
        if random.random() < 0.2:
            logger.warning(f"SAGA Rollback: Payment failed for ride {ride_id}!")
            db_manager.save_payment(ride_id, amount, "FAILED")
            
            kafka_producer.produce(
                topic=config.KAFKA_TOPIC_PAYMENT_FAILED,
                key=str(ride_id),
                payload={"ride_id": ride_id, "reason": "Insufficient funds"}
            )
        else:
            logger.info(f"Payment successful for ride {ride_id}.")
            db_manager.save_payment(ride_id, amount, "SUCCESS")
            
            kafka_producer.produce(
                topic=config.KAFKA_TOPIC_PAYMENT_COMPLETED,
                key=str(ride_id),
                payload={"ride_id": ride_id, "status": "PAID"}
            )

kafka_consumer = KafkaConsumerManager(config.CONSUMER_CONFIG)
