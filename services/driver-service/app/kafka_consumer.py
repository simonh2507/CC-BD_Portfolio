import asyncio
import json
import logging
import threading

from confluent_kafka import Consumer, KafkaError, KafkaException

from . import config, state

logger = logging.getLogger(__name__)

class KafkaConsumerManager:
    def __init__(self, conf: dict) -> None:
        self._conf = conf
        self._consumer: Consumer | None = None
        self.running = False
        self._main_loop: asyncio.AbstractEventLoop | None = None
        self._thread = threading.Thread(target=self._consume_loop, daemon=True)

    def start(self) -> None:
        # Greife den Haupt-Event-Loop von FastAPI ab
        self._main_loop = asyncio.get_running_loop()
        self.running = True
        self._thread.start()
        logger.info(
            "Kafka consumer started, subscribed to: "
            f"[{config.KAFKA_TOPIC_RIDE_REQUEST}, "
            f"{config.KAFKA_TOPIC_PAYMENT_COMPLETED}, "
            f"{config.KAFKA_TOPIC_PAYMENT_FAILED}]"
        )

    def stop(self) -> None:
        self.running = False
        self._thread.join()
        logger.info("Kafka consumer stopped.")

    # ------------------------------------------------------------------
    # Der synchrone Thread, der Kafka pollt
    # ------------------------------------------------------------------
    def _consume_loop(self) -> None:
        self._consumer = Consumer(self._conf)
        self._consumer.subscribe(
            [
                config.KAFKA_TOPIC_RIDE_REQUEST,
                config.KAFKA_TOPIC_PAYMENT_COMPLETED,
                config.KAFKA_TOPIC_PAYMENT_FAILED,
            ]
        )
        try:
            while self.running:
                msg = self._consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    raise KafkaException(msg.error())

                topic = msg.topic()
                try:
                    payload = json.loads(msg.value().decode("utf-8"))
                    logger.info(f"Received on topic '{topic}': {payload}")

                    # FIX: Sichere Übergabe der asynchronen Handler an den Haupt-Loop!
                    if topic == config.KAFKA_TOPIC_RIDE_REQUEST:
                        asyncio.run_coroutine_threadsafe(self._handle_ride_request(payload), self._main_loop)
                    elif topic == config.KAFKA_TOPIC_PAYMENT_COMPLETED:
                        asyncio.run_coroutine_threadsafe(self._handle_payment_completed(payload), self._main_loop)
                    elif topic == config.KAFKA_TOPIC_PAYMENT_FAILED:
                        asyncio.run_coroutine_threadsafe(self._handle_payment_failed(payload), self._main_loop)

                except Exception as e:
                    logger.error(
                        f"Error processing message from topic '{topic}': {e}"
                    )
        finally:
            self._consumer.close()

    # ------------------------------------------------------------------
    # Handlers (Bleiben async, da sie Motor/MongoDB nutzen)
    # ------------------------------------------------------------------

    async def _handle_ride_request(self, payload: dict) -> None:
        ride_id = payload.get("ride_id")
        if not ride_id:
            logger.warning("Ride request event missing ride_id — skipping.")
            return

        await state.add_pending_request(ride_id, payload)
        available = await state.get_first_available_driver()
        logger.info(
            f"Ride request '{ride_id}' persisted. "
            f"First available driver: {available or 'none'}"
        )

    async def _handle_payment_completed(self, payload: dict) -> None:
        ride_id = payload.get("ride_id")
        if not ride_id:
            logger.warning("Payment completed event missing ride_id — skipping.")
            return

        released = await state.release_driver_by_ride(ride_id)
        if released:
            logger.info(
                f"[SAGA happy-path] Payment completed for ride '{ride_id}'. "
                f"Driver '{released}' is available again."
            )
        else:
            logger.warning(
                f"[SAGA happy-path] Payment completed for ride '{ride_id}' "
                f"but no assigned driver found in MongoDB."
            )

    async def _handle_payment_failed(self, payload: dict) -> None:
        ride_id = payload.get("ride_id")
        if not ride_id:
            logger.warning("Payment failed event missing ride_id — skipping.")
            return

        logger.warning(
            f"[SAGA compensation] Payment failed for ride '{ride_id}'. "
            f"Initiating compensating transaction: releasing driver."
        )

        released = await state.release_driver_by_ride(ride_id)
        if released:
            logger.info(
                f"[SAGA compensation] Driver '{released}' released from ride '{ride_id}'. "
                f"Driver status reset to 'available'."
            )
        else:
            logger.warning(
                f"[SAGA compensation] No driver found for ride '{ride_id}' in MongoDB. "
                f"Compensation is a no-op (possibly already released or never assigned)."
            )

kafka_consumer = KafkaConsumerManager(config.CONSUMER_CONFIG)