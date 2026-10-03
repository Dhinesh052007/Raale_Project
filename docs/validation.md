# Stakeholder Validation Protocol & Evaluation Template

## 1. Stakeholder Validation Overview

To validate that the **End-to-End Experience Recorder** fulfills the operational requirements of financial network teams, a structured stakeholder evaluation protocol was established.

### Target Evaluator Personas:
- **L2 / L3 Network Support Engineer**: Responsible for diagnosing WAN, routing, and router link faults.
- **IT Helpdesk Operations Lead**: Responsible for reviewing branch complaints and routing tickets to infrastructure teams.
- **Financial Branch IT Coordinator**: Responsible for counter terminal uptime and teller experience.

---

## 2. Validation Scenario: "The 10:20 AM Mystery at Branch B007"

### Scenario Briefing Given to Participant:
> *"At 10:21 AM, a branch teller at **Branch B007** filed a high-priority ticket reporting that customer transactions were freezing and timing out. The ticket was assigned to you at 10:28 AM. By the time you opened the monitoring dashboard, all current branch pings returned normal 35ms latency.*
> 
> *Use the **Experience Recorder** system to investigate what occurred."*

### Participant Tasks:
1. Locate the affected branch and determine if an incident occurred around 10:20 AM.
2. Determine the exact **start time**, **end time**, and **duration** of the service degradation.
3. Determine the **probable fault domain** (WAN, Wi-Fi, Application, or Multiple).
4. Identify the **supporting evidence** that justifies or refutes the finding.
5. Determine whether the local branch Wi-Fi access point should be rebooted or if the ticket should be escalated to the WAN service provider.

---

## 3. Ground Truth Reference (System Reality)

- **Target Branch**: B007 (Metropolitan Capital Zone)
- **Degradation Type**: `WAN_DEGRADATION`
- **Onset Time**: 10:20:10 AM
- **Recovery Time**: 10:22:30 AM (Duration: 140s)
- **Observed Metrics**:
  - Peak Latency: $340.2\text{ ms}$ (Normal baseline: $42\text{ ms}$)
  - Packet Loss: $15.8\%$ (Normal baseline: $0\%$)
  - Wi-Fi RSSI: $-51.5\text{ dBm}$ (Completely healthy)
  - Wi-Fi Retry Rate: $1.8\%$ (Completely healthy)
  - Application Response: $2,850\text{ ms}$ (Collateral TCP latency)
- **Correct Conclusion**: Escalate to WAN ISP / Telco with proof of 15.8% packet loss; do NOT reboot local Wi-Fi.

---

## 4. Stakeholder Feedback Recording Template

*(Use this template when conducting live demonstrations and evaluations with faculty or technical stakeholders.)*

```text
======================================================================
STAKEHOLDER EVALUATION FORM — EXPERIENCE RECORDER
======================================================================
Participant Name: _____________________________________________
Role / Title:     _____________________________________________
Organisation:     _____________________________________________
Date & Time:      _____________________________________________

PART A: TASK COMPLETION
----------------------------------------------------------------------
Task 1: Located affected branch & incident?
[ ] Completed Successfully    [ ] Partially Completed    [ ] Failed
Recorded Incident ID: _________________________________________

Task 2: Correctly identified start time, end time, and duration?
Start Time: __________________  End Time: ____________________
Duration:   __________________
[ ] Accurate within 15 seconds [ ] Inaccurate

Task 3: Correctly identified fault domain?
Identified Domain: [ ] WAN  [ ] Wi-Fi  [ ] Application  [ ] Multiple
[ ] Matched Ground Truth      [ ] Misdiagnosed

Task 4: Able to articulate supporting evidence?
Observed Peak Latency:     _________ ms
Observed Packet Loss:      _________ %
Observed Wi-Fi Health:     ____________________________________
Was Wi-Fi ruled out?       [ ] Yes  [ ] No

PART B: SYSTEM USABILITY & OPERATIONAL VALUE (Scale 1 to 5)
1 = Strongly Disagree | 3 = Neutral | 5 = Strongly Agree
----------------------------------------------------------------------
1. The 2-minute pre/post evidence window provides critical context:
   [ 1 ]   [ 2 ]   [ 3 ]   [ 4 ]   [ 5 ]

2. The explainable localisation prevents guessing between teams:
   [ 1 ]   [ 2 ]   [ 3 ]   [ 4 ]   [ 5 ]

3. The system would reduce "Cannot Reproduce" ticket closures:
   [ 1 ]   [ 2 ]   [ 3 ]   [ 4 ]   [ 5 ]

4. The dashboard interface is intuitive for support engineers:
   [ 1 ]   [ 2 ]   [ 3 ]   [ 4 ]   [ 5 ]

5. Overall operational value for branch-based organisations:
   [ 1 ]   [ 2 ]   [ 3 ]   [ 4 ]   [ 5 ]

PART C: QUALITATIVE FEEDBACK & COMMENTS
----------------------------------------------------------------------
What was the most useful feature during investigation?
______________________________________________________________________
______________________________________________________________________

What suggestions do you have for future enhancement?
______________________________________________________________________
______________________________________________________________________

Signature of Evaluator: ______________________ Date: _________________
======================================================================
```
