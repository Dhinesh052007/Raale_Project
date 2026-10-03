# System Architecture

## 1. Architectural Overview

The **End-to-End Experience Recorder** is engineered as a decoupled, multi-tier pipeline designed for high resilience, deterministic reproducibility, and zero data loss under hostile network conditions.

```text
                    SIMULATED BRANCHES (50+ Branches)
                                   |
        +--------------------------+--------------------------+
        |                          |                          |
        v                          v                          v
   Active Probe               Wi-Fi Metrics              Application
     Simulator                  Simulator                 Simulator
 (Latency, Loss, Jitter)   (RSSI, Retries, Util)   (Response Time, HTTP)
        |                          |                          |
        +--------------------------+--------------------------+
                                   |
                                   v
                            EVENT COLLECTOR
                 (Accepts multi-source branch events)
                                   |
                                   v
                            EVENT VALIDATOR
           (Schema validation, negative checks, boundary guards)
                                   |
                                   v
                            EVENT PROCESSOR
                 (Deduplication, Out-of-order, Delay detection)
                                   |
                    +--------------+--------------+
                    |                             |
                    v                             v
             EVENT STORAGE                   EVENT BUFFER
         SQLite (Persistent Store)       / Edge Disconnection Recovery
                    |                             |
                    +--------------+--------------+
                                   |
                                   v
                          CORRELATION ENGINE
             (Sliding temporal window, branch grouping)
                                   |
                                   v
                          INCIDENT DETECTOR
           (Lifecycle: NORMAL -> SUSPECTED -> ACTIVE -> RECOVERED)
                                   |
                                   v
                         LOCALISATION ENGINE
        (Explainable rule-based decision tree with evidence scoring)
                                   |
                                   v
                         EXPERIENCE RECORDER
             (Preserves 2m Before + Incident + 2m After Window)
                                   |
                                   v
                            FASTAPI BACKEND
            (RESTful JSON APIs, OpenAPI / Swagger Documentation)
                                   |
                                   v
                          STREAMLIT DASHBOARD
             (Executive Overview, Deep-Dive, Forensic Timeline,
              Resilience Lab, 100-Incident Benchmark Suite)
                                   |
                                   v
                           NETWORK ENGINEER
```

---

## 2. Core Subsystems

### 2.1 Branch Telemetry Simulators (`src/simulator/`)
- Generates multi-modal telemetry across 50 simulated branches (scalable to hundreds).
- Deterministic initialization via seed (default: 42) ensures scientific reproducibility.
- **Active Probe**: Latency (ms), Jitter (ms), Packet Loss (%), DNS response time (ms).
- **Wi-Fi Infrastructure**: RSSI (dBm), Retry Rate (%), Channel Utilisation (%).
- **Application Monitor**: Response Time (ms), HTTP Status (200, 500, 503), Transaction Duration (ms).
- **User Reports**: Branch counter complaints with location, description, and severity.

### 2.2 Ingestion & Resilience Engine (`src/collector/`)
- **Event Validator (`validator.py`)**: Pydantic schema validation, range checks (packet loss $\in [0, 100]\%$, latency $\ge 0$, valid HTTP codes). Fault isolation ensures bad records never crash the ingestion pipeline.
- **Event Deduplicator (`collector.py`)**: Idempotent event handling keyed on `event_id`. Duplicate deliveries are dropped and audited as `DUPLICATE_REJECTED` in `event_processing_log`.
- **Chronological Reordering**: Evaluates `event_time` rather than `arrival_time`. Out-of-order deliveries are reconciled into true historical sequence.
- **Transit Delay Detection**: Detects events arriving $> 60\text{s}$ after occurrence and associates them with historical windows without triggering false new incidents.
- **Edge Buffer & Recovery (`buffer.py`)**: Queues telemetry locally during collector outages; replays and reconciles ordered events upon link restoration.

### 2.3 Analytic Engines (`src/engine/`)
- **Baseline Monitor (`baseline.py`)**: Traditional threshold monitor (e.g. latency $> 150\text{ms}$) acting as an experimental control.
- **Correlation Engine (`recorder.py`)**: Aggregates multi-source events occurring within a 180-second sliding window for a given branch into a unified incident cluster.
- **Incident Lifecycle State Machine**:
  $$\text{NORMAL} \longrightarrow \text{SUSPECTED} \longrightarrow \text{ACTIVE} \longrightarrow \text{RECOVERED}$$
  Incidents persist indefinitely after recovery for post-hoc root cause analysis.
- **Localisation Engine (`localisation.py`)**: Explainable decision logic classifying degradations into:
  - `WAN degradation`
  - `Wi-Fi degradation`
  - `Application degradation`
  - `Multiple contributing signals`
  - `Insufficient evidence`
- **Forensic Evidence Window (`recorder.py`)**: Captures telemetry from 2 minutes before incident start to 2 minutes after incident recovery.

### 2.4 Presentation Tier
- **FastAPI REST API (`src/api/`)**: High-performance backend providing full JSON API endpoints with Swagger UI.
- **Streamlit Interactive Dashboard (`dashboard/app.py`)**: Full visual observability suite with Plotly interactive charts, live failure injection controls, and automated benchmark comparison.
