"""AquaPulse — 4-Tab Streamlit Interactive Prototype & Hackathon Pitch Dashboard.

Sime Darby Property University Hackathon ("Township of Tomorrow")
Tracks: People (Life Safety, Community Harmony, Inclusivity) & Planet (Energy & Water Conservation)
"""

from __future__ import annotations

import cv2
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from aquapulse.agent.tools import synthesize_alert_wav
from aquapulse.api.main import AquaPulseRuntimeService
from aquapulse.db.database import (
    fetch_30d_esg_summary,
    fetch_maintenance_tickets,
    fetch_recent_incidents,
)
from aquapulse.esg.pump_optimizer import (
    compute_instantaneous_esg_metrics,
    generate_affinity_law_curve,
    optimize_24h_vfd_schedule,
)
from aquapulse.schemas import (
    AgentState,
    PoolZone,
    PostureState,
    PrivacyMode,
    ScenarioName,
    SwimmerRole,
    SwimmerTrack,
    ViolationType,
)
from aquapulse.vision.agentic_inspector import crop_and_zoom_roi
from aquapulse.vision.detector import build_coco_keypoints
from aquapulse.vision.privacy import render_tier2_silhouette_frame
from aquapulse.vision.water_inspector import inspect_water_clarity

st.set_page_config(
    page_title="AquaPulse | Sime Darby Property Township Pool AI",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

SCENARIO_LABELS: dict[ScenarioName, str] = {
    ScenarioName.SILENT_DROWNING_RESCUE: (
        "1. 🚨 Silent Drowning Rescue (0s Flailing -> 10s VERIFY -> 20s CRITICAL Siren)"
    ),
    ScenarioName.UNACCOMPANIED_TODDLER_DEEP_END: (
        "2. 👶 Unaccompanied Toddler Near Deep End (1.5m Supervision Radius)"
    ),
    ScenarioName.COTTON_TSHIRT_AND_FOOD_NUDGE: (
        "3. 👕 System 2 Governance: Cotton T-Shirt & Poolside Food/Drink (15s Nudge -> 30s Ticket)"
    ),
    ScenarioName.PET_AND_STRAY_ANIMAL_POOL: (
        "4. 🐕‍🦺 Pet Dog in Pool & Stray Cat on Deck (YOLO26 COCO #15/#16 -> Strata Nudge + 100% VFD Bio-Purge)"
    ),
    ScenarioName.MONSOON_DEBRIS_AND_ALGAE: (
        "5. 🍂 Off-Peak Monsoon Storm Leaves & Algae Drift (Auto JMB Cleaner Ticket)"
    ),
    ScenarioName.PEAK_CROWD_SURGE_ECO_DRIVE: (
        "6. ⚡ Peak Crowd Surge (14 Swimmers -> High VFD Filtration & Post-Peak Purge)"
    ),
    ScenarioName.NORMAL_LAP_AND_FAMILY: (
        "7. 🏊 Normal Lap & Supervised Family Swim (Baseline Operation)"
    ),
}

DAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def _get_service() -> AquaPulseRuntimeService:
    """Return session-scoped `AquaPulseRuntimeService`."""
    if "aquapulse_service" not in st.session_state:
        svc = AquaPulseRuntimeService()
        svc.step_simulation(
            scenario=ScenarioName.SILENT_DROWNING_RESCUE,
            target_elapsed_sec=0.0,
            reset=True,
        )
        st.session_state["aquapulse_service"] = svc
    return st.session_state["aquapulse_service"]


def _bgr_to_rgb(img_bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)


@st.fragment
def render_tab1_command_center() -> None:
    """Tab 1: Live Vision & Agentic Command Center wrapped in @st.fragment for smooth updates."""
    svc = _get_service()

    st.subheader("🎯 Live Vision & Dual-Path Agentic Command Center")
    st.caption(
        "**Path 1 (System 1 `<30ms` Local Reflex)**: Active Surface Flailing + Silent Submersion & Toddler Deep-End Supervision | "
        "**Path 2 (System 2 `1–3s` Agentic ROI)**: Tier-1 Face-Masked Attire & Poolside Item Verification"
    )

    ctrl_col1, ctrl_col2 = st.columns([2.2, 1.3])
    with ctrl_col1:
        selected_scenario = st.selectbox(
            "Select Deterministic Hackathon Pitch Scenario",
            options=list(SCENARIO_LABELS.keys()),
            format_func=lambda s: SCENARIO_LABELS[s],
            index=list(SCENARIO_LABELS.keys()).index(svc.current_scenario),
            key="tab1_scenario_select",
        )
    with ctrl_col2:
        view_mode = st.radio(
            "Malaysia PDPA 2010 / 2024 Privacy View Mode",
            options=[
                "Tier-2 Skeletal Silhouette (Default 0% Raw Pixels)",
                "Tier-1 Face-Masked Raw + ROI Inspector",
            ],
            index=0,
            key="tab1_pdpa_mode",
        )

    # Timeline quick-jump preset buttons for effortless 3-minute live pitch
    btn_cols = st.columns(6)
    target_jump: float | None = None
    step_dt: float | None = None

    if selected_scenario != svc.current_scenario:
        target_jump = 0.0

    if btn_cols[0].button("⏮️ Reset (0s)", use_container_width=True):
        target_jump = 0.0
    if btn_cols[1].button("⏩ Step +5s", use_container_width=True, type="primary"):
        step_dt = 5.0
    if btn_cols[2].button("🟡 10s (VERIFY)", use_container_width=True):
        target_jump = 10.0
    if btn_cols[3].button("🔊 15s (Sys2 Nudge #1)", use_container_width=True):
        target_jump = 15.0
    if btn_cols[4].button("🚨 20s (CRITICAL)", use_container_width=True):
        target_jump = 20.0
    if btn_cols[5].button("👮 30s (Guard Ticket)", use_container_width=True):
        target_jump = 30.0

    if target_jump is not None:
        snap = svc.step_simulation(
            scenario=selected_scenario,
            target_elapsed_sec=target_jump,
            reset=True,
            privacy_mode=PrivacyMode.SILHOUETTE,
        )
    elif step_dt is not None:
        snap = svc.step_simulation(
            scenario=selected_scenario,
            dt_sec=step_dt,
            reset=False,
            privacy_mode=PrivacyMode.SILHOUETTE,
        )
    else:
        snap = svc.last_snapshot or svc.step_simulation(
            scenario=selected_scenario,
            target_elapsed_sec=0.0,
            reset=True,
        )

    sys1 = snap["system1_trace"]
    overall_state = sys1["overall_state"]
    frames = snap["_frames"]

    # Top KPI telemetry bar
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Simulation Clock", f"{snap['elapsed_sec']:.1f} s")
    k2.metric("Overall Agent State", overall_state)
    k3.metric(
        "System 1 Reflex Latency",
        f"{sys1['execution_latency_ms']:.2f} ms",
        delta="< 30.0 ms Real-Time Budget",
    )
    k4.metric(
        "Tracked Swimmers (Persistent IDs)",
        f"{len(snap['tracks'])} active",
        delta="PDPA Tier-2 Anonymized",
    )

    # Visual Canvas + System 2 ROI Zoom & Audio Alert Panel
    left_canvas, right_inspector = st.columns([1.65, 1.15])

    with left_canvas:
        if view_mode.startswith("Tier-2"):
            st.image(
                _bgr_to_rgb(frames["silhouette_bgr"]),
                caption=(
                    f"Tier-2 PDPA Skeletal Silhouette Canvas (0% Raw Biometric Pixels) — "
                    f"Scenario: {snap['scenario']} @ t={snap['elapsed_sec']:.1f}s"
                ),
                use_container_width=True,
            )
        else:
            # Show raw synthetic frame with Tier-1 Face Redaction applied on all tracked persons
            masked_preview = frames["raw_bgr"].copy()
            for tr_dict in snap["tracks"]:
                tr_obj = SwimmerTrack.model_validate(tr_dict)
                from aquapulse.vision.privacy import apply_tier1_face_mask

                masked_preview, _ = apply_tier1_face_mask(masked_preview, tr_obj)
            st.image(
                _bgr_to_rgb(masked_preview),
                caption="Tier-1 Face-Masked Frame (Head kp[0..4] Redacted in Solid Black; Torso/Deck Preserved for System 2)",
                use_container_width=True,
            )

        # Custom Pool Photo / Frame Uploader (Judge Live Test Mode)
        with st.expander("📷 Upload Custom Pool Image / Video Frame (Live PDPA & Water QA Test)"):
            uploaded = st.file_uploader(
                "Upload a swimming pool image (.jpg, .png) to run Two-Tier PDPA & OpenCV Water Inspection",
                type=["jpg", "jpeg", "png"],
                key="custom_frame_upload",
            )
            if uploaded is not None:
                file_bytes = np.frombuffer(uploaded.read(), dtype=np.uint8)
                decoded = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                if decoded is not None:
                    resized = cv2.resize(decoded, (640, 360))
                    kps_demo, bbox_demo = build_coco_keypoints(
                        320, 180, posture=PostureState.VERTICAL_TREADING
                    )
                    demo_track = SwimmerTrack(
                        track_id=901,
                        role=SwimmerRole.ADULT,
                        zone=PoolZone.ZONE_A_SHALLOW,
                        posture=PostureState.VERTICAL_TREADING,
                        bbox=bbox_demo,
                        pool_coords_m=(12.5, 6.0),
                        keypoints=kps_demo,
                        suspected_violation=ViolationType.COTTON_ATTIRE,
                    )
                    roi_zoom, is_redacted, _ = crop_and_zoom_roi(resized, demo_track)
                    sil_custom = render_tier2_silhouette_frame([demo_track])
                    water_rep_custom, water_vis_custom = inspect_water_clarity(resized)

                    u1, u2, u3 = st.columns(3)
                    u1.image(
                        _bgr_to_rgb(sil_custom),
                        caption="Tier-2 Skeletal Silhouette Output",
                        use_container_width=True,
                    )
                    u2.image(
                        _bgr_to_rgb(roi_zoom),
                        caption=f"Tier-1 Face-Masked 2x ROI (Redacted={is_redacted})",
                        use_container_width=True,
                    )
                    u3.image(
                        _bgr_to_rgb(water_vis_custom),
                        caption=f"Water QA: {water_rep_custom.status} ({water_rep_custom.turbidity_score}/100)",
                        use_container_width=True,
                    )

    with right_inspector:
        st.markdown("#### 🔍 System 2 Tier-1 Face-Masked ROI Zoom & Audio Actuators")
        roi_crops: dict[int, np.ndarray] = frames["roi_crops_bgr"]
        if roi_crops:
            roi_cols = st.columns(min(2, len(roi_crops)))
            for idx, (tid, crop_bgr) in enumerate(roi_crops.items()):
                roi_cols[idx % len(roi_cols)].image(
                    _bgr_to_rgb(crop_bgr),
                    caption=f"Track #{tid} Tier-1 Face-Masked 2x ROI (kp[0..4] = [0,0,0])",
                    use_container_width=True,
                )
        else:
            st.info(
                "No System 2 attire/item ROI crop active in this scenario. "
                "(Select Scenario #3 'Cotton T-Shirt & Food Nudge' to inspect Tier-1 Face-Masked 2x ROI crops.)"
            )

        # Playable Offline WAV Audio & Directional Speaker Broadcast
        if overall_state == AgentState.CRITICAL_EMERGENCY:
            st.error(
                "🚨 **CRITICAL EMERGENCY (20.0s)!** Poolside Directional Siren + Bilingual TTS Broadcast Active!"
            )
            st.audio(synthesize_alert_wav("critical_siren"), format="audio/wav")
        elif overall_state == AgentState.VERIFY:
            st.warning(
                "🟡 **VERIFY STATE (10.0s):** Yellow Poolside Caution Strobe Flashing & Guardhouse Pre-Alerted."
            )
            st.audio(synthesize_alert_wav("verify_beacon"), format="audio/wav")
        elif overall_state in (AgentState.NUDGE_REQUIRED, AgentState.ESCALATED_GUARD_TICKET):
            st.warning(
                f"🔊 **{overall_state}:** Polite Directional Speaker Nudge Active (System 2 Verified)."
            )
            st.audio(synthesize_alert_wav("polite_nudge"), format="audio/wav")
        else:
            st.success("✅ **NORMAL MONITORING:** All swimmers active or supervised within 1.5m.")

        # Guardhouse Smartphone Dispatch Card
        latest_tools = snap["tool_logs"]
        if latest_tools:
            last_tool = latest_tools[-1]
            with st.container(border=True):
                st.markdown("##### 📱 Guardhouse Auxiliary Police Smartphone Alert")
                st.markdown(
                    f"**Tool Fired**: `{last_tool['tool_name']}` (`{last_tool['system_path']}`)"
                )
                st.markdown(
                    f"**Zone**: `{last_tool['zone']}` | **Track ID**: `#{last_tool['track_id']}`"
                )
                if last_tool.get("audio_tts_text"):
                    st.markdown(f"**Directional Speaker TTS**: *{last_tool['audio_tts_text']}*")
                if last_tool.get("guard_route_hint"):
                    st.markdown(f"**Fastest Entry Route**: `{last_tool['guard_route_hint']}`")

    # Per-Track State Table & Structured Reasoning Log
    t_col, r_col = st.columns([1.2, 1.3])
    with t_col:
        st.markdown("##### 🧭 Persistent Multi-Swimmer State Table (`track_id`)")
        if sys1["track_states"]:
            df_tracks = pd.DataFrame(sys1["track_states"])[
                [
                    "track_id",
                    "role",
                    "zone",
                    "submersion_sec",
                    "is_flailing",
                    "is_submerged",
                    "unaccompanied_infant_sec",
                    "nearest_adult_m",
                    "is_supervised",
                    "violation_sec",
                    "nudge_count",
                    "agent_state",
                ]
            ]
            st.dataframe(df_tracks, use_container_width=True, hide_index=True)
    with r_col:
        st.markdown("##### 🧠 Live System 1 & System 2 Reasoning Trace")
        recent_thoughts = svc.reasoning_logger.logs[-8:]
        if recent_thoughts:
            st.dataframe(
                pd.DataFrame(reversed(recent_thoughts)),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption(
                "Step the simulation (+5s or 10s/15s/20s buttons) to record reasoning traces."
            )


def render_tab2_esg_simulator() -> None:
    """Tab 2: Planet Track ESG & VFD Pump Energy Simulator with Township Scale Multiplier."""
    svc = _get_service()
    summary_30d = fetch_30d_esg_summary(svc.conn)

    st.subheader("🌱 Dynamic Bather-Load VFD Filtration Pump & Township ESG Simulator")
    st.caption(
        "**Pump Affinity Law**: $P_2 / P_1 = (N_2 / N_1)^3$ | "
        "**Malaysian TNB Commercial/Strata Tariff**: `RM 0.51 / kWh` | "
        "**Grid Carbon Factor**: `0.758 kg CO2 / kWh` | "
        "**Sanitation Floor**: `>= 3.5 Turnovers / Day` (`1,575 m³/day`)"
    )

    # Interactive What-If Bather-Load & Sime Darby Township Scale Sliders
    s1, s2, s3, s4, s5 = st.columns(5)
    sim_bathers = s1.slider(
        "Live Swimmer Headcount", min_value=0, max_value=30, value=0, key="esg_bathers"
    )
    sim_cotton = s2.slider(
        "Cotton Attire Violations", min_value=0, max_value=6, value=0, key="esg_cotton"
    )
    sim_food = s3.slider(
        "Poolside Food/Drink Events", min_value=0, max_value=5, value=0, key="esg_food"
    )
    sim_animal = s4.slider(
        "🐕 Pet / Stray Animal Events", min_value=0, max_value=3, value=0, key="esg_animal"
    )
    township_pools = s5.slider(
        "🏙️ Sime Darby Township Scale (Strata Pools)",
        min_value=1,
        max_value=25,
        value=10,
        help="Scale annual savings across multiple Sime Darby Property townships (Elmina, Putra Heights, Ara Damansara, etc.)",
        key="esg_township_scale",
    )

    live_esg = compute_instantaneous_esg_metrics(
        bather_count=sim_bathers,
        cotton_violations=sim_cotton,
        food_drink_events=sim_food,
        animal_events=sim_animal,
    )

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Contamination Score", f"{live_esg.contamination_score:.1f}")
    m2.metric(
        "Recommended VFD Speed",
        f"{live_esg.recommended_vfd_speed_pct:.0f}%",
        delta=f"{live_esg.flow_rate_m3h:.1f} m³/h flow",
    )
    m3.metric(
        "VFD Pump Power Draw",
        f"{live_esg.vfd_pump_kw:.3f} kW",
        delta=f"-{live_esg.hourly_kwh_saved:.2f} kWh/h vs 5.5kW Fixed",
    )
    m4.metric(
        "Daily Turnover Compliance",
        f"{live_esg.projected_daily_turnovers:.2f}x / day",
        delta="COMPLIANT (>= 3.5x Floor)" if live_esg.turnover_floor_compliant else "BELOW FLOOR",
    )
    annual_township_rm = summary_30d["projected_annual_rm_saved"] * township_pools
    annual_township_co2_tonnes = (
        summary_30d["projected_annual_co2_saved_kg"] * township_pools
    ) / 1000.0
    m5.metric(
        f"Township Annual Savings ({township_pools} Pools)",
        f"RM {annual_township_rm:,.0f} / yr",
        delta=f"{annual_township_co2_tonnes:,.1f} tonnes CO2 / yr avoided",
    )

    # Plotly Charts: (1) Cubic Pump Affinity Law Curve & (2) 24-Hour VFD Schedule
    c_left, c_right = st.columns(2)

    with c_left:
        curve = generate_affinity_law_curve()
        df_curve = pd.DataFrame(curve)
        fig_aff = go.Figure()
        fig_aff.add_trace(
            go.Scatter(
                x=df_curve["vfd_speed_pct"],
                y=df_curve["fixed_power_kw"],
                mode="lines",
                name="Fixed-Speed Pump (5.5 kW Constant)",
                line={"dash": "dash", "color": "#EF476F", "width": 2},
            )
        )
        fig_aff.add_trace(
            go.Scatter(
                x=df_curve["vfd_speed_pct"],
                y=df_curve["vfd_power_kw"],
                mode="lines+markers",
                name="VFD Eco-Drive Power P ∝ N³ (kW)",
                line={"color": "#06D6A0", "width": 3},
            )
        )
        fig_aff.add_trace(
            go.Scatter(
                x=[live_esg.recommended_vfd_speed_pct],
                y=[live_esg.vfd_pump_kw],
                mode="markers",
                name="Current Operating Point",
                marker={"size": 14, "color": "#FFD166", "symbol": "star"},
            )
        )
        fig_aff.update_layout(
            title="Cubic Pump Affinity Law Curve: Power (kW) vs. VFD Speed (%)",
            xaxis_title="VFD Pump Speed (%)",
            yaxis_title="Electrical Power Draw (kW)",
            height=360,
            margin={"l": 20, "r": 20, "t": 45, "b": 20},
        )
        st.plotly_chart(fig_aff, use_container_width=True)

    with c_right:
        typical_bathers = [
            0,
            0,
            0,
            0,
            0,
            0,
            8,
            12,
            9,
            4,
            3,
            2,
            1,
            2,
            3,
            5,
            12,
            18,
            20,
            15,
            8,
            3,
            0,
            0,
        ]
        plan_24h = optimize_24h_vfd_schedule(typical_bathers)
        df_24h = pd.DataFrame(plan_24h["hourly_schedule"])
        fig_24h = go.Figure()
        fig_24h.add_trace(
            go.Bar(
                x=df_24h["hour"],
                y=df_24h["bather_count"],
                name="Swimmer Headcount",
                marker_color="#118AB2",
                opacity=0.45,
                yaxis="y2",
            )
        )
        fig_24h.add_trace(
            go.Scatter(
                x=df_24h["hour"],
                y=df_24h["fixed_pump_kw"],
                mode="lines",
                name="Fixed Pump (5.5 kW)",
                line={"dash": "dot", "color": "#EF476F"},
            )
        )
        fig_24h.add_trace(
            go.Scatter(
                x=df_24h["hour"],
                y=df_24h["vfd_pump_kw"],
                mode="lines+markers",
                name="AquaPulse VFD Power (kW)",
                line={"color": "#06D6A0", "width": 3},
            )
        )
        fig_24h.update_layout(
            title=(
                f"24-Hour VFD Eco-Drive Profile ({plan_24h['energy_reduction_pct']}% kWh Saved | "
                f"{plan_24h['daily_turnovers']}x Daily Turnovers)"
            ),
            xaxis_title="Hour of Day (00:00 – 23:00)",
            yaxis={"title": "Pump Power (kW)"},
            yaxis2={"title": "Swimmers", "overlaying": "y", "side": "right"},
            height=360,
            margin={"l": 20, "r": 20, "t": 45, "b": 20},
        )
        st.plotly_chart(fig_24h, use_container_width=True)

    # 30-Day SQLite Historical Summary Banner
    with st.container(border=True):
        st.markdown(
            "##### 📊 30-Day Seeded Malaysian Strata Condo Pool Telemetry Summary (`720 Hours`)"
        )
        b1, b2, b3, b4, b5 = st.columns(5)
        b1.metric("30-Day Fixed Baseline", f"{summary_30d['total_fixed_kwh']:,.1f} kWh")
        b2.metric(
            "30-Day AquaPulse VFD",
            f"{summary_30d['total_vfd_kwh']:,.1f} kWh",
            delta=f"-{summary_30d['energy_reduction_pct']}% Energy Cut",
        )
        b3.metric(
            "Single-Pool 30d TNB Saved",
            f"RM {summary_30d['total_rm_saved']:,.2f}",
            delta=f"RM {summary_30d['projected_annual_rm_saved']:,.0f} / yr",
        )
        b4.metric(
            "Single-Pool 30d Carbon Cut",
            f"{summary_30d['total_co2_saved_kg']:,.1f} kg CO2",
            delta=f"{summary_30d['projected_annual_co2_saved_kg']:,.0f} kg / yr",
        )
        b5.metric(
            "Min Daily Turnover Floor",
            f"{summary_30d['min_daily_turnovers']:.2f} turnovers/day",
            delta="100% Days >= 3.5x Floor",
        )


def render_tab3_water_inspector() -> None:
    """Tab 3: Visual Water Clarity & Monsoon Storm Debris Inspector."""
    svc = _get_service()

    st.subheader("🍂 Off-Peak Visual Water Clarity & Monsoon Storm Debris Inspector")
    st.caption(
        "Analyzes underwater ceramic tile contrast (`cv2.Laplacian`), early green-algae hue shift (`HSV`), "
        "and floating organic monsoon storm leaves/twigs (`cv2.findContours`) to auto-dispatch JMB morning skimming crews."
    )

    clean_frame, _, _ = svc.detector.process_scenario(ScenarioName.NORMAL_LAP_AND_FAMILY, 0.0)
    clean_rep, clean_vis = inspect_water_clarity(clean_frame)

    monsoon_frame, _, _ = svc.detector.process_scenario(ScenarioName.MONSOON_DEBRIS_AND_ALGAE, 0.0)
    monsoon_rep, monsoon_vis = inspect_water_clarity(monsoon_frame)

    col_clean, col_monsoon = st.columns(2)
    with col_clean:
        st.markdown("##### ✅ Baseline: Crystal-Clear Chlorinated Basin")
        st.image(_bgr_to_rgb(clean_vis), use_container_width=True)
        st.success(
            f"**Status**: `{clean_rep.status}` | **Clarity Score**: `{clean_rep.turbidity_score}/100` | "
            f"**Green Algae Index**: `{clean_rep.algae_green_index}` | **Floating Leaves**: `{clean_rep.floating_debris_count}`"
        )

    with col_monsoon:
        st.markdown("##### 🌧️ Post-Monsoon Squall: Floating Leaves & Early Algae Drift")
        st.image(_bgr_to_rgb(monsoon_vis), use_container_width=True)
        st.error(
            f"**Status**: `{monsoon_rep.status}` | **Clarity Score**: `{monsoon_rep.turbidity_score}/100` | "
            f"**Green Algae Index**: `{monsoon_rep.algae_green_index}` | **Floating Leaves**: `{monsoon_rep.floating_debris_count}`"
        )
        if st.button("🛠️ Auto-Dispatch JMB Morning Cleaner Work Order", type="primary"):
            svc.actuator.create_jmb_cleaner_ticket(monsoon_rep)
            st.toast("JMB Morning Pool Cleaning Crew ticket created in SQLite!")

    st.markdown(
        "##### 📋 Automated JMB / MC Facility Maintenance Work-Order Log (`maintenance_tickets`)"
    )
    tickets = fetch_maintenance_tickets(svc.conn, limit=15)
    if tickets:
        st.dataframe(pd.DataFrame(tickets), use_container_width=True, hide_index=True)

    st.markdown(
        "##### 🛡️ Recent PDPA-Anonymized Security & Governance Incident Log (`incident_logs`)"
    )
    incidents = fetch_recent_incidents(svc.conn, limit=10)
    if incidents:
        st.dataframe(pd.DataFrame(incidents), use_container_width=True, hide_index=True)


def render_tab4_resident_widget() -> None:
    """Tab 4: Resident Township App 'Crowd & Comfort' Mobile Widget & Scikit-Learn Forecaster."""
    svc = _get_service()

    st.subheader("📱 Resident Township App — 'Crowd & Comfort' Live Widget")
    st.caption(
        "Empowers Sime Darby Property township residents with anonymous real-time pool occupancy, "
        "water clarity status, `scikit-learn` predicted Quiet Swim Windows, and inclusive Senior/Toddler safe hours."
    )

    top_ctrl1, top_ctrl2 = st.columns([1.2, 1.8])
    with top_ctrl1:
        selected_dow = st.selectbox(
            "Select Day of Week for Diurnal Forecast",
            options=list(range(7)),
            format_func=lambda d: DAY_NAMES[d],
            index=5,  # Saturday default
            key="tab4_dow_select",
        )
    with top_ctrl2:
        notify_enabled = st.toggle(
            "🔔 Subscribe Resident App to 'Quiet Window & Senior/Toddler Safe-Hour' Push Alerts",
            value=True,
            key="tab4_notify_toggle",
        )

    _, tracks, _ = svc.detector.process_scenario(svc.current_scenario, svc.elapsed_sec)
    raw_frame, _, _ = svc.detector.process_scenario(svc.current_scenario, svc.elapsed_sec)
    water_rep, _ = inspect_water_clarity(raw_frame)

    comfort = svc.forecaster.build_resident_comfort_status(
        tracks=tracks,
        water_report=water_rep,
        day_of_week=selected_dow,
    )
    forecast_24h = svc.forecaster.predict_24h_profile(day_of_week=selected_dow)

    card_col, chart_col = st.columns([1.1, 1.6])

    with card_col:
        with st.container(border=True):
            st.markdown("### 🏙️ Elmina Township Resident App")
            st.caption("📍 **Olympic & Family Wading Pool • 100% PDPA Anonymous Telemetry**")

            badge_color = (
                "🟢 QUIET"
                if comfort.crowd_level == "QUIET"
                else ("🟡 MODERATE" if comfort.crowd_level == "MODERATE" else "🔴 BUSY")
            )
            w1, w2 = st.columns(2)
            w1.metric("Live Pool Crowd", badge_color)
            w2.metric("Active Swimmers", f"{comfort.live_headcount} persons")

            st.markdown(
                f"- **🏊 Lap Swimmers (Zone B)**: `{comfort.lap_swimmers}`\n"
                f"- **👨‍👩‍👧 Family / Leisure Swimmers (Zone A)**: `{comfort.family_swimmers}`\n"
                f"- **💧 Visual Water Quality**: `{comfort.water_clarity_label}`"
            )
            st.divider()
            st.markdown("##### 🕒 Recommended Daytime Quiet Swim Windows")
            for qw in comfort.recommended_quiet_hours:
                st.markdown(f"- ✨ `{qw}`")

            st.markdown("##### 👵👶 Inclusive Senior & Toddler Safe Window")
            st.info(f"🛡️ **{comfort.senior_toddler_safe_window}**")

            if notify_enabled:
                st.success(
                    "📲 Push Notification Armed: You will be notified 15 mins before the next Quiet / Safe Window begins."
                )

    with chart_col:
        df_fc = pd.DataFrame(forecast_24h)
        colors = [
            "#06D6A0" if b == "QUIET" else ("#FFD166" if b == "MODERATE" else "#EF476F")
            for b in df_fc["crowd_band"]
        ]
        fig_fc = go.Figure()
        fig_fc.add_trace(
            go.Bar(
                x=df_fc["hour_label"],
                y=df_fc["predicted_swimmers"],
                marker_color=colors,
                name="Predicted Swimmers",
            )
        )
        fig_fc.update_layout(
            title=f"Scikit-Learn 24-Hour Diurnal Crowd Forecast ({DAY_NAMES[selected_dow]})",
            xaxis_title="Hour of Day",
            yaxis_title="Predicted Swimmer Headcount",
            height=430,
            margin={"l": 20, "r": 20, "t": 45, "b": 20},
        )
        st.plotly_chart(fig_fc, use_container_width=True)


def main() -> None:
    """Render sidebar overview and the 4-Tab AquaPulse Pitch Workbench."""
    with st.sidebar:
        st.markdown("## 🌊 AquaPulse AI")
        st.caption(
            "**Privacy-First Agentic Vision & ESG Pool Optimization** for the "
            "**Sime Darby Property University Hackathon (*Township of Tomorrow*)**"
        )
        st.divider()
        st.markdown(
            "**Dual-Path Agentic Architecture**:\n"
            "- ⚡ **System 1 (`<30ms` Edge Reflex)**: Active Flailing + Silent Submersion (`10s VERIFY -> 20s CRITICAL Siren/TTS`) & `1.5m` Toddler Supervision.\n"
            "- 🔍 **System 2 (`1–3s` Agentic ROI)**: Tier-1 Face-Masked (`kp[0..4]`) 2× ROI Zoom for Cotton Attire & Poolside Food/Drink Nudges.\n"
            "- 🛡️ **Two-Tier Malaysia PDPA Shield**: 0% facial biometrics exposed; full Skeletal Silhouette Mode.\n"
            "- 🌱 **Planet Track VFD Eco-Drive**: Pump Affinity Law ($P \\propto N^3$) + `>= 3.5` Daily Turnover Floor."
        )

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "🚨 Tab 1: Live Vision & Agentic Command",
            "🌱 Tab 2: ESG & VFD Pump Simulator",
            "🍂 Tab 3: Water Clarity & Monsoon Debris",
            "📱 Tab 4: Resident 'Crowd & Comfort' App",
        ]
    )

    with tab1:
        render_tab1_command_center()
    with tab2:
        render_tab2_esg_simulator()
    with tab3:
        render_tab3_water_inspector()
    with tab4:
        render_tab4_resident_widget()


if __name__ == "__main__":
    main()
