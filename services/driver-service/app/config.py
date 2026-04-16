import os

# Kafka connection
KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS", "my-cluster-kafka-bootstrap:9092"
)
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "driver-service")

# Topics consumed
KAFKA_TOPIC_RIDE_REQUEST = os.getenv(
    "KAFKA_TOPIC_RIDE_REQUEST", "rides.fct.riderequest.created"
)
KAFKA_TOPIC_PAYMENT_COMPLETED = os.getenv(
    "KAFKA_TOPIC_PAYMENT_COMPLETED", "rides.fct.payment.completed"
)

# Topics produced
KAFKA_TOPIC_RIDE_ACCEPTED = os.getenv(
    "KAFKA_TOPIC_RIDE_ACCEPTED", "rides.fct.ride.accepted"
)

CONSUMER_CONFIG = {
    "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
    "group.id": KAFKA_GROUP_ID,
    "auto.offset.reset": "earliest",
    "enable.auto.commit": True,
}

PRODUCER_CONFIG = {
    "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
    "message.timeout.ms": 60000,
}