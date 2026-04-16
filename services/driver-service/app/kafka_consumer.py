import json
import logging
import threading

from confluent_kafka import Consumer, KafkaError, KafkaException

from . import config, state

logger = logging.getLogger(__name__)


class KafkaConsumerManager:
    """
    Background Kafka consumer subscribing to:
      - rides.fct.riderequest.created  → store pending ride; find and notify available driver
      - rides.fct.payment.completed    → SAGA happy-path: release driver
    """

    def __init__(self, conf: dict) -> None:
        self._conf = conf
        self._consumer: Consumer | None = None
        self.running = False
        self._thread = threading.Thread(target=self._consume_loop, daemon=True)

    def start(self) -> None:
        self._consumer = Consumer(self._conf)
        self._consumer.subscribe(
            [
                config.KAFKA_TOPIC_RIDE_REQUEST,
                config.KAFKA_TOPIC_PAYMENT_COMPLETED,
            ]
        )
        self.running = True
        self._thread.start()
        logger.info(
            f"Kafka consumer started, subscribed to: "
            f"[{config.KAFKA_TOPIC_RIDE_REQUEST}, "
            f"{config.KAFKA_TOPIC_PAYMENT_COMPLETED}, "
        )

    def stop(self) -> None:
        self.running = False
        self._thread.join()
        if self._consumer:
            self._consumer.close()
        logger.info("Kafka consumer stopped.")

    def is_subscribed(self) -> bool:
        try:
            if self._consumer is None:
                return False
            assignment = self._consumer.assignment()
            return len(assignment) > 0
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    #  Internal                                                            #
    # ------------------------------------------------------------------ #

    def _consume_loop(self) -> None:
        while self.running:
            try:
                msg = self._consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    raise KafkaException(msg.error())

                topic = msg.topic()
                payload = json.loads(msg.value().decode("utf-8"))
                logger.info(f"Received message on topic '{topic}': {payload}")

                if topic == config.KAFKA_TOPIC_RIDE_REQUEST:
                    self._handle_ride_request(payload)
                elif topic == config.KAFKA_TOPIC_PAYMENT_COMPLETED:
                    self._handle_payment_completed(payload)

            except KafkaException as e:
                logger.error(f"Kafka consumer error: {e}")
            except Exception as e:
                logger.error(f"Unexpected error in consumer loop: {e}")

    def _handle_ride_request(self, payload: dict) -> None:
        """
        A new ride request has been published.
        Store it as a pending request so a driver can accept it via REST.
        We do NOT auto-assign here — the driver explicitly calls POST /rides/{ride_id}/accept.
        """
        ride_id = payload.get("ride_id")
        if not ride_id:
            logger.warning("Received ride request without ride_id — skipping.")
            return

        state.add_pending_request(ride_id, payload)
        available = state.get_first_available_driver()
        logger.info(
            f"New ride request queued: ride_id={ride_id}. "
            f"First available driver: {available or 'none'}"
        )

    def _handle_payment_completed(self, payload: dict) -> None:
        """SAGA happy-path: payment succeeded → release driver."""
        ride_id = payload.get("ride_id")
        if not ride_id:
            logger.warning("Payment completed event missing ride_id.")
            return

        released = state.release_driver_by_ride(ride_id)
        state.remove_pending_request(ride_id)
        if released:
            logger.info(
                f"Payment completed for ride {ride_id}. "
                f"Driver {released} is now available again."
            )
        else:
            logger.warning(
                f"Payment completed for ride {ride_id} but no driver found to release."
            )


kafka_consumer = KafkaConsumerManager(config.CONSUMER_CONFIG)