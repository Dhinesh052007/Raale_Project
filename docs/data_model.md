# Database Design & Data Model

## 1. Relational Schema Architecture

The database is built on **SQLite** with full foreign key constraints (`PRAGMA foreign_keys=ON`) and write-ahead logging (`PRAGMA journal_mode=WAL`) managed via **SQLAlchemy 2.0 ORM**.

```text
+------------------------------------+
|             branches               |
+------------------------------------+
| PK branch_id VARCHAR(50)           |
|    name VARCHAR(100)               |
|    region VARCHAR(50)              |
|    wan_type VARCHAR(50)            |
|    created_at DATETIME             |
+------------------------------------+
         |                 |
         | 1:N             | 1:N
         v                 v
+-----------------------+ +-----------------------+
|        events         | |       incidents       |
+-----------------------+ +-----------------------+
| PK id INTEGER AUTO    | | PK id INTEGER AUTO    |
| UK event_id VARCHAR   | | UK incident_id VARCHAR|
| FK branch_id VARCHAR  | | FK branch_id VARCHAR  |
|    event_time DATETIME| |    start_time DATETIME|
|    arrival_time DTTM  | |    end_time DATETIME  |
|    source VARCHAR     | |    status VARCHAR     |
|    latency_ms FLOAT   | |    probable_cause TEXT|
|    jitter_ms FLOAT    | |    peak_latency FLOAT |
|    packet_loss FLOAT  | |    peak_loss FLOAT    |
|    dns_response FLOAT | |    peak_app FLOAT     |
|    wifi_rssi FLOAT    | |    user_report_count  |
|    wifi_retry FLOAT   | |    severity VARCHAR   |
|    channel_util FLOAT | |    supporting_evidence|
|    app_response FLOAT | |    duration_seconds   |
|    http_status INT    | |    created_at DATETIME|
|    tx_duration FLOAT  | +-----------------------+
|    user_report TEXT   |
|    sequence_number INT|
|    created_at DATETIME|
+-----------------------+
         |
         | 1:N
         v
+-------------------------------+ +-------------------------------+
|         user_reports          | |     event_processing_log      |
+-------------------------------+ +-------------------------------+
| PK id INTEGER AUTO            | | PK id INTEGER AUTO            |
| UK report_id VARCHAR          | |    event_id VARCHAR           |
| FK branch_id VARCHAR          | |    processing_status VARCHAR  |
|    event_time DATETIME        | |    reason TEXT                |
|    location VARCHAR           | |    processed_at DATETIME      |
|    description TEXT           | +-------------------------------+
|    severity VARCHAR           |
|    created_at DATETIME        |
+-------------------------------+
```

---

## 2. Table Specifications

### 2.1 `events`
Stores raw telemetry measurements from active probes, Wi-Fi controllers, application health checks, and user complaint events.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT | Internal synthetic identifier |
| `event_id` | VARCHAR(64) | UNIQUE, NOT NULL, INDEXED | Globally unique event identifier |
| `event_time` | DATETIME | NOT NULL, INDEXED | Timestamp when event occurred at source |
| `arrival_time` | DATETIME | NOT NULL | Timestamp when event reached collector |
| `branch_id` | VARCHAR(50) | FOREIGN KEY (`branches.branch_id`) | Originating branch ID |
| `source` | VARCHAR(50) | NOT NULL, INDEXED | `ACTIVE_PROBE`, `WIFI`, `APPLICATION`, `USER_REPORT` |
| `latency_ms` | FLOAT | NULLABLE, $\ge 0$ | Network round-trip time in milliseconds |
| `jitter_ms` | FLOAT | NULLABLE, $\ge 0$ | Latency variance |
| `packet_loss_percent`| FLOAT | NULLABLE, $0 \le x \le 100$ | Measured packet loss percentage |
| `dns_response_ms` | FLOAT | NULLABLE, $\ge 0$ | DNS query resolution latency |
| `wifi_rssi` | FLOAT | NULLABLE | Wi-Fi Signal Strength in dBm (typically $-30$ to $-95$) |
| `wifi_retry_rate` | FLOAT | NULLABLE, $0 \le x \le 100$ | Wi-Fi frame retransmission rate |
| `channel_utilisation`| FLOAT | NULLABLE, $0 \le x \le 100$ | Radio channel congestion percentage |
| `application_response_ms`| FLOAT | NULLABLE, $\ge 0$| End-to-end application transaction response |
| `http_status` | INTEGER | NULLABLE, $100 \le x \le 599$ | HTTP response status code |
| `transaction_duration_ms`| FLOAT | NULLABLE, $\ge 0$ | Database / backend execution duration |
| `user_report` | TEXT | NULLABLE | Associated user complaint summary text |
| `sequence_number` | INTEGER | NULLABLE | Monotonic sequence number per source |
| `created_at` | DATETIME | DEFAULT UTC NOW | Database record creation timestamp |

**Indexes**:
- `idx_events_branch_time`: Compound index on `(branch_id, event_time)` for high-speed chronological range scans during evidence window reconstruction.
- `idx_events_source`: Index on `source` for filtered telemetry queries.

---

### 2.2 `incidents`
Stores recorded degradations, correlated peaks, and explainable localisation evidence.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT | Internal identifier |
| `incident_id` | VARCHAR(64) | UNIQUE, NOT NULL, INDEXED | Unique incident identifier (e.g., `INC-A1B2C3D4`) |
| `branch_id` | VARCHAR(50) | FOREIGN KEY (`branches.branch_id`) | Affected branch ID |
| `start_time` | DATETIME | NOT NULL, INDEXED | Earliest observed anomalous event timestamp |
| `end_time` | DATETIME | NULLABLE | Timestamp when branch returned to normal baseline |
| `status` | VARCHAR(30) | NOT NULL | `SUSPECTED`, `ACTIVE`, `RECOVERED` |
| `probable_cause` | VARCHAR(100)| NOT NULL | `WAN degradation`, `Wi-Fi degradation`, etc. |
| `peak_latency` | FLOAT | NULLABLE | Maximum observed latency during incident (ms) |
| `peak_packet_loss` | FLOAT | NULLABLE | Maximum observed packet loss (%) |
| `peak_application_response`| FLOAT | NULLABLE | Maximum observed application response (ms) |
| `user_report_count`| INTEGER | DEFAULT 0 | Count of user tickets correlated to this incident |
| `severity` | VARCHAR(20) | NOT NULL | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `supporting_evidence`| TEXT | NULLABLE | JSON document storing complete metric breakdown |
| `duration_seconds`| FLOAT | NULLABLE | Incident duration from onset to recovery |
| `created_at` | DATETIME | DEFAULT UTC NOW | Record creation timestamp |

---

### 2.3 `user_reports`
Stores complaints submitted by tellers or branch personnel.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY | Internal identifier |
| `report_id` | VARCHAR(64) | UNIQUE, NOT NULL | Unique complaint ID (e.g. `URP-7F8E9D0A`) |
| `branch_id` | VARCHAR(50) | FOREIGN KEY | Branch ID |
| `event_time` | DATETIME | NOT NULL, INDEXED | Timestamp when user experienced slowness |
| `location` | VARCHAR(100)| NOT NULL | Terminal / counter location in branch |
| `description` | TEXT | NOT NULL | Detailed text description of slowness |
| `severity` | VARCHAR(20) | DEFAULT 'HIGH' | Priority level |
| `created_at` | DATETIME | DEFAULT UTC NOW | Insertion timestamp |

---

### 2.4 `event_processing_log`
Audit trail recording data ingestion status, deduplication discards, and ordering anomalies.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PRIMARY KEY | Audit row identifier |
| `event_id` | VARCHAR(64) | Event ID evaluated |
| `processing_status` | VARCHAR(50) | `VALID`, `DUPLICATE_REJECTED`, `OUT_OF_ORDER`, `DELAYED`, `VALIDATION_FAILED`, `BUFFERED`, `RECOVERED` |
| `reason` | TEXT | Explanation of the handling decision |
| `processed_at` | DATETIME | Ingestion audit timestamp |
