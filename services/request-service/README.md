# Request Service

The Request Service is a microservice responsible for receiving ride requests from users and queuing them for processing via Kafka.

## Functionality

- **Accept Ride Requests**: Receives requests with starting and destination points.
- **Asynchronous Processing**: Immediately acknowledges the request and assigns a unique `ride_id` (UUID), then publishes the request to a Kafka topic for processing by other services (like the driver service and ride status).
- **HATEOAS Support**: Provides a link to check the status of the requested ride.
- **Health Monitoring**: Includes health check endpoints that verify connectivity to Kafka.

## API Endpoints

### `POST /ride-requests`

Creates a new ride request.

**Request Body:**

```json
{
  "start": "Karlsruhe, Germany",
  "destination": "Stuttgart, Germany"
}
```

**Response (202 Accepted):**

```json
{
  "message": "Ride request accepted and queued.",
  "ride_id": "550e8400-e29b-41d4-a716-446655440000",
  "_links": {
    "status": {
      "href": "http://ride-status-service:8000/status/550e8400-e29b-41d4-a716-446655440000"
    }
  }
}
```

### `GET /health`

Returns the health status of the service and its dependencies (Kafka).

### `GET /ping`

Simple endpoint to verify the service is reachable.

## Environment Variables

The service can be configured using the following environment variables:

| Variable                  | Description                          | Default                           |
| ------------------------- | ------------------------------------ | --------------------------------- |
| `KAFKA_BOOTSTRAP_SERVERS` | Address of the Kafka broker(s)       | `my-cluster-kafka-bootstrap:9092` |
| `KAFKA_TOPIC`             | Kafka topic for ride requests        | `Request`                         |
| `RIDE_STATUS_URL`         | Base URL for the Ride Status service | `http://ride-status-service:8000` |
| `GPS_SERVICE_URL`         | Base URL for the GPS service         | `http://gps-service:8000`         |
| `PRICING_SERVICE_URL`     | Base URL for the Pricing service     | `http://pricing-service:8000`     |

## Deployment

### Docker

This service is continously being built into a [docker image](https://github.com/simonh2507/CC-BD_Portfolio/pkgs/container/request-service).
