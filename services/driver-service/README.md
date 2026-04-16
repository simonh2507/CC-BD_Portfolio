# Driver Service

The Driver Service is a microservice responsible for managing driver availability, processing incoming ride requests, and coordinating ride acceptance within the SAGA transaction flow.

## Functionality

- **Driver State Tracking**: Tracks each driver's availability (`available` vs. `on_ride`) in a thread-safe in-memory store.
- **Ride Request Processing**: Consumes new ride requests from Kafka and holds them as pending until a driver explicitly accepts.
- **Ride Acceptance**: Exposes a REST endpoint for drivers to accept a pending ride. Atomically assigns the driver and publishes a ride-accepted event to Kafka.
- **Health Monitoring**: Includes health check and ping endpoints that verify Kafka connectivity.

## API Endpoints

### `POST /rides/{ride_id}/accept`

A driver accepts a pending ride request.

**Query Parameters:**

| Parameter   | Description                          | Required |
| ----------- | ------------------------------------ | -------- |
| `driver_id` | The ID of the driver accepting the ride | Yes   |

**Response (200 OK):**

```json
{
  "message": "Ride 'abc-123' accepted by driver 'driver-1'.",
  "ride_id": "abc-123",
  "driver_id": "driver-1",
  "driver_name": "Anna Müller"
}
```

**Error Responses:**

| Status | Reason |
|--------|--------|
| `404`  | `ride_id` not found or already accepted |
| `404`  | `driver_id` not found |
| `409`  | Driver is already on a ride (race condition guard) |
| `503`  | Kafka publish failed |

---

### `GET /drivers`

Returns the current status of all drivers.

**Response (200 OK):**

```json
{
  "drivers": {
    "driver-1": { "name": "Anna Müller",  "status": "available",  "current_ride_id": null },
    "driver-2": { "name": "Ben Schmidt",  "status": "on_ride",    "current_ride_id": "abc-123" },
    "driver-3": { "name": "Clara Weber",  "status": "available",  "current_ride_id": null }
  }
}
```

---

### `GET /drivers/{driver_id}`

Returns the status of a single driver.

**Response (200 OK):**

```json
{
  "name": "Anna Müller",
  "status": "available",
  "current_ride_id": null
}
```

---

### `GET /rides/pending`

Returns all ride requests that are awaiting driver acceptance.

**Response (200 OK):**

```json
{
  "pending_rides": {
    "abc-123": {
      "ride_id": "abc-123",
      "start": "Karlsruhe, Germany",
      "destination": "Stuttgart, Germany"
    }
  }
}
```

---

### `GET /health`

Returns the health status of the service and its Kafka dependency.

**Response (200 OK — healthy):**

```json
{
  "status": "ok",
  "service": "driver-service",
  "dependencies": { "kafka": "up" }
}
```

**Response (503 — degraded):**

```json
{
  "status": "degraded",
  "service": "driver-service",
  "dependencies": { "kafka": "down" }
}
```

---

### `GET /ping`

Simple endpoint to verify the service is reachable.

---

## Kafka

### Consumed Topics

| Topic                          | Purpose |
| ------------------------------ | ------- |
| `rides.fct.riderequest.created` | Incoming ride requests — stored as pending for driver acceptance |
| `rides.fct.payment.completed`   | SAGA happy-path — releases the assigned driver after successful payment |
<!-- trunk-ignore(markdownlint/MD060) -->
| `rides.fct.payment.failed`      | SAGA compensation — releases the assigned driver when payment fails |

### Produced Topics

| Topic                    | Purpose |
| ------------------------ | ------- |
| `rides.fct.ride.accepted` | Published when a driver accepts a ride; consumed by the Ride Status Service |

### Event Schemas

**`rides.fct.ride.accepted` payload:**

```json
{
  "ride_id": "abc-123",
  "driver_id": "driver-1",
  "driver_name": "Anna Müller",
  "start": "Karlsruhe, Germany",
  "destination": "Stuttgart, Germany"
}
```
---

## Environment Variables

| Variable                     | Description                              |
| ---------------------------- | ---------------------------------------- 
| `KAFKA_BOOTSTRAP_SERVERS`    | Address of the Kafka broker(s)           |
| `KAFKA_GROUP_ID`             | Kafka consumer group ID                  |
| `KAFKA_TOPIC_RIDE_REQUEST`   | Topic for incoming ride requests         |
| `KAFKA_TOPIC_PAYMENT_COMPLETED` | Topic for successful payment events   |
| `KAFKA_TOPIC_RIDE_ACCEPTED`  | Topic to publish ride acceptance events  |
---

## Deployment

### Docker

This service is containerized using the provided `Dockerfile` and deployed as a microservice.

### Kubernetes

Deploy with the provided manifest:

```bash
kubectl apply -f k8s/driver-service.yaml
```

The manifest includes a `Deployment` (1 replica) and a `ClusterIP` `Service` on port 80.