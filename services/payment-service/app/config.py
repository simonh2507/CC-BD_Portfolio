import os

KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS", "my-cluster-kafka-bootstrap:9092"
)

CONSUME_TOPIC = os.getenv("CONSUME_TOPIC", "rides.fct.ride.completed")
PRODUCE_TOPIC = os.getenv("PRODUCE_TOPIC", "rides.fct.payment.completed")
GROUP_ID = os.getenv("GROUP_ID", "payment-service-group")