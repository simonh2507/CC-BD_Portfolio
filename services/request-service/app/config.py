import os

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "http://my-cluster-kafka-bootstrap:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "Request")

GPS_SERVICE_URL = os.getenv("GPS_SERVICE_URL", "http://gps-service:8000")
PRICING_SERVICE_URL = os.getenv("PRICING_SERVICE_URL", "http://pricing-service:8000")
RIDE_STATUS_URL = os.getenv("RIDE_STATUS_URL", "http://ride-status-service:8000")

PRODUCER_CONFIG = {
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'message.timeout.ms': 5000  # 5 seconds
}
