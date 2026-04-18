# Driver Service

The Driver Service is a microservice responsible for managing driver availability, processing incoming ride requests, and coordinating ride acceptance within the SAGA transaction flow. Driver and ride state is persisted in a dedicated MongoDB database.

## Functionality

- **Driver State Persistence**: Stores each driver's availability (`available` / `on_ride`) and current ride assignment in MongoDB, surviving pod restarts.
- **Ride Request Processing**: Consumes new ride requests from Kafka and persists them as pending requests in MongoDB until a driver explicitly accepts.
- **Ride Acceptance**: Exposes a REST endpoint for drivers to accept a pending ride. Uses MongoDB's `find_one_and_update` to atomically assign the driver (race-condition safe) and publishes a ride-accepted event to Kafka.
- **SAGA Compensation**: On a `Payment Failed` event, triggers a compensating transaction by releasing the assigned driver back to `available` in MongoDB, making them bookable for new rides.
- **Health Monitoring**: Includes health check and ping endpoints that verify both Kafka and MongoDB connectivity.

## API Endpoints

### `POST /rides/{ride_id}/accept`

A driver accepts a pending ride request.

**Query Parameters:**

| Parameter   | Description                             | Required |
| ----------- | --------------------------------------- | -------- |
| `driver_id` | The ID of the driver accepting the ride | Yes      |

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
| `409`  | Driver is already on a ride |
| `503`  | Kafka publish failed (driver assignment is rolled back automatically) |

---

### `GET /drivers`

Returns the current status of all drivers.

**Response (200 OK):**

```json
{
  "drivers": {
    "driver-1": { "driver_id": "driver-1", "name": "Anna Müller",  "status": "available",  "current_ride_id": null },
    "driver-2": { "driver_id": "driver-2", "name": "Ben Schmidt",  "status": "on_ride",    "current_ride_id": "abc-123" },
    "driver-3": { "driver_id": "driver-3", "name": "Clara Weber",  "status": "available",  "current_ride_id": null }
  }
}
```

---

### `GET /drivers/{driver_id}`

Returns the status of a single driver.

---

### `GET /rides/pending`

Returns all ride requests currently awaiting driver acceptance.

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

Returns the health status of the service and its dependencies.

**Response (200 OK — healthy):**

```json
{
  "status": "ok",
  "service": "driver-service",
  "dependencies": {
    "kafka":   "up",
    "mongodb": "up"
  }
}
```

**Response (503 — degraded):** Same shape with `"status": "degraded"` and affected dependency set to `"down"`.

---

### `GET /ping`

Simple endpoint to verify the service is reachable.

---

## Kafka

### Consumed Topics

| Topic                           | Purpose |
| ------------------------------- | ------- |
| `rides.fct.riderequest.created` | New ride request — persist as pending in MongoDB |
| `rides.fct.payment.completed`   | SAGA happy-path — release assigned driver to `available` |
| `rides.fct.payment.failed`      | SAGA compensating transaction — release assigned driver to `available` |

### Produced Topics

| Topic                     | Purpose |
| ------------------------- | ------- |
| `rides.fct.ride.accepted` | Driver accepted a ride — consumed by the Ride Status Service |

### Event Schemas

**`rides.fct.ride.accepted` payload:**

```json
{
  "ride_id":     "abc-123",
  "driver_id":   "driver-1",
  "driver_name": "Anna Müller",
  "start":       "Karlsruhe, Germany",
  "destination": "Stuttgart, Germany"
}
```

---

## SAGA & Compensating Transaction

This service participates in the distributed SAGA that spans the full ride lifecycle.

```
rides.fct.riderequest.created
       │
       ▼
  pending ride stored in MongoDB
       │
  driver calls POST /rides/{ride_id}/accept
       │
       ▼
  driver atomically assigned (MongoDB find_one_and_update)
  rides.fct.ride.accepted published ──────────────────────▶ Ride Status Service
       │
       ▼
  ride completed (Ride Status Service)
  rides.fct.ride.completed published ─────────────────────▶ Payment Service
       │
       ├── Payment SUCCESS
       │     rides.fct.payment.completed
       │          │
       │          ▼
       │     driver released → status: available
       │
       └── Payment FAILURE
             rides.fct.payment.failed
                  │
                  ▼
             [COMPENSATING TRANSACTION]
             driver released → status: available 
             (Ride Status Service independently sets ride → cancelled)
```

### Compensation guarantees

- **Idempotent**: `release_driver_by_ride()` uses `find_one_and_update` with a predicate. Re-processing the same `payment.failed` event is a no-op if the driver is already released.
- **Independent**: Each participating service performs its own compensation. The driver-service and ride-status-service both listen to `rides.fct.payment.failed` and compensate independently — no central orchestrator is required.
- **Rollback on Kafka failure**: If the Kafka publish for `ride.accepted` fails, the driver assignment is immediately rolled back in MongoDB before returning a `503` to the caller.

---

## Database

The service uses a dedicated **MongoDB 7.0** instance (`driver-db`) deployed as a Kubernetes StatefulSet with a persistent volume claim.

### Collections

| Collection          | Purpose |
| ------------------- | ------- |
| `drivers`           | One document per driver — tracks `status` and `current_ride_id` |
| `pending_requests`  | One document per incoming ride request awaiting acceptance |

### Driver Document

```json
{
  "driver_id":       "driver-1",
  "name":            "Anna Müller",
  "status":          "available",
  "current_ride_id": null
}
```

Three mock drivers (`driver-1`, `driver-2`, `driver-3`) are seeded automatically at startup using `$setOnInsert` — idempotent across pod restarts.

### Atomic Assignment

Driver assignment uses `find_one_and_update` with a `"status": "available"` filter. Only one concurrent request can match; all others receive `None` and get a `409 Conflict` — no application-level lock needed.

---

## Environment Variables

| Variable                        | Description                             | Default                                   |
| ------------------------------- | --------------------------------------- | ----------------------------------------- |
| `MONGODB_URL`                   | MongoDB connection string               | `mongodb://driver-db:27017`               |
| `MONGODB_DB_NAME`               | MongoDB database name                   | `driverdb`                                |
| `KAFKA_BOOTSTRAP_SERVERS`       | Address of the Kafka broker(s)          | `my-cluster-kafka-bootstrap:9092`         |
| `KAFKA_GROUP_ID`                | Kafka consumer group ID                 | `driver-service`                          |
| `KAFKA_TOPIC_RIDE_REQUEST`      | Topic for incoming ride requests        | `rides.fct.riderequest.created`           |
| `KAFKA_TOPIC_PAYMENT_COMPLETED` | Topic for successful payment events     | `rides.fct.payment.completed`             |
| `KAFKA_TOPIC_PAYMENT_FAILED`    | Topic for failed payment events (SAGA)  | `rides.fct.payment.failed`                |
| `KAFKA_TOPIC_RIDE_ACCEPTED`     | Topic to publish ride acceptance events | `rides.fct.ride.accepted`                 |

`MONGODB_URL` is injected at runtime via the `driver-db-secret` Kubernetes Secret.

---

## Deployment

### Docker

This service is containerized using the provided `Dockerfile` and continuously built into a Docker image via the shared GitHub Actions CI pipeline (`.github/workflows/build-microservices.yaml`), which detects the `Dockerfile` automatically.

### Kubernetes

Apply database resources first, then the service:

```bash
# 1. MongoDB StatefulSet, headless Service, and Secret
kubectl apply -f k8s/driver-db.yaml

# 2. Driver Service Deployment and ClusterIP Service
kubectl apply -f k8s/driver-service.yaml
```
