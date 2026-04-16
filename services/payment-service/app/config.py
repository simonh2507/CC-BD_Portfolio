import os

KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS", "my-cluster-kafka-bootstrap:9092"
)
MONGO_URL = os.getenv("MONGO_URL", "mongodb://mongodb:27017")

CONSUME_TOPIC = os.getenv("CONSUME_TOPIC", "rides.fct.ride.completed")
PRODUCE_TOPIC = os.getenv("PRODUCE_TOPIC", "rides.fct.payment.completed")
GROUP_ID = os.getenv("GROUP_ID", "payment-service-group")
PRODUCE_FAILED_TOPIC = os.getenv("PRODUCE_FAILED_TOPIC", "rides.fct.payment.failed")