# In-Depth Problem Analysis

## 1. Context: Branch-Based Financial Organisations

Modern commercial banking and financial organisations operate extensive distributed networks spanning hundreds or thousands of retail branches. Each branch relies on continuous WAN connectivity to connect teller workstations, loan processing portals, customer service desks, and ATM controllers back to centralized core banking platforms and cloud-hosted microservices.

A standard branch topology typically comprises:
- **WAN Edge**: Primary MPLS circuit or dual-homed SD-WAN appliances with cellular (4G/5G) or broadband backup.
- **LAN / Wi-Fi Access**: Local access points (APs) servicing teller laptops, administrative terminals, tablets, and customer Wi-Fi.
- **Critical Applications**: Core transaction processing, CRM, KYC verification, DNS resolution, and document retrieval.

---

## 2. The Intermittent Degradation Dilemma

In enterprise operations, permanent failures (such as a physical fiber cut or hard power outage) are relatively straightforward to detect: SNMP traps fire, interface states transition to `DOWN`, and network operations center (NOC) dashboards turn red immediately.

In contrast, the most disruptive and expensive operational challenge is **intermittent service degradation** (frequently termed "gray failures", "transient brownouts", or "micro-burst degradations"). 

### Typical Incident Progression:

```text
10:20:00 AM — Sudden micro-burst congestion on branch WAN circuit (packet loss 14%, latency jumps to 320ms).
10:20:30 AM — Teller terminal transactions begin timing out (HTTP 504 / high latency).
10:21:00 AM — Branch teller reports application slowness to the central IT helpdesk.
10:22:15 AM — Network micro-burst clears; WAN buffer queues drain; latency returns to 40ms.
10:25:00 AM — Network support engineer picks up the helpdesk ticket and logs in.
10:25:30 AM — Engineer pings the branch router and tests app latency: EVERYTHING APPEARS COMPLETELY NORMAL.
```

### Consequences:
1. **False "No Issue Found" Resolution**: The engineer closes the ticket as "unable to reproduce" or "transient user glitch."
2. **Intermittent Recurrence**: The issue recurs multiple times per day or week, causing teller frustration, customer queues at bank counters, and reputational damage.
3. **Finger-Pointing Between Teams**: 
   - Network engineering blames the application / database team.
   - Application engineering blames branch Wi-Fi signal.
   - Branch staff lose confidence in central IT monitoring.

---

## 3. Why Existing Monitoring Approaches Fail

### Traditional Network Monitoring (SNMP / Polling)
- **Coarse Polling Intervals**: Standard SNMP poll cycles occur every 3 to 5 minutes. An intermittent degradation lasting 60 to 90 seconds often falls entirely between two polling cycles.
- **Average vs Peak Distortion**: 5-minute averages smooth out micro-burst spikes, making a severe 45-second latency surge look like a minor 2ms variance in historical graphs.

### Baseline Threshold Alerting
- Threshold alarms (e.g. `latency > 150ms`) trigger stateless alerts. Once the metric drops back to 40ms, the alert auto-clears.
- When the support engineer opens the dashboard 5 minutes later, no active alarm exists, and zero pre/post historical forensic context is preserved.

### Siloed Domain Telemetry
- Network probes, Wi-Fi controllers, and application APM tools operate in separate silos.
- Traditional systems lack automated cross-source correlation to determine whether an application timeout was caused by a WAN link drop, Wi-Fi channel saturation, or backend database lock.

---

## 4. The Experience Recorder Solution

The **End-to-End Experience Recorder** solves this systemic problem by acting as an **additional forensic evidence layer**:

1. **High-Frequency Multi-Modal Capture**: Continuously records telemetry from active probes, Wi-Fi infrastructure, core applications, and user tickets.
2. **Incident Preservation Beyond Recovery**: When degradation occurs, the system records it as a durable incident object that persists **permanently**, even after the live network returns to normal.
3. **Forensic Evidence Window**: Automatically packages:
   $$\text{Evidence Window} = [t_{\text{start}} - 2\text{ min}] \cup [t_{\text{start}}, t_{\text{end}}] \cup [t_{\text{end}} + 2\text{ min}]$$
   Engineers can examine the exact state *before* the issue arose, *during* the failure, and *after* recovery.
4. **Explainable Fault Localisation**: Rule-based decision logic pinpoints whether the root cause was WAN degradation, Wi-Fi interference, application server stalling, or multiple simultaneous anomalies.
