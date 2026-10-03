# End-to-End Experience Recorder for Capturing and Localising Intermittent Service Degradation in Branch-Based Financial Organisations

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.38%2B-FF4B4B.svg)](https://streamlit.io/)
[![SQLite](https://img.shields.io/badge/Database-SQLite%20WAL-003B57.svg)](https://www.sqlite.org/)
[![Tests](https://img.shields.io/badge/Tests-26%20Passed-brightgreen.svg)]()

> A complete, production-grade software prototype designed to capture, correlate, localise, and preserve evidence of transient network and service degradations across distributed branch banking environments.

---

## 1. The Core Problem

In branch-based financial institutions with hundreds of distributed WAN circuits, users frequently encounter **intermittent slowness** that recovers before support engineers can investigate:

```text
10:20 AM  —  User experiences severe application slowness
10:21 AM  —  User reports issue to central helpdesk
10:25 AM  —  Support engineer investigates
10:25 AM  —  Transient issue has disappeared; everything looks normal!
```

Traditional monitoring tools (SNMP pollers, stateless ping threshold alerts) clear active alarms when conditions return to normal. Consequently, engineers lack historical evidence and close tickets with status **"Unable to Reproduce."**

### The Solution: Experience Recorder
The **End-to-End Experience Recorder** works as an **additional evidence layer** alongside existing helpdesk ticketing systems:

$$\text{Detect} \longrightarrow \text{Record} \longrightarrow \text{Correlate} \longrightarrow \text{Localise} \longrightarrow \text{Preserve Evidence} \longrightarrow \text{Recover} \longrightarrow \text{Engineer Investigation}$$

Crucially, the system preserves a complete **Forensic Evidence Window**:
$$\text{Evidence Window} = \text{2 min BEFORE} + \text{INCIDENT PERIOD} + \text{2 min AFTER RECOVERY}$$

---

## 2. Architecture & Pipeline

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
                 (Validation, Deduplication, Ordering)
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
                    +--------------+--------------+
                    |                             |
                    v                             v
             FASTAPI BACKEND             STREAMLIT DASHBOARD
          (RESTful JSON APIs)        (Visual Observability Suite)
```

---

## 3. Technology Stack

- **Backend**: Python 3.11+, FastAPI, Uvicorn
- **Database**: SQLite with Write-Ahead Logging (`WAL`), SQLAlchemy 2.0 ORM
- **Data Engineering**: Pandas, NumPy
- **Data Validation**: Pydantic v2
- **Dashboard**: Streamlit, Plotly Express & Graph Objects
- **Testing**: PyTest, TestClient, StaticPool SQLite in-memory fixtures

*No heavy dependencies, Kubernetes, Kafka, or complex cloud infrastructure required. Designed to run seamlessly on a standard student laptop.*

---

## 4. Project Directory Structure

```text
COE_Project/
├── dashboard/
│   └── app.py                      # Multi-view Streamlit interactive dashboard
├── data/
│   ├── experience_recorder.db     # SQLite persistence database (created on init)
│   └── experiment_results.json    # Empirical 100-incident benchmark results
├── docs/
│   ├── architecture.md            # In-depth architectural design
│   ├── data_model.md              # Database schema and field specifications
│   ├── demo.md                    # 3-minute structured presentation script
│   ├── error_analysis.md          # Scientific error analysis of boundary cases
│   ├── experiments.md             # Benchmark methodology and results
│   ├── failure_state_design.md    # Deduplication, ordering, and buffer resilience
│   ├── final_report.md            # Complete 28-section academic project report
│   ├── problem_analysis.md        # Comprehensive problem domain analysis
│   ├── validation.md              # Stakeholder validation protocol & template
│   └── workflow.md                # Existing vs proposed operational workflows
├── src/
│   ├── api/
│   │   ├── main.py                # FastAPI entrypoint, CORS, lifespan
│   │   └── routes.py              # REST API endpoints
│   ├── collector/
│   │   ├── buffer.py              # Edge buffer for disconnection handling
│   │   ├── collector.py           # Ingestion, deduplication, ordering
│   │   └── validator.py           # Pydantic schema validation & bounds checking
│   ├── engine/
│   │   ├── baseline.py            # Traditional threshold monitor (control)
│   │   ├── localisation.py        # Explainable rule-based fault localisation
│   │   └── recorder.py            # Experience Recorder & evidence window manager
│   ├── experiments/
│   │   └── benchmark.py           # 100-scenario automated benchmark runner
│   ├── models/
│   │   ├── db.py                  # SQLAlchemy models (events, incidents, branches, etc.)
│   │   └── schemas.py             # Pydantic v2 data transfer schemas
│   └── simulator/
│       ├── branch_generator.py    # 50-branch deterministic topology generator
│       ├── branch_simulator.py    # Multi-source telemetry simulator
│       └── failure_scenarios.py   # WAN, Wi-Fi, App, Multiple failure injectors
├── tests/
│   ├── conftest.py                # Root test configuration & environment setup
│   ├── test_api.py                # FastAPI REST endpoint integration tests
│   ├── test_benchmark.py          # Benchmark suite & formula tests
│   ├── test_collector.py          # Validation, deduplication, ordering, recovery tests
│   ├── test_e2e.py                # Full end-to-end scenario integration test
│   ├── test_engine.py             # Baseline, localisation rules, lifecycle tests
│   ├── test_models.py             # Database models and schema tests
│   └── test_simulator.py          # Synthetic branches & failure injector tests
├── pytest.ini                     # Pytest path and execution configuration
├── requirements.txt               # Python package dependencies
├── run_experiments.py             # Standalone CLI runner for 100-incident benchmark
└── README.md                      # Primary project guide
```

---

## 5. Installation & Setup

### Step 1: Clone or Navigate to Directory
```powershell
cd c:\Users\Dhinesh\Desktop\COE_Project
```

### Step 2: Install Dependencies
```powershell
pip install -r requirements.txt
```

### Step 3: Run the PyTest Verification Suite
Run all 26 unit, integration, and end-to-end tests:
```powershell
python -m pytest
```
*Expected: 26 passed in ~3.8 seconds.*

---

## 6. How to Run the System

### Option A: Launch the Streamlit Interactive Dashboard
```powershell
python -m streamlit run dashboard/app.py
```
The dashboard will open automatically in your browser at `http://localhost:8501`.

#### Available Dashboard Views:
1. **🏢 Executive Overview**: High-level KPIs, branch health matrix, and live 1-click failure injector.
2. **📊 Branch Telemetry Deep-Dive**: Select any branch (B001 - B050) and view synchronized Plotly time-series for Active Probes, Wi-Fi RF, Application transactions, and User complaints.
3. **🔍 Incident Forensic Investigation**: Select any active or recovered incident and inspect the **Forensic Evidence Window** (2 min before + incident + 2 min after recovery).
4. **🛡️ Event Integrity & Resilience Lab**: Interactive buttons to inject duplicates, out-of-order packets, simulate collector network cuts, and recover buffers.
5. **🧪 Experiment Benchmark & Baseline**: Side-by-side comparison charts, 100-scenario metrics, and automated error analysis.

---

### Option B: Launch the FastAPI REST Backend
```powershell
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
```
Interactive OpenAPI documentation will be accessible at:
- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

#### Key API Endpoints:
- `GET /api/v1/health`: System status, event counts, buffer state.
- `GET /api/v1/branches`: List all 50 branches.
- `GET /api/v1/events`: Query raw telemetry with branch and source filters.
- `POST /api/v1/events`: Ingest single telemetry event (validation, deduplication).
- `GET /api/v1/incidents`: List all active and recovered incidents.
- `GET /api/v1/incidents/{incident_id}`: Retrieve full forensic evidence window timeline.
- `POST /api/v1/simulation/inject-failure`: Trigger a transient failure scenario on any branch.
- `POST /api/v1/buffer/simulate-outage`: Simulate collector network cut.
- `POST /api/v1/buffer/recover`: Flush and recover buffered edge events.
- `POST /api/v1/experiments/run`: Execute the 100-incident benchmark suite.
- `GET /api/v1/experiments/results`: Retrieve the benchmark report JSON.

---

### Option C: Run the 100-Incident Benchmark Suite (CLI)
```powershell
python run_experiments.py
```
This runs 100 injected failure scenarios (WAN, Wi-Fi, App, Multiple) plus 50 normal controls, computing real mathematical metrics and writing the report to `data/experiment_results.json`.

---

## 7. Experimental Results (100 Scenarios Tested)

*Empirically measured from `python run_experiments.py` (Random Seed: 42):*

```text
======================================================================
Metric                         | Baseline System  | Experience Recorder
----------------------------------------------------------------------
Detection Rate (%)             | 45.00%           | 100.00%
Miss Rate (%)                  | 55.00%           | 0.00%
Localisation Accuracy (%)      | 66.67%*          | 61.00%
False Positive Rate (%)        | 0.00%            | 0.00%
----------------------------------------------------------------------
Total Detected / Injected:     | 45 / 100         | 100 / 100
Correct Localisation:          | 30 / 45          | 61 / 100
False Positives on Controls:   | 0 / 50           | 0 / 50
Historical Evidence Window:    | Lost immediately | 100% Preserved
======================================================================
```
*\*Note: Baseline only detects WAN incidents where ping latency crosses 150ms. It completely missed 100% of Wi-Fi (30/30) and Application (25/25) degradations.*

---

## 8. Resilience to Hostile Telemetry

During testing, **9,049 events** were processed:
- **Duplicate Deliveries**: 25 detected $\to$ Idempotently discarded, **0 database corruptions**.
- **Out-of-Order Deliveries**: 100 detected $\to$ Successfully sorted by `event_time` to restore ground truth.
- **Delayed Deliveries**: 25 detected $\to$ Tagged and backfilled without false alert generation.
- **Link Interruption**: Edge buffer queued 100% of events and recovered them with zero data loss upon reconnection.

---

## 9. Faculty Review Demonstration Sequence

Follow this step-by-step sequence during your project evaluation:

1. **State the Problem (30s)**:
   - *"Sir/Ma'am, in financial branches, intermittent slowness occurs at 10:20 AM and clears by 10:22 AM. When an engineer investigates at 10:25 AM, everything looks normal, and the ticket is closed with 'No Issue Found.' Our system solves this by preserving historical evidence."*
2. **Show the 50 Branches (30s)**:
   - Open `http://localhost:8501`. Show the **Executive Overview** with 50 branches across different regions.
3. **Inject a Transient Failure (45s)**:
   - Under Quick Injection, select **Branch B007**, failure mode **WAN_DEGRADATION**, duration **90 seconds**, and click **🚀 Inject & Record Failure**.
   - Show how the incident is created, localized to **WAN degradation**, and assigned an incident ID.
4. **Demonstrate Evidence Window Preservation (45s)**:
   - Go to **Incident Forensic Investigation**. Select the B007 incident.
   - Point out the **Forensic Evidence Window**: Blue (normal 2 min before), Red (90s degradation), Green (normal 2 min after recovery).
   - *"The failure is gone right now, but the engineer has the full evidence!"*
5. **Show Hostile Delivery Resilience (30s)**:
   - Go to **Event Integrity & Resilience**.
   - Click **Ingest Duplicate Event** $\to$ show audit log displaying `DUPLICATE_REJECTED` and zero database corruption.
   - Click **Simulate Link Outage** $\to$ show events buffering at edge $\to$ click **Restore Connection** $\to$ show 100% recovery without loss.
6. **Show Benchmark Results (30s)**:
   - Go to **Experiment Benchmark & Baseline**.
   - Show the 100-scenario comparison: **Baseline missed 55% of failures, Experience Recorder detected 100%**.
