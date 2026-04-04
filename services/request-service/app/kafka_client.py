import json
import logging
import threading

from confluent_kafka import KafkaError, Message, Producer

from . import config

logger = logging.getLogger(__name__)


def delivery_report(err: KafkaError | None, msg: Message) -> None:
    if err is not None:
        logger.error(f"Kafka delivery error: {err}")
    else:
        logger.debug(
            f"Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}"
        )


class KafkaProducerManager:
    def __init__(self, conf: dict) -> None:
        self.producer = Producer(conf)
        self.running = True
        self.poll_thread = threading.Thread(target=self._poll_loop, daemon=True)

    def is_connected(self) -> bool:
        try:
            self.producer.list_topics(timeout=1.0)
            return True
        except Exception as e:
            logger.error(f"Kafka health check failed: {e}")
            return False

    def start(self) -> None:
        self.poll_thread.start()

    def stop(self) -> None:
        self.running = False
        self.poll_thread.join()
        logger.info("Flushing Kafka producer on shutdown...")
        self.producer.flush(15)

    def _poll_loop(self) -> None:
        while self.running:
            self.producer.poll(0.1)

    def produce_message(self, topic: str, key: str, payload: dict) -> None:
        self.producer.produce(
            topic,
            key=key.encode("utf-8"),
            value=json.dumps(payload).encode("utf-8"),
            on_delivery=delivery_report,
        )


kafka_manager = KafkaProducerManager(config.PRODUCER_CONFIG)
