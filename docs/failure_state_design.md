# Failure-State Design & System Resilience

## 1. The Real-World Telemetry Environment

Real-world enterprise network telemetry rarely arrives in clean, synchronized, chronological streams. Across distributed WAN links, packets encounter retransmissions, jittery transmission queues, route flapping, and edge proxy drops.

The Experience Recorder is engineered with defensive architectural patterns to handle four primary failure states:
1. **Duplicate Event Delivery** (At-least-once message queues, retry loops).
2. **Out-of-Order Delivery** (Multi-path WAN routing, jittery transit delays).
3. **Delayed Delivery** (Long store-and-forward transit delays).
4. **Collector Disconnection** (Edge buffer queueing and ordered replay).

---

## 2. Duplicate Event Handling (Idempotency)

### Problem
When active probes or edge forwarders fail to receive an HTTP `200 OK` acknowledgment due to transient packet loss, client retry mechanisms re-transmit the event. 
If an ingestion pipeline naively inserts duplicates:
- Statistical aggregates (average latency, total loss) become distorted.
- Database tables become bloated with redundant rows.
- False alarms can be triggered by multiplied synthetic readings.

### Solution Pattern
1. **Unique Identity Keying**: Every measurement has a client-generated UUID `event_id` (e.g., `PRB-9F2D8A710BC3`).
2. **Database Unique Constraint**: The `events.event_id` column is enforced with a database-level `UNIQUE` index.
3. **Pre-Insert Idempotency Check**: The collector queries `db.query(Event).filter(Event.event_id == validated["event_id"]).first()`.
4. **Graceful Discard & Audit**:
   - If present, the duplicate payload is discarded immediately without writing to `events`.
   - The transaction is logged in `event_processing_log` with status `DUPLICATE_REJECTED`.
   - The HTTP response returns `{"success": true, "status": "DUPLICATE_REJECTED"}` so the forwarder acknowledges successful processing.

```text
Incoming Event [E002] 
         |
         v
Check DB for E002?
    /         \
  No           Yes
  /             \
Insert to DB     Discard Duplicate
Log 'VALID'      Log 'DUPLICATE_REJECTED'
Return Success   Return Success (Idempotent)
```

---

## 3. Out-of-Order Event Handling

### Problem
Two consecutive probe measurements generated at $t_1 = 10:00:10$ and $t_2 = 10:00:20$ might traverse different SD-WAN tunnels. $t_2$ may arrive at the central collector at $10:00:21$, while $t_1$ arrives late at $10:00:25$.
If the monitoring system evaluates state strictly based on *arrival time*, the incident detector would register an artificial recovery followed by an artificial re-trigger.

### Solution Pattern
1. **Separation of Source Time and Arrival Time**:
   - `event_time`: The source-side timestamp when the packet was transmitted.
   - `arrival_time`: The collector timestamp when the HTTP payload was received.
2. **State Ordering by `event_time`**:
   - All analytical window queries, correlation engines, and timeline visualizers sort explicitly by `Event.event_time.asc()`.
3. **Out-of-Order Detection**:
   - The collector maintains the latest seen `event_time` per branch.
   - If `event_time < latest_seen_event_time[branch_id]`, the event is flagged as `OUT_OF_ORDER` in the processing log.
   - The event is correctly stored in the database at its historical chronological position.

```text
Sequence of Occurrence:
E1 (10:00:10) ---> E2 (10:00:20) ---> E3 (10:00:30)

Sequence of Arrival at Collector:
E1 (Arrival: 10:00:11)
E3 (Arrival: 10:00:31) -> (latest_seen = 10:00:30)
E2 (Arrival: 10:00:33) -> (event_time 10:00:20 < 10:00:30) -> Flagged 'OUT_OF_ORDER'

Reconstructed Ground-Truth Timeline:
10:00:10 [E1] -> 10:00:20 [E2] -> 10:00:30 [E3]  (PERFECT RECONSTRUCTION)
```

---

## 4. Delayed Event Handling

### Problem
A branch experiencing extreme bufferbloat or transient WAN disconnection may delay transmitting a batch of events by 2 to 5 minutes.
When the delayed batch finally reaches the collector, a naive detector might interpret those historical readings as a *brand-new failure occurring right now*, generating false alarms.

### Solution Pattern
1. **Transit Latency Calculation**:
   $$\Delta t_{\text{transit}} = t_{\text{arrival}} - t_{\text{event}}$$
2. **Threshold Flagging**:
   - If $\Delta t_{\text{transit}} > 60\text{ seconds}$, the event is tagged as `DELAYED`.
3. **Backfill Association**:
   - The event is placed into the historical record matching its `event_time`.
   - The correlation engine evaluates the incident window relative to the event's timestamp, preventing false instantaneous alerts.

---

## 5. Collector Disconnection & Edge Buffering

### Problem
If the central collector server is rebooted or the branch WAN link completely drops, active probes and metric collectors at the branch cannot reach the central API.

### Solution Pattern
1. **Local Edge Buffer**:
   - An in-memory queue (`EventBuffer`) stores telemetry records locally when collector communication fails.
   - Optional local file persistence (`data/buffer_persistence.json`) ensures survival across edge process restarts.
2. **Ordered Drain & Replay**:
   - Once connectivity is restored, the buffer is drained.
   - All buffered events are sorted by `event_time` before replaying into the collector pipeline.
   - The standard validation, deduplication, and ordering pipeline processes each recovered event.
   - Log entries record status `RECOVERED`.
   - Zero events are lost.
