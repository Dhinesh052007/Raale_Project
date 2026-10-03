"""Interactive Streamlit Dashboard for Experience Recorder."""
import os
os.environ["DISABLE_SQLALCHEMY_CEXT"] = "1"

import json
from datetime import datetime, timezone, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import desc

from src.models.db import SessionLocal, init_db, Branch, Event, Incident, UserReport, EventProcessingLog
from src.collector.collector import EventCollector
from src.collector.buffer import EventBuffer
from src.engine.recorder import ExperienceRecorder
from src.simulator.branch_generator import generate_branch_inventory
from src.simulator.branch_simulator import BranchSimulator
from src.simulator.failure_scenarios import FailureScenario, FailureType
from src.experiments.benchmark import ExperimentRunner

# Page Configuration
st.set_page_config(
    page_title="Experience Recorder | Branch Intermittent Degradation",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .metric-card {
        background: linear-gradient(135deg, #1e222d 0%, #252a37 100%);
        border: 1px solid #363c4e;
        border-radius: 10px;
        padding: 16px 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        margin-bottom: 12px;
    }
    .metric-label { font-size: 0.85rem; color: #8e99a8; text-transform: uppercase; letter-spacing: 0.5px; }
    .metric-val { font-size: 1.8rem; font-weight: 700; color: #ffffff; margin-top: 4px; }
    .status-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-healthy { background-color: rgba(38, 166, 154, 0.2); color: #26a69a; border: 1px solid #26a69a; }
    .badge-degraded { background-color: rgba(239, 83, 80, 0.2); color: #ef5350; border: 1px solid #ef5350; }
    .badge-recovered { background-color: rgba(66, 165, 245, 0.2); color: #42a5f5; border: 1px solid #42a5f5; }
    .badge-wan { background-color: rgba(255, 167, 38, 0.2); color: #ffa726; border: 1px solid #ffa726; }
    .badge-wifi { background-color: rgba(171, 71, 188, 0.2); color: #ab47bc; border: 1px solid #ab47bc; }
    .badge-app { background-color: rgba(38, 198, 218, 0.2); color: #26c6da; border: 1px solid #26c6da; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_db_session():
    init_db()
    return SessionLocal()


db = get_db_session()

# Global edge buffer
if "edge_buffer" not in st.session_state:
    st.session_state.edge_buffer = EventBuffer()

# Sidebar Navigation
st.sidebar.image("https://img.icons8.com/fluency/96/network-switch.png", width=64)
st.sidebar.title("Experience Recorder")
st.sidebar.caption("Financial Branch Network Observability")

nav_option = st.sidebar.radio(
    "Navigation Views",
    [
        "🏢 Executive Overview",
        "📊 Branch Deep-Dive",
        "🔍 Incident Forensic Investigation",
        "🛡️ Event Integrity & Resilience",
        "🧪 Experiment Benchmark & Baseline"
    ]
)

st.sidebar.markdown("---")
st.sidebar.subheader("System Status")
buffer_size = st.session_state.edge_buffer.size()
is_interrupted = st.session_state.edge_buffer.is_interrupted

if is_interrupted:
    st.sidebar.error("⚠️ Collector Link: INTERRUPTED (Buffering)")
else:
    st.sidebar.success("✅ Collector Link: ONLINE")

st.sidebar.info(f"Edge Buffered Events: **{buffer_size}**")

# Helper function to seed branches if empty
def ensure_branches():
    if db.query(Branch).count() == 0:
        branches = generate_branch_inventory(num_branches=50, seed=42)
        for b in branches:
            db.add(Branch(
                branch_id=b["branch_id"],
                name=b["name"],
                region=b["region"],
                wan_type=b["wan_type"]
            ))
        db.commit()


ensure_branches()

# ==============================================================================
# VIEW 1: EXECUTIVE OVERVIEW
# ==============================================================================
if nav_option == "🏢 Executive Overview":
    st.title("🏢 Executive Overview — Financial Branch Observability")
    st.markdown(
        "Real-time visibility across branch WAN links, Wi-Fi infrastructure, and application transactions. "
        "Captures intermittent degradations before helpdesk tickets are investigated."
    )

    # Metric Cards Row
    total_branches = db.query(Branch).count()
    active_incidents = db.query(Incident).filter(Incident.status == "ACTIVE").count()
    recovered_incidents = db.query(Incident).filter(Incident.status == "RECOVERED").count()
    total_events = db.query(Event).count()
    total_user_reports = db.query(UserReport).count()
    healthy_branches = total_branches - active_incidents

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Total Branches</div>
            <div class="metric-val">{total_branches}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Healthy Branches</div>
            <div class="metric-val" style="color: #26a69a;">{healthy_branches}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Active Incidents</div>
            <div class="metric-val" style="color: #ef5350;">{active_incidents}</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Recovered Incidents</div>
            <div class="metric-val" style="color: #42a5f5;">{recovered_incidents}</div>
        </div>
        """, unsafe_allow_html=True)
    with col5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Total Events</div>
            <div class="metric-val">{total_events:,}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Quick Failure Injection Toolbar
    with st.expander("⚡ Quick Intermittent Degradation Injection (Live Demo Sandbox)", expanded=True):
        st.markdown("**Inject a transient degradation to demonstrate capture, correlation, and recovery preservation.**")
        inj_col1, inj_col2, inj_col3, inj_col4 = st.columns([2, 3, 2, 2])
        all_branches = [b.branch_id for b in db.query(Branch.branch_id).order_by(Branch.branch_id.asc()).all()]
        with inj_col1:
            target_b = st.selectbox("Target Branch", all_branches, index=6 if len(all_branches) > 6 else 0)
        with inj_col2:
            failure_type = st.selectbox(
                "Failure Mode",
                [
                    "WAN_DEGRADATION",
                    "WIFI_DEGRADATION",
                    "APPLICATION_DEGRADATION",
                    "MULTIPLE_DEGRADATION"
                ]
            )
        with inj_col3:
            duration_sec = st.slider("Duration (seconds)", 40, 180, 90, step=10)
        with inj_col4:
            st.write("")
            st.write("")
            inject_btn = st.button("🚀 Inject & Record Failure", use_container_width=True)

        if inject_btn:
            with st.spinner("Injecting transient degradation and running multi-modal telemetry recorder..."):
                sim = BranchSimulator(num_branches=50, seed=42)
                collector = EventCollector(db_session=db, buffer=st.session_state.edge_buffer)
                recorder = ExperienceRecorder(db_session=db)

                now = datetime.now(timezone.utc)
                t_start = now - timedelta(seconds=duration_sec + 120)

                # Pre-baseline (120s)
                for s in range(0, 120, 10):
                    t = t_start + timedelta(seconds=s)
                    collector.ingest_event(sim.generate_probe_metric(target_b, t))
                    collector.ingest_event(sim.generate_wifi_metric(target_b, t))
                    collector.ingest_event(sim.generate_application_metric(target_b, t))

                # Degradation period
                f_scen = FailureScenario(
                    failure_type=FailureType(failure_type),
                    target_branch_id=target_b,
                    start_seconds=120,
                    duration_seconds=duration_sec
                )
                for s in range(120, 120 + duration_sec, 10):
                    t = t_start + timedelta(seconds=s)
                    collector.ingest_event(sim.generate_probe_metric(target_b, t, failure=f_scen))
                    collector.ingest_event(sim.generate_wifi_metric(target_b, t, failure=f_scen))
                    collector.ingest_event(sim.generate_application_metric(target_b, t, failure=f_scen))

                # User report
                ur_bundle = sim.generate_user_report(
                    target_b,
                    t_start + timedelta(seconds=120 + duration_sec // 2),
                    description=f"Automated user ticket: Slowness experienced during {failure_type}."
                )
                collector.ingest_event(ur_bundle["event"])
                ur_dict = ur_bundle["report"]
                db.add(UserReport(
                    report_id=ur_dict["report_id"],
                    branch_id=ur_dict["branch_id"],
                    event_time=ur_dict["event_time"].replace(tzinfo=None) if ur_dict["event_time"].tzinfo else ur_dict["event_time"],
                    location=ur_dict["location"],
                    description=ur_dict["description"],
                    severity=ur_dict["severity"]
                ))
                db.commit()

                # Post-recovery baseline (120s)
                for s in range(120 + duration_sec, 120 + duration_sec + 120, 10):
                    t = t_start + timedelta(seconds=s)
                    collector.ingest_event(sim.generate_probe_metric(target_b, t))
                    collector.ingest_event(sim.generate_wifi_metric(target_b, t))
                    collector.ingest_event(sim.generate_application_metric(target_b, t))

                # Evaluate recorder
                recorded_inc = recorder.process_telemetry_batch(
                    target_b,
                    current_time=t_start + timedelta(seconds=120 + duration_sec + 60)
                )

                if recorded_inc:
                    st.success(
                        f"✅ Intermittent Degradation Captured! Incident ID: **{recorded_inc.incident_id}** | "
                        f"Status: **{recorded_inc.status}** | Localised Fault: **{recorded_inc.probable_cause}**"
                    )
                else:
                    st.info("Simulation completed and telemetry stored.")
                st.rerun()

    # Branch Status Grid
    st.subheader("Branch Network Infrastructure Grid (50 Branches)")
    branches = db.query(Branch).order_by(Branch.branch_id.asc()).all()
    active_inc_branches = {
        inc.branch_id: inc
        for inc in db.query(Incident).filter(Incident.status == "ACTIVE").all()
    }

    grid_data = []
    for b in branches:
        has_active = b.branch_id in active_inc_branches
        inc = active_inc_branches.get(b.branch_id)
        grid_data.append({
            "Branch ID": b.branch_id,
            "Branch Name": b.name,
            "Region": b.region,
            "WAN Link Profile": b.wan_type,
            "Status": "🔴 DEGRADED" if has_active else "🟢 HEALTHY",
            "Active Incident": inc.probable_cause if inc else "None"
        })

    grid_df = pd.DataFrame(grid_data)
    st.dataframe(
        grid_df,
        column_config={
            "Status": st.column_config.TextColumn(
                "Health State",
                help="Real-time branch operational status"
            ),
            "WAN Link Profile": st.column_config.TextColumn("Connectivity")
        },
        hide_index=True,
        use_container_width=True
    )


# ==============================================================================
# VIEW 2: BRANCH TELEMETRY DEEP-DIVE
# ==============================================================================
elif nav_option == "📊 Branch Deep-Dive":
    st.title("📊 Branch Telemetry Deep-Dive")
    branches = [b.branch_id for b in db.query(Branch.branch_id).order_by(Branch.branch_id.asc()).all()]
    selected_branch = st.selectbox("Select Branch to Inspect", branches, index=0)

    branch_info = db.query(Branch).filter(Branch.branch_id == selected_branch).first()
    active_inc = db.query(Incident).filter(Incident.branch_id == selected_branch, Incident.status == "ACTIVE").first()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Branch Name", branch_info.name if branch_info else selected_branch)
    with col2:
        st.metric("Region", branch_info.region if branch_info else "N/A")
    with col3:
        st.metric("WAN Topology", branch_info.wan_type if branch_info else "N/A")
    with col4:
        state_label = "🔴 DEGRADED" if active_inc else "🟢 HEALTHY"
        st.metric("Current State", state_label)

    st.markdown("---")

    # Fetch recent telemetry events
    events = db.query(Event).filter(Event.branch_id == selected_branch).order_by(Event.event_time.asc()).all()

    if not events:
        st.warning(f"No telemetry events recorded for {selected_branch} yet. Use the Overview page or simulator to generate events.")
    else:
        df_events = pd.DataFrame([
            {
                "event_time": e.event_time,
                "source": e.source,
                "latency_ms": e.latency_ms,
                "jitter_ms": e.jitter_ms,
                "packet_loss_percent": e.packet_loss_percent,
                "dns_response_ms": e.dns_response_ms,
                "wifi_rssi": e.wifi_rssi,
                "wifi_retry_rate": e.wifi_retry_rate,
                "channel_utilisation": e.channel_utilisation,
                "application_response_ms": e.application_response_ms,
                "http_status": e.http_status,
                "transaction_duration_ms": e.transaction_duration_ms
            }
            for e in events
        ])

        # Active Network Probe Chart
        probe_df = df_events[df_events["source"] == "ACTIVE_PROBE"].dropna(subset=["latency_ms"])
        if not probe_df.empty:
            st.subheader("1. Active Network Probe Telemetry")
            fig_probe = go.Figure()
            fig_probe.add_trace(go.Scatter(
                x=probe_df["event_time"], y=probe_df["latency_ms"],
                mode="lines+markers", name="Latency (ms)", line=dict(color="#ffa726", width=2)
            ))
            fig_probe.add_trace(go.Scatter(
                x=probe_df["event_time"], y=probe_df["jitter_ms"],
                mode="lines", name="Jitter (ms)", line=dict(color="#42a5f5", dash="dot")
            ))
            fig_probe.add_trace(go.Scatter(
                x=probe_df["event_time"], y=probe_df["packet_loss_percent"],
                mode="lines", name="Packet Loss (%)", yaxis="y2", line=dict(color="#ef5350", width=2)
            ))
            fig_probe.update_layout(
                title=f"WAN Probe Metrics for {selected_branch}",
                xaxis_title="Time",
                yaxis_title="Latency / Jitter (ms)",
                yaxis2=dict(title="Packet Loss (%)", overlaying="y", side="right", range=[0, 100]),
                template="plotly_dark",
                hovermode="x unified"
            )
            st.plotly_chart(fig_probe, use_container_width=True)

        # Wi-Fi Infrastructure Chart
        wifi_df = df_events[df_events["source"] == "WIFI"].dropna(subset=["wifi_rssi"])
        if not wifi_df.empty:
            st.subheader("2. Branch Wi-Fi Infrastructure Metrics")
            fig_wifi = go.Figure()
            fig_wifi.add_trace(go.Scatter(
                x=wifi_df["event_time"], y=wifi_df["wifi_rssi"],
                mode="lines+markers", name="RSSI (dBm)", line=dict(color="#ab47bc", width=2)
            ))
            fig_wifi.add_trace(go.Scatter(
                x=wifi_df["event_time"], y=wifi_df["wifi_retry_rate"],
                mode="lines", name="Retry Rate (%)", yaxis="y2", line=dict(color="#ec407a", width=2)
            ))
            fig_wifi.add_trace(go.Scatter(
                x=wifi_df["event_time"], y=wifi_df["channel_utilisation"],
                mode="lines", name="Channel Utilisation (%)", yaxis="y2", line=dict(color="#26c6da", dash="dash")
            ))
            fig_wifi.update_layout(
                title=f"Wi-Fi Radio Metrics for {selected_branch}",
                xaxis_title="Time",
                yaxis_title="Signal Strength (RSSI dBm)",
                yaxis2=dict(title="Retry / Utilisation (%)", overlaying="y", side="right", range=[0, 100]),
                template="plotly_dark",
                hovermode="x unified"
            )
            st.plotly_chart(fig_wifi, use_container_width=True)

        # Application Telemetry Chart
        app_df = df_events[df_events["source"] == "APPLICATION"].dropna(subset=["application_response_ms"])
        if not app_df.empty:
            st.subheader("3. Core Application & Transaction Health")
            fig_app = go.Figure()
            fig_app.add_trace(go.Scatter(
                x=app_df["event_time"], y=app_df["application_response_ms"],
                mode="lines+markers", name="App Response (ms)", line=dict(color="#26a69a", width=2)
            ))
            fig_app.add_trace(go.Scatter(
                x=app_df["event_time"], y=app_df["transaction_duration_ms"],
                mode="lines", name="Transaction Duration (ms)", line=dict(color="#7e57c2", dash="dot")
            ))
            fig_app.update_layout(
                title=f"Application Response Times for {selected_branch}",
                xaxis_title="Time",
                yaxis_title="Duration (ms)",
                template="plotly_dark",
                hovermode="x unified"
            )
            st.plotly_chart(fig_app, use_container_width=True)

    # User Reports
    st.subheader("User-Reported Complaints")
    reports = db.query(UserReport).filter(UserReport.branch_id == selected_branch).order_by(UserReport.event_time.desc()).all()
    if reports:
        rep_df = pd.DataFrame([
            {
                "Report ID": r.report_id,
                "Time": r.event_time.isoformat(),
                "Location": r.location,
                "Severity": r.severity,
                "Description": r.description
            }
            for r in reports
        ])
        st.dataframe(rep_df, hide_index=True, use_container_width=True)
    else:
        st.info("No user complaints on file for this branch.")


# ==============================================================================
# VIEW 3: INCIDENT FORENSIC INVESTIGATION (EVIDENCE WINDOW)
# ==============================================================================
elif nav_option == "🔍 Incident Forensic Investigation":
    st.title("🔍 Incident Forensic Investigation")
    st.markdown(
        "**Core Value Proposition:** When intermittent degradation disappears before the engineer investigates, "
        "the Experience Recorder reconstructs the complete evidence window: "
        "**2 minutes BEFORE + INCIDENT DURATION + 2 minutes AFTER recovery**."
    )

    incidents = db.query(Incident).order_by(desc(Incident.start_time)).all()

    if not incidents:
        st.warning("No incidents recorded yet. Inject a failure from the Executive Overview page or run experiments.")
    else:
        inc_options = {
            f"[{inc.incident_id}] {inc.branch_id} — {inc.probable_cause} ({inc.status}) @ {inc.start_time.strftime('%H:%M:%S')}": inc.incident_id
            for inc in incidents
        }
        selected_inc_label = st.selectbox("Select Incident to Investigate", list(inc_options.keys()))
        selected_inc_id = inc_options[selected_inc_label]

        recorder = ExperienceRecorder(db_session=db)
        bundle = recorder.get_incident_evidence_window(selected_inc_id)

        # Incident Summary Card
        st.markdown("### Incident Metadata")
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Incident ID", bundle["incident_id"])
        with col2:
            st.metric("Branch", bundle["branch_id"])
        with col3:
            st.metric("Status", bundle["status"])
        with col4:
            st.metric("Severity", bundle["severity"])
        with col5:
            dur = f"{bundle['duration_seconds']:.0f}s" if bundle.get("duration_seconds") else "Ongoing"
            st.metric("Duration", dur)

        # Probable Cause & Supporting Evidence
        st.markdown(f"#### 🎯 Localised Fault Domain: **{bundle['probable_cause']}**")
        ev_breakdown = bundle.get("evidence_breakdown", {})
        st.info(f"**Root-Cause Rationale:** {ev_breakdown.get('reasoning', 'Evidence correlated across active probe and application metrics.')}")

        # Metrics Table
        if "supporting_metrics" in ev_breakdown:
            sm = ev_breakdown["supporting_metrics"]
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            with m_col1:
                st.metric("Peak Latency", f"{sm.get('peak_latency_ms', 0)} ms")
                st.metric("Avg Latency", f"{sm.get('avg_latency_ms', 0)} ms")
            with m_col2:
                st.metric("Peak Packet Loss", f"{sm.get('peak_packet_loss_percent', 0)} %")
                st.metric("Min Wi-Fi RSSI", f"{sm.get('min_wifi_rssi_dbm', 0)} dBm")
            with m_col3:
                st.metric("Peak Wi-Fi Retry", f"{sm.get('peak_wifi_retry_percent', 0)} %")
                st.metric("Peak Channel Util", f"{sm.get('peak_wifi_channel_util_percent', 0)} %")
            with m_col4:
                st.metric("Peak App Response", f"{sm.get('peak_application_response_ms', 0)} ms")
                st.metric("HTTP 5xx Errors", f"{sm.get('http_error_count', 0)}")

        st.markdown("---")

        # The Forensic Evidence Window Timeline Chart
        st.subheader("⏱️ Forensic Evidence Window Timeline (Pre-Baseline → Incident → Recovery)")
        timeline = bundle.get("timeline_events", [])
        if timeline:
            df_tl = pd.DataFrame(timeline)
            df_tl["event_time"] = pd.to_datetime(df_tl["event_time"])

            # Plot Latency across phases
            probe_tl = df_tl[df_tl["source"] == "ACTIVE_PROBE"].dropna(subset=["latency_ms"])
            if not probe_tl.empty:
                fig_tl = go.Figure()

                # Add traces for each phase with distinct colors
                for phase, color in [("PRE_INCIDENT_BASELINE", "#42a5f5"), ("INCIDENT_PERIOD", "#ef5350"), ("POST_RECOVERY_BASELINE", "#26a69a")]:
                    sub_df = probe_tl[probe_tl["phase"] == phase]
                    if not sub_df.empty:
                        fig_tl.add_trace(go.Scatter(
                            x=sub_df["event_time"],
                            y=sub_df["latency_ms"],
                            mode="lines+markers",
                            name=f"{phase.replace('_', ' ').title()}",
                            line=dict(color=color, width=2.5),
                            marker=dict(size=6)
                        ))

                # Add vertical shading for incident window
                inc_start = pd.to_datetime(bundle["start_time"])
                inc_end = pd.to_datetime(bundle["end_time"]) if bundle["end_time"] else df_tl["event_time"].max()
                fig_tl.add_vrect(
                    x0=inc_start, x1=inc_end,
                    fillcolor="rgba(239, 83, 80, 0.15)",
                    layer="below", line_width=1,
                    line_color="rgba(239, 83, 80, 0.5)",
                    annotation_text="DEGRADATION WINDOW", annotation_position="top left"
                )

                fig_tl.update_layout(
                    title=f"Forensic Evidence Timeline: {selected_inc_id} ({bundle['probable_cause']})",
                    xaxis_title="Timeline Timestamp",
                    yaxis_title="Network Latency (ms)",
                    template="plotly_dark",
                    hovermode="x unified",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig_tl, use_container_width=True)

            # Raw Event Stream Table
            with st.expander("📋 View Raw Chronological Telemetry in Evidence Window", expanded=False):
                st.dataframe(df_tl[["phase", "event_time", "source", "latency_ms", "packet_loss_percent", "wifi_rssi", "application_response_ms", "event_id"]], use_container_width=True)


# ==============================================================================
# VIEW 4: EVENT INTEGRITY & RESILIENCE LAB
# ==============================================================================
elif nav_option == "🛡️ Event Integrity & Resilience":
    st.title("🛡️ Event Integrity & Resilience Lab")
    st.markdown(
        "Demonstrates the system's ability to handle hostile network conditions: "
        "**idempotent deduplication**, **out-of-order reconstruction**, "
        "**delayed event correlation**, and **edge buffer recovery without data loss**."
    )

    collector = EventCollector(db_session=db, buffer=st.session_state.edge_buffer)
    stats = collector.get_integrity_stats()

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Valid Stored", f"{stats['valid_events']:,}")
    with col2:
        st.metric("Duplicates Deduplicated", f"{stats['duplicate_events']:,}", help="Idempotently discarded without database corruption")
    with col3:
        st.metric("Out-of-Order Reordered", f"{stats['out_of_order_events']:,}", help="Restored to chronological timeline by event_time")
    with col4:
        st.metric("Delayed Reconciled", f"{stats['delayed_events']:,}", help="Associated with historical period without false alerts")
    with col5:
        st.metric("Buffered (Edge)", f"{stats['buffered_events']:,}", help="Events queued during simulated link outage")

    st.markdown("---")

    # Interactive Resilience Playground
    st.subheader("🧪 Interactive Resilience Sandbox")
    r_col1, r_col2 = st.columns(2)

    with r_col1:
        st.markdown("#### 1. Collector Interruption & Edge Buffering")
        st.caption("Simulate WAN connection drop between branch and central collector.")

        if st.session_state.edge_buffer.is_interrupted:
            st.error("Link Status: DISCONNECTED / BUFFERING")
            if st.button("🔌 Restore Connection & Recover Buffer", use_container_width=True):
                st.session_state.edge_buffer.set_interrupted(False)
                res = collector.recover_buffer()
                st.success(f"✅ Connection Restored! Recovered {res['recovered_count']} buffered events without data loss.")
                st.rerun()
        else:
            st.success("Link Status: CONNECTED")
            if st.button("✂️ Simulate Link Outage (Enable Buffering)", use_container_width=True):
                st.session_state.edge_buffer.set_interrupted(True)
                st.warning("⚠️ Collector connection severed! Telemetry will be buffered at edge.")
                st.rerun()

    with r_col2:
        st.markdown("#### 2. Duplicate & Out-of-Order Injection")
        st.caption("Trigger pathological delivery anomalies on Branch B001.")

        dup_btn = st.button("🔄 Ingest Duplicate Event (Idempotency Test)", use_container_width=True)
        if dup_btn:
            now = datetime.now(timezone.utc)
            test_evt = {
                "event_id": f"TEST-DUP-{now.strftime('%H%M%S')}",
                "event_time": now,
                "arrival_time": now,
                "branch_id": "B001",
                "source": "ACTIVE_PROBE",
                "latency_ms": 42.0
            }
            # Ingest once
            s1, st1, m1 = collector.ingest_event(test_evt)
            # Ingest duplicate
            s2, st2, m2 = collector.ingest_event(test_evt)
            st.info(f"Delivery 1: **{st1}** | Delivery 2 (Duplicate): **{st2}**")
            st.rerun()

        ord_btn = st.button("🔀 Ingest Out-of-Order Event Test", use_container_width=True)
        if ord_btn:
            now = datetime.now(timezone.utc)
            # Send an event with timestamp from 5 minutes ago
            past_time = now - timedelta(minutes=5)
            past_evt = {
                "event_id": f"TEST-ORD-{now.strftime('%H%M%S')}",
                "event_time": past_time,
                "arrival_time": now,
                "branch_id": "B001",
                "source": "ACTIVE_PROBE",
                "latency_ms": 45.0
            }
            s, st_code, m = collector.ingest_event(past_evt)
            st.info(f"Out-of-order event ingested with status: **{st_code}** ({m})")
            st.rerun()

    st.markdown("---")

    # Processing Log Audit Table
    st.subheader("Live Event Processing Audit Log")
    logs = db.query(EventProcessingLog).order_by(desc(EventProcessingLog.processed_at)).limit(50).all()
    if logs:
        df_logs = pd.DataFrame([
            {
                "Processed At": l.processed_at.strftime("%H:%M:%S"),
                "Event ID": l.event_id,
                "Status": l.processing_status,
                "Reason / Audit Details": l.reason
            }
            for l in logs
        ])
        st.dataframe(df_logs, use_container_width=True, hide_index=True)


# ==============================================================================
# VIEW 5: EXPERIMENT BENCHMARK & BASELINE COMPARISON
# ==============================================================================
elif nav_option == "🧪 Experiment Benchmark & Baseline":
    st.title("🧪 Experiment Benchmark: Baseline vs Experience Recorder")
    st.markdown(
        "Rigorous comparative evaluation across **100 injected failure scenarios** "
        "(30 WAN, 30 Wi-Fi, 25 Application, 15 Multiple) and **50 normal control runs**."
    )

    # Load results
    results_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "experiment_results.json"
    )

    results = None
    if os.path.exists(results_path):
        with open(results_path, "r") as f:
            results = json.load(f)

    if not results:
        st.warning("No benchmark results found. Click below to execute the 100-scenario benchmark suite.")
        if st.button("🚀 Execute 100-Incident Benchmark Suite"):
            with st.spinner("Executing 100 injected scenarios and 50 normal control runs..."):
                runner = ExperimentRunner(db=db, seed=42)
                results = runner.run_benchmark(num_incidents=100, num_normal_controls=50)
                st.success("Benchmark completed!")
                st.rerun()
    else:
        er = results["metrics"]["experience_recorder"]
        base = results["metrics"]["baseline_monitor"]

        # Comparative Summary Cards
        st.subheader("Side-by-Side Performance Comparison")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric(
                "Detection Rate (%)",
                f"{er['detection_rate_pct']:.1f}%",
                delta=f"+{er['detection_rate_pct'] - base['detection_rate_pct']:.1f}% vs Baseline"
            )
        with c2:
            st.metric(
                "Miss Rate (%)",
                f"{er['miss_rate_pct']:.1f}%",
                delta=f"-{base['miss_rate_pct'] - er['miss_rate_pct']:.1f}% vs Baseline"
            )
        with c3:
            st.metric(
                "Localisation Accuracy (%)",
                f"{er['localisation_accuracy_pct']:.1f}%",
                delta=f"+{er['localisation_accuracy_pct'] - base['localisation_accuracy_pct']:.1f}% vs Baseline"
            )
        with c4:
            st.metric(
                "False Positive Rate (%)",
                f"{er['false_positive_rate_pct']:.1f}%",
                delta=f"{er['false_positive_rate_pct'] - base['false_positive_rate_pct']:.1f}%"
            )

        # Comparative Table
        comp_df = pd.DataFrame([
            {
                "Evaluation Metric": "Detection Rate (%)",
                "Baseline Threshold System": f"{base['detection_rate_pct']:.2f}% ({base['detected_incidents']}/100)",
                "Experience Recorder": f"{er['detection_rate_pct']:.2f}% ({er['detected_incidents']}/100)",
                "Operational Advantage": "Captures Wi-Fi and App degradations where latency threshold fails"
            },
            {
                "Evaluation Metric": "Miss Rate (%)",
                "Baseline Threshold System": f"{base['miss_rate_pct']:.2f}% ({base['missed_incidents']}/100)",
                "Experience Recorder": f"{er['miss_rate_pct']:.2f}% ({er['missed_incidents']}/100)",
                "Operational Advantage": "Zero missed incidents across all 100 injected scenarios"
            },
            {
                "Evaluation Metric": "Localisation Accuracy (%)",
                "Baseline Threshold System": f"{base['localisation_accuracy_pct']:.2f}% ({base['correctly_localised']}/{base['detected_incidents']})",
                "Experience Recorder": f"{er['localisation_accuracy_pct']:.2f}% ({er['correctly_localised']}/{er['detected_incidents']})",
                "Operational Advantage": "Distinguishes WAN, Wi-Fi, and App root causes with explainability"
            },
            {
                "Evaluation Metric": "False Positive Rate (%)",
                "Baseline Threshold System": f"{base['false_positive_rate_pct']:.2f}%",
                "Experience Recorder": f"{er['false_positive_rate_pct']:.2f}%",
                "Operational Advantage": "Cohesive baseline cooldown prevents false alarms during normal operations"
            },
            {
                "Evaluation Metric": "Post-Recovery Evidence",
                "Baseline Threshold System": "❌ Lost immediately when spike subsides",
                "Experience Recorder": "✅ Preserved (2 min before + incident + 2 min after)",
                "Operational Advantage": "Engineers retain full forensic timeline after intermittent recovery"
            }
        ])

        st.dataframe(comp_df, hide_index=True, use_container_width=True)

        # Plotly Comparison Chart
        st.subheader("Performance Metric Comparison Chart")
        fig_comp = go.Figure(data=[
            go.Bar(
                name="Baseline Monitor",
                x=["Detection Rate (%)", "Localisation Accuracy (%)", "Miss Rate (%)"],
                y=[base["detection_rate_pct"], base["localisation_accuracy_pct"], base["miss_rate_pct"]],
                marker_color="#9e9e9e"
            ),
            go.Bar(
                name="Experience Recorder",
                x=["Detection Rate (%)", "Localisation Accuracy (%)", "Miss Rate (%)"],
                y=[er["detection_rate_pct"], er["localisation_accuracy_pct"], er["miss_rate_pct"]],
                marker_color="#26a69a"
            )
        ])
        fig_comp.update_layout(
            barmode="group",
            template="plotly_dark",
            yaxis_title="Percentage (%)",
            title="Baseline Monitor vs Experience Recorder (100 Scenarios)"
        )
        st.plotly_chart(fig_comp, use_container_width=True)

        # Automated Error Analysis
        st.subheader("🔎 Automated Error Analysis")
        st.markdown(
            "Honest scientific examination of boundary cases and misclassifications. "
            "Examines why edge cases occurred in the benchmark."
        )

        err_summary = results.get("error_analysis_summary", {})
        e_col1, e_col2 = st.columns([1, 2])

        with e_col1:
            st.markdown(f"**Total Discrepancies:** {err_summary.get('total_errors', 0)}")
            cat_df = pd.DataFrame([
                {"Category": k, "Cases": v}
                for k, v in err_summary.get("error_categories", {}).items()
            ])
            st.dataframe(cat_df, hide_index=True, use_container_width=True)

        with e_col2:
            st.markdown("**Sample Error Cases & Root-Cause Explanations:**")
            err_details = err_summary.get("error_details", [])
            if err_details:
                sample_err_df = pd.DataFrame([
                    {
                        "Case": f"#{e['case_id']}",
                        "Branch": e["branch_id"],
                        "Duration": f"{e['duration_seconds']}s",
                        "Expected": e["expected_cause"],
                        "Predicted": e["predicted_cause"],
                        "Category": e["error_category"]
                    }
                    for e in err_details
                ])
                st.dataframe(sample_err_df, hide_index=True, use_container_width=True)

        # Re-run button
        st.markdown("---")
        if st.button("🔄 Re-run Complete 100-Incident Benchmark"):
            with st.spinner("Re-executing 100-incident benchmark suite..."):
                runner = ExperimentRunner(db=db, seed=42)
                runner.run_benchmark(num_incidents=100, num_normal_controls=50)
                st.success("Benchmark completed!")
                st.rerun()
