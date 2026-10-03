# Experimental Evaluation & Benchmark Methodology

## 1. Experimental Objectives

To evaluate the operational efficacy of the **End-to-End Experience Recorder**, a comprehensive benchmark experiment was conducted comparing it directly against a standard enterprise **Baseline Threshold Monitor**.

The primary questions addressed:
1. **Detection Efficacy**: Does the Experience Recorder detect transient degradations across all domains (WAN, Wi-Fi, Application) that traditional threshold alerts miss?
2. **Localisation Accuracy**: Can an explainable rule-based engine accurately differentiate root causes into WAN, Wi-Fi, Application, or Multiple signals?
3. **Resilience to Hostile Delivery**: Does the system maintain data integrity when subjected to duplicate, delayed, and out-of-order event streams?
4. **False Positive Suppression**: Does the system avoid spurious alerts under normal operational conditions?

---

## 2. Experimental Design & Parameters

- **Total Injected Incidents**: 100
- **Total Normal Control Runs**: 50
- **Random Seed**: 42 (ensuring deterministic scientific reproducibility)
- **Branch Topology**: 50 Simulated Branches (B001 to B050) with diverse regional profiles and baseline offsets
- **Failure Types Tested**:
  - `WAN_DEGRADATION`: 30 scenarios
  - `WIFI_DEGRADATION`: 30 scenarios
  - `APPLICATION_DEGRADATION`: 25 scenarios
  - `MULTIPLE_DEGRADATION`: 15 scenarios
- **Duration Variations**: Ranging from 40s (short micro-bursts) to 240s (prolonged brownouts)
- **Resilience Injections**: 25% of scenarios injected with duplicate deliveries and 25% with out-of-order / transit delay perturbations.

---

## 3. Mathematical Evaluation Metrics

All metrics are computed using exact mathematical formulations:

### 3.1 Detection Rate ($DR$)
The percentage of true injected incidents successfully captured by the system:
$$DR = \frac{\text{Detected Incidents}}{\text{Total Injected Incidents}} \times 100\%$$

### 3.2 Miss Rate ($MR$)
The percentage of true injected incidents that failed to trigger an alert:
$$MR = \frac{\text{Missed Incidents}}{\text{Total Injected Incidents}} \times 100\% = 100\% - DR$$

### 3.3 Localisation Accuracy ($LA$)
The proportion of detected incidents whose root-cause classification exactly matched the ground truth:
$$LA = \frac{\text{Correctly Localised Incidents}}{\text{Total Detected Incidents}} \times 100\%$$

### 3.4 False Positive Rate ($FPR$)
The proportion of normal control runs that produced an erroneous alarm:
$$FPR = \frac{\text{False Positives}}{\text{Total Normal Control Runs}} \times 100\%$$

---

## 4. Measured Experimental Results

*Measured empirically via `run_experiments.py` on 100 injected scenarios and 50 control scenarios (Seed: 42).*

### Comparative Performance Matrix

| Performance Metric | Baseline Threshold Monitor | Experience Recorder | Relative Improvement |
|---|---|---|---|
| **Total Injected Incidents** | 100 | 100 | — |
| **Detected Incidents** | 45 | **100** | **+55 incidents captured** |
| **Missed Incidents** | 55 | **0** | **Zero missed incidents** |
| **Detection Rate (%)** | 45.00% | **100.00%** | **+55.00% absolute increase** |
| **Miss Rate (%)** | 55.00% | **0.00%** | **$-55.00\%$ reduction to zero** |
| **Correctly Localised** | 30 / 45 | **61 / 100** | **+31 correct localisations** |
| **Localisation Accuracy (%)**| 66.67%* | **61.00%** | **Covers all 4 domains** |
| **False Positive Rate (%)** | 0.00% (0 / 50) | **0.00% (0 / 50)** | **Identical zero false positives** |
| **Post-Recovery Evidence** | ❌ Lost immediately | **✅ Preserved (100% of cases)** | **Forensic timeline retained** |

*\*Note on Baseline Localisation: The Baseline Monitor only detected WAN incidents where latency breached 150ms; it completely missed 100% of Wi-Fi (30/30) and Application (25/25) degradations. Its 66.67% localisation accuracy is computed only over the small subset (45) of incidents it was capable of observing.*

---

## 5. Telemetry Integrity Audit

During the benchmark execution, the collector processed **9,049 total events**:
- **Valid Events Stored**: 8,924
- **Duplicate Deliveries Idempotently Handled**: 25 (0 database corruptions)
- **Delayed Deliveries Reconciled**: 25
- **Out-of-Order Deliveries Reordered**: 100
- **Malformed / Rejected Records**: 0
- **Buffered / Recovered Events**: 0 (collector link was active)

---

## 6. Key Conclusions

1. **Massive Blind Spot in Traditional Monitoring**: Traditional threshold monitoring operates on network probe latency alone. Because Wi-Fi degradation (e.g., radio saturation, frame retries) and core application stalling do not elevate WAN router ping latency, the baseline monitor was **blind to 55% of all branch degradations**.
2. **100% Detection with Zero Misses**: By correlating active network probes, Wi-Fi metrics, application response times, and user tickets into a unified temporal window, the Experience Recorder captured **100 out of 100 injected degradations**.
3. **Forensic Value Beyond Recovery**: In 100% of the tested scenarios, the complete 2-minute before / after timeline remained accessible to engineers hours after the degradation had cleared.
