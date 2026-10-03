# Three-Minute Demonstration Script

## Overview
This script is specifically structured for a tight, high-impact **3-minute project review or faculty demonstration** (180 seconds total). Every segment has precise time markers, visual actions to perform on screen, and the exact spoken dialogue.

---

## ⏱️ Timeline Breakdown

```text
[0:00 - 0:30] The Problem: The Transient Degradation Dilemma
[0:30 - 1:00] Architecture & Solution Concept
[1:00 - 1:30] Normal Operations (50 Branch Infrastructure)
[1:30 - 2:00] Live Failure Injection: WAN Degradation on B007
[2:00 - 2:20] Capture, Correlation & Localisation in Action
[2:20 - 2:45] Telemetry Resilience (Duplicates, Ordering & Buffer)
[2:45 - 3:00] Experimental Benchmark (Baseline vs Recorder) & Conclusion
```

---

## 🎬 Minute-by-Minute Script

### 0:00 – 0:30 | The Problem
- **Screen Action**: Show slide or open **Overview** tab on Streamlit dashboard.
- **Spoken Dialogue**:
  > *"Good morning. In financial institutions with hundreds of branches, the most frustrating network issue is intermittent service degradation. At 10:20 AM, a teller experiences severe application freezes. By 10:25 AM when the network engineer investigates, the network has already recovered and everything looks completely normal. The engineer has zero historical evidence and closes the ticket as 'Unable to Reproduce.' We built the End-to-End Experience Recorder to solve this exact problem."*

### 0:30 – 1:00 | Architecture & Solution
- **Screen Action**: Point to the architecture flow in docs or the sidebar status badges.
- **Spoken Dialogue**:
  > *"Our system does not replace the existing helpdesk—it acts as an additional forensic evidence layer. It continuously collects telemetry from four sources: active network probes, Wi-Fi infrastructure metrics, application monitors, and user complaint tickets. When a transient degradation strikes, the system detects it, correlates multi-modal signals, localises the probable root cause, and permanently preserves a forensic evidence window containing 2 minutes before the failure, the incident duration, and 2 minutes after recovery."*

### 1:00 – 1:30 | Normal Operations
- **Screen Action**: Switch to **Branch Deep-Dive** tab. Select Branch **B007**.
- **Spoken Dialogue**:
  > *"Here we see Branch B007 operating under normal conditions. Notice the natural variation across all three domains: active probe latency is healthy around 40ms with 0% packet loss; Wi-Fi RSSI is strong at -50 dBm with low retry rates; and application response time is steady at 250ms. All 50 branches in our simulated topology are operating normally."*

### 1:30 – 2:00 | Live Failure Injection
- **Screen Action**: Switch to **Executive Overview**. Under 'Quick Intermittent Degradation Injection', select **B007**, failure mode **WAN_DEGRADATION**, duration **90 seconds**, and click **🚀 Inject & Record Failure**.
- **Spoken Dialogue**:
  > *"Now, let's inject a realistic 90-second WAN degradation into Branch B007. Watch what happens: network latency surges past 300ms, packet loss climbs to 15%, and application transactions slow down. However, notice that Wi-Fi metrics remain completely healthy. Simultaneously, an automated teller user ticket is logged at the counter."*

### 2:00 – 2:20 | Capture & Forensic Evidence Window
- **Screen Action**: Switch to **Incident Forensic Investigation** tab. Select the newly recorded incident on **B007**.
- **Spoken Dialogue**:
  > *"The degradation has already cleared from the live network, but look at the Experience Recorder! The incident was captured, assigned ID INC-..., and localized to 'WAN degradation' with high confidence. Even though the live link is normal right now, the engineer has access to the full Forensic Evidence Window: blue shows normal operation 2 minutes before, red highlights the 90-second failure window, and green proves full recovery. The engineer can confidently escalate to the WAN telecom provider without guessing."*

### 2:20 – 2:45 | Telemetry Resilience & Failure-State Lab
- **Screen Action**: Switch to **Event Integrity & Resilience** tab. Click **Ingest Duplicate Event**, then **Simulate Link Outage**, then **Restore Connection**.
- **Spoken Dialogue**:
  > *"Enterprise telemetry is hostile. Here we demonstrate our resilience layer: when duplicate events arrive, our collector enforces idempotency and rejects duplicates without corrupting the database. When out-of-order packets arrive, we reconstruct the chronological timeline using source timestamps. And when the collector connection drops, events queue into our edge buffer and recover with zero data loss once reconnected."*

### 2:45 – 3:00 | Experimental Benchmark & Conclusion
- **Screen Action**: Switch to **Experiment Benchmark & Baseline** tab. Show the side-by-side comparison charts and error analysis.
- **Spoken Dialogue**:
  > *"We tested our system against an enterprise Baseline Monitor across 100 injected incidents. The traditional baseline missed 55% of all degradations because it is blind to Wi-Fi and application failures. Our Experience Recorder achieved a 100% detection rate, distinguished root causes across all domains, and generated honest error analysis on short-duration boundary cases. This is a complete, working, resilient software system. Thank you."*
