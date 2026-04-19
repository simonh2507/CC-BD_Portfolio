import os

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "ride-service")
MONGO_URL = os.getenv("MONGO_URL", "mongodb://mongodb.ride-sharing.svc.cluster.local:27017")
GPS_SERVICE_URL = os.getenv("GPS_SERVICE_URL", "http://gps-service:80")

# Topics
KAFKA_TOPIC_RIDE_ACCEPTED = os.getenv("KAFKA_TOPIC_RIDE_ACCEPTED", "rides.fct.ride.accepted")
KAFKA_TOPIC_RIDE_COMPLETED = os.getenv("KAFKA_TOPIC_RIDE_COMPLETED", "rides.fct.ride.completed")
KAFKA_TOPIC_PAYMENT_FAILED = os.getenv("KAFKA_TOPIC_PAYMENT_FAILED", "rides.fct.payment.failed")

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
