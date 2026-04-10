# GPS Service

The GPS Service is a microservice responsible for GPS tracking and driving time estimation.

## Functionality

- **Estimated Driving Time**: Mocked driving time calculation between an origin and destination.
- **Health Monitoring**: Includes health check and ping endpoints.

## API Endpoints

### `GET /estimated-driving-time`

Estimates the driving time between two points.

**Request Body:**

```json
{
  "origin": "Karlsruhe, Germany",
  "destination": "Stuttgart, Germany"
}
```

**Response (200 OK):**

```json
{
  "origin": "Karlsruhe, Germany",
  "destination": "Stuttgart, Germany",
  "estimated_seconds": 1234
}
```

### `GET /health`

Returns the health status of the service.

### `GET /ping`

Simple endpoint to verify the service is reachable.

## Deployment

### Docker

This service is containerized using the provided `Dockerfile` and deployed as a microservice.
