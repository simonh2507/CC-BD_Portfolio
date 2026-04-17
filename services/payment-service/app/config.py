import os

# Kafka connection
KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS", "my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092"
)
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "payment-service")

# MongoDB connection
MONGO_URL = os.getenv("MONGO_URL", "mongodb://mongodb.ride-sharing.svc.cluster.local:27017")

# Topics consumed
KAFKA_TOPIC_RIDE_COMPLETED = os.getenv(
    "KAFKA_TOPIC_RIDE_COMPLETED", "rides.fct.ride.completed"
)

# Topics produced
KAFKA_TOPIC_PAYMENT_COMPLETED = os.getenv(
    "KAFKA_TOPIC_PAYMENT_COMPLETED", "rides.fct.payment.completed"
)
KAFKA_TOPIC_PAYMENT_FAILED = os.getenv(
    "KAFKA_TOPIC_PAYMENT_FAILED", "rides.fct.payment.failed"
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
