# CC-BD_Portfolio

Smart Mobility Plattform: Microservice-basiertes Ride-Sharing-System (Uber-Stil). Kernfeatures: SAGA-Transaktionen mit Compensation, synchrone/event-basierte Kommunikation. Orchestriert via Kubernetes inkl. Docker-Containerisierung, Zero-Downtime Updates und dedizierter Datenbank-Deployments.

## User stories

### User Story 1 & 2

> 1. Fahrt buchen
>
> > Der User will eine Fahrt von Start zu Ziel buchen. Es wird die berechnete Fahrzeit angezeigt. Außerdem wird ein Preis angezeigt. Der User bestätigt die Buchung. Wenn ein Driver die die Fahrt bestätigt, erhält der User diese Info. Während der Fahrt wird regelmäßig die Position aktualisiert um den Fahrtfortschritt zu ermitteln. Bei Ankunft am Ziel wird die Bezahlung durchgeführt.

> 2. Ein Driver bekommt die Benachrichtigung bis der User am Ziel angekommen ist
>
> > Ein Driver erhält eine Benachrichtigung, dass ein Ride verfügbar ist. Diesen kann der Driver bestätigen. Ist der User am Ziel angekommen erhält der Driver eine Benachrichtigung über den Abschluss der Fahrt. Während der Fahrt ist der Driver nicht für andere Fahrten buchbar, nach der Fahrt ist dieser wieder verfügbar.

Dieses Sequenzdiagramm stellt den Ablauf dieser beiden User stories dar:

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant System
    actor Driver

    %% User Story 1
    User->>System: Fahrtanfrage
    System-->>User: Berechnete Fahrzeit & Preis anzeigen
    User->>System: Buchung bestätigen

    %% User Story 2
    System->>Driver: Info: Neuer Ride verfügbar
    Driver->>System: Ride bestätigen

    System->>User: Info: Driver hat bestätigt

    Note over User,Driver: Während der Fahrt
    loop Regelmäßiges Tracking
        System->>System: Position aktualisieren & Fahrtfortschritt ermitteln
        System-->>User: Position und Fahrtfortschritt anzeigen
    end

    System->>User: Ankunft am Ziel anzeigen und Bezahlung anfordern
    User->>System: Bezahlung durchführen
    System->>System: Bezahlung bei Zahlungssystem bestätigen
    System->>Driver: Info: Fahrt abgeschlossen und Bezahlung durchgeführt
```

### User Story 3

> 3. Analytics (Batch Processing)
>
> > Das System analysiert regelmäßig historische Daten (z.B. Fahrten der letzten 24h) in einem Batch-Job. Die Ergebnisse werden in einer NoSQL-Datenbank gespeichert und können von anderen Services (z.B. Pricing) abgefragt werden.

## Architektur

```mermaid
flowchart TB
    classDef k8s fill:transparent,stroke:#0ea5e9,stroke-width:2px,stroke-dasharray: 5 5
    classDef kafkaCluster fill:transparent,stroke:#fb923c,stroke-width:2px,stroke-dasharray: 5 5
    classDef invisible fill:transparent,stroke:none,font-weight:bold

    classDef service fill:#3b82f6,stroke:#1e40af,stroke-width:2px,color:#fff,rx:5px,ry:5px
    classDef topic fill:#f97316,stroke:#c2410c,stroke-width:2px,color:#fff
    classDef actor fill:#14b8a6,stroke:#0f766e,stroke-width:2px,color:#fff,rx:20px,ry:20px

    User("👤 User UI"):::actor
    Driver("🧑‍✈️ Driver UI"):::actor

    subgraph K8s ["☸️ Kubernetes Cluster"]

        subgraph Services [" "]
            S_Req("📱 Request Service"):::service
            S_Price("💰 Pricing Service"):::service
            S_GPS("📍 GPS Tracking"):::service
            S_Driver("🧑‍✈️ Driver Service"):::service
            S_Ride("🚗 Ride Status"):::service
            S_Pay("💳 Payment"):::service
        end

        subgraph Kafka ["Kafka Cluster"]
            T_Req{{"Topic: Request"}}:::topic
            T_Ride{{"Topic: Ride"}}:::topic
            T_RideComp{{"Topic: Ride Completion"}}:::topic
            T_PayComp{{"Topic: Payment Completion"}}:::topic
        end
    end

    class K8s k8s
    class Kafka kafkaCluster
    class Services invisible

    User --> S_Req
    User --> S_Ride
    User --> S_Pay

    Driver --> S_Driver
    Driver --> S_Ride

    S_Req -.->|REST| S_GPS
    S_Req -.->|REST| S_Price
    S_Ride -.->|REST| S_GPS

    S_Req ===>|pub| T_Req
    T_Req ===>|sub| S_Driver

    S_Driver ===>|pub| T_Ride
    T_Ride ===>|sub| S_Ride

    S_Ride ===>|pub| T_RideComp
    T_RideComp ===>|sub| S_Pay

    S_Pay ===>|pub| T_PayComp
    T_PayComp ===>|sub| S_Driver
```
