# Operational Workflow: Existing vs Proposed

## 1. Core Principle: Supplementary Evidence Layer

A fundamental design requirement of the **End-to-End Experience Recorder** is that **it must NOT replace existing helpdesk or monitoring workflows**. 

Financial organisations have established ITIL-compliant ticketing systems (e.g., ServiceNow, Jira Service Management) and existing NOC procedures. The Experience Recorder acts as a **specialized forensic evidence layer** that attaches objective telemetry to user tickets, removing guesswork.

---

## 2. Existing Workflow (Without Experience Recorder)

```text
+------------------------+
| User at Branch B007    |
| Experiences Slowness   |
+------------------------+
           |
           v (1-3 min delay)
+------------------------+
| User Reports to        |
| IT Helpdesk (Ticket)   |
+------------------------+
           |
           v (5-10 min delay)
+------------------------+
| Helpdesk Assigns to    |
| Network Engineer       |
+------------------------+
           |
           v
+------------------------+
| Engineer Investigates: |
| - Pings router         |
| - Checks SNMP graphs   |
+------------------------+
           |
           v
+------------------------+
| Transient Failure Has  |
| Already Recovered!     |
+------------------------+
           |
           v
+------------------------+
| Ticket Closed as:      |
| "Cannot Reproduce"     |
+------------------------+
```

### Critical Flaws in the Existing Workflow:
- Total reliance on real-time investigation for transient phenomena.
- No synchronized timeline correlating user complaints with network packet loss or application latency.
- Inability to verify user claims, leading to user dissatisfaction and unresolved link quality issues.

---

## 3. Proposed Workflow (With Experience Recorder)

```text
+------------------------+         +-------------------------------+
| User at Branch B007    |         | Experience Recorder           |
| Experiences Slowness   |         | Continuous Ingestion & Capture|
+------------------------+         +-------------------------------+
           |                                       |
           |                                       v
           |                        [Detects Transient Anomaly]
           |                        [Correlates Probe + Wi-Fi + App]
           |                        [Captures 2m Before + Incident + 2m After]
           |                        [Localises Fault to Domain]
           |                        [Preserves Incident State & Evidence]
           v (Ticket submitted)                    |
+------------------------+                         |
| IT Helpdesk Ticket:    |<------------------------+ (Incident ID Attached)
| "INC-B007-1020"        |
+------------------------+
           |
           v (5-10 min delay)
+------------------------+
| Network Engineer       |
| Opens Ticket           |
+------------------------+
           |
           v
+------------------------+
| Engineer Opens         |
| Experience Recorder    |
| Forensic Evidence      |
+------------------------+
           |
           v
+------------------------------------------------------------------------+
| Complete Evidence Available Even After Transient Recovery:             |
| - Exact start: 10:20:10 AM | End: 10:22:30 AM (Duration: 140s)         |
| - Localised Cause: WAN degradation (Loss 14%, Latency 320ms)           |
| - Wi-Fi was normal (RSSI -50dBm, Retry 2%), ruling out local AP        |
| - Application slowed due to WAN RTT (no server 5xx crash)              |
+------------------------------------------------------------------------+
           |
           v
+------------------------------------+
| Engineer Escalates to Telco / ISP  |
| with Definitive Evidence!          |
+------------------------------------+
```

---

## 4. Key Differences Summary

| Operational Factor | Existing Helpdesk Workflow | Proposed Experience Recorder Workflow |
|---|---|---|
| **Evidence Window** | Zero (instantaneous observation only) | Full timeline (2 min before + incident + 2 min after) |
| **Persistence** | Disappears as soon as failure clears | Persists permanently with status `RECOVERED` |
| **Fault Localisation** | Manual guessing between teams | Automated explainable rule-based decision tree |
| **Cross-Source Corroboration** | Siloed probe, Wi-Fi, and app data | Unified correlation by branch and time window |
| **Helpdesk Impact** | Leaves tickets unresolved ("Cannot Reproduce") | Empowers engineers with objective, incontrovertible proof |
