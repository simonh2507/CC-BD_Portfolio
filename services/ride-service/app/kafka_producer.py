import json
import logging
import threading

from confluent_kafka import KafkaError, Message, Producer

from . import config

logger = logging.getLogger(__name__)


def _delivery_report(err: KafkaError | None, msg: Message) -> None:
    if err is not None:
        logger.error(f"Kafka delivery error: {err}")
    else:
        logger.debug(
            f"Message delivered to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()}"
        )


class KafkaProducerManager:
    def __init__(self, conf: dict) -> None:
        self.producer = Producer(conf)
        self.running = False
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)

    def start(self) -> None:
        self.running = True
        self._poll_thread.start()
        logger.info("Kafka producer started.")

    def stop(self) -> None:
        self.running = False
        self._poll_thread.join()
        logger.info("Flushing Kafka producer...")
        self.producer.flush(15)

    def _poll_loop(self) -> None:
        while self.running:
            self.producer.poll(0.1)

    def is_connected(self) -> bool:
        try:
            self.producer.list_topics(timeout=1.0)
            return True
        except Exception as e:
            logger.error(f"Kafka producer health check failed: {e}")
            return False

    def produce(self, topic: str, key: str, payload: dict) -> None:
        self.producer.produce(
            topic,
            key=key.encode("utf-8"),
            value=json.dumps(payload).encode("utf-8"),
            on_delivery=_delivery_report,
        )


kafka_producer = KafkaProducerManager(config.PRODUCER_CONFIG)
