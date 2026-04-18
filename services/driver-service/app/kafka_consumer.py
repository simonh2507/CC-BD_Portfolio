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
        self._thread = threading.Thread(target=self._thread_entry, daemon=True)

    def start(self) -> None:
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
    # Thread entry — owns its own asyncio event loop
    # ------------------------------------------------------------------

    def _thread_entry(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._consume_loop())
        finally:
            loop.close()

    async def _consume_loop(self) -> None:
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

                    if topic == config.KAFKA_TOPIC_RIDE_REQUEST:
                        await self._handle_ride_request(payload)
                    elif topic == config.KAFKA_TOPIC_PAYMENT_COMPLETED:
                        await self._handle_payment_completed(payload)
                    elif topic == config.KAFKA_TOPIC_PAYMENT_FAILED:
                        await self._handle_payment_failed(payload)

                except Exception as e:
                    logger.error(
                        f"Error processing message from topic '{topic}': {e}"
                    )
        finally:
            self._consumer.close()

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    async def _handle_ride_request(self, payload: dict) -> None:
        """
        Persist an incoming ride request to MongoDB as a pending request.
        The driver explicitly accepts via POST /rides/{ride_id}/accept.
        Duplicate deliveries are safe: add_pending_request uses $setOnInsert.
        """
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
        """
        SAGA happy-path: payment succeeded.
        Release the driver assigned to this ride back to 'available'.
        """
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
        """
        SAGA compensating transaction: payment failed.

        This service's compensation step is to release the driver back to
        'available' so they are not permanently blocked by a failed ride.

        The ride-status-service independently compensates on the same event
        by setting the ride status to 'cancelled' in PostgreSQL.

        Both compensations are idempotent — safe to re-process if the event
        is delivered more than once (at-least-once Kafka semantics).
        """
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