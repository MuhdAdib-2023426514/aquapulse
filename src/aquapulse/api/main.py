"""FastAPI application and unified runtime service for AquaPulse."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

import cv2
from fastapi import FastAPI
from pydantic import BaseModel, Field

from aquapulse.agent.reasoning import AgentReasoningLogger
from aquapulse.agent.state_machine import AquaPulseStateMachine
from aquapulse.agent.tools import PoolsideToolActuator
from aquapulse.api.calibration_routes import router as calibration_router
from aquapulse.api.video_routes import router as video_router
from aquapulse.config import DEFAULT_CONFIG, DEFAULT_DB_PATH, SYS1_MAX_LATENCY_MS
from aquapulse.db.database import (
    fetch_30d_esg_summary,
    fetch_hourly_telemetry,
    fetch_maintenance_tickets,
    fetch_recent_incidents,
    init_db,
)
from aquapulse.esg.forecaster import DiurnalCrowdForecaster
from aquapulse.esg.pump_optimizer import (
    compute_instantaneous_esg_metrics,
    generate_affinity_law_curve,
    optimize_24h_vfd_schedule,
)
from aquapulse.schemas import (
    PrivacyMode,
    ScenarioName,
    SwimmerTrack,
    ViolationType,
)
from aquapulse.vision.agentic_inspector import verify_attire_or_item
from aquapulse.vision.detector import AquaPulseVisionDetector
from aquapulse.vision.privacy import render_tier2_silhouette_frame
from aquapulse.vision.water_inspector import inspect_water_clarity


class StepVisionRequest(BaseModel):
    """Request payload for stepping the Vision + Dual-Path Agent pipeline."""

    scenario: ScenarioName = Field(default=ScenarioName.NORMAL_LAP_AND_FAMILY)
    dt_sec: float = Field(default=5.0, ge=0.0, le=120.0)
    target_elapsed_sec: float | None = Field(
        default=None,
        ge=0.0,
        le=300.0,
        description="Optional absolute elapsed timestamp to jump to (e.g., 0s, 5s, 8s, 15s, 30s)",
    )
    reset: bool = Field(default=False)
    privacy_mode: PrivacyMode = Field(default=PrivacyMode.SILHOUETTE)
    include_frames: bool = Field(
        default=False,
        description="When True, encode rendered vision frames as base64 JPEGs for frontend preview",
    )


class AquaPulseRuntimeService:
    """Orchestrates Vision, System 1/2 State Machine, ESG Optimizer, and SQLite persistence."""

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        self.conn = init_db(db_path, auto_seed=True)
        self.detector = AquaPulseVisionDetector()
        self.actuator = PoolsideToolActuator(db_conn=self.conn)
        self.reasoning_logger = AgentReasoningLogger()
        self.state_machine = AquaPulseStateMachine(
            config=DEFAULT_CONFIG,
            actuator=self.actuator,
            reasoning_logger=self.reasoning_logger,
        )
        self.forecaster = DiurnalCrowdForecaster(conn=self.conn)

        self.current_scenario: ScenarioName = ScenarioName.NORMAL_LAP_AND_FAMILY
        self.elapsed_sec: float = 0.0
        self.last_snapshot: dict[str, Any] | None = None

    def reset_simulation(
        self,
        scenario: ScenarioName = ScenarioName.NORMAL_LAP_AND_FAMILY,
    ) -> None:
        """Reset elapsed timer and per-track state machine timers."""
        self.current_scenario = scenario
        self.elapsed_sec = 0.0
        self.state_machine.reset()

    def step_simulation(
        self,
        *,
        scenario: ScenarioName = ScenarioName.NORMAL_LAP_AND_FAMILY,
        dt_sec: float = 5.0,
        target_elapsed_sec: float | None = None,
        reset: bool = False,
        privacy_mode: PrivacyMode = PrivacyMode.SILHOUETTE,
    ) -> dict[str, Any]:
        """Advance or jump simulation to a target time and return full telemetry + frames."""
        if reset or scenario != self.current_scenario:
            self.reset_simulation(scenario=scenario)

        if target_elapsed_sec is not None:
            # Replay deterministically from 0s so 5s/8s/15s/30s transitions fire
            self.reset_simulation(scenario=scenario)
            if target_elapsed_sec <= 0.0:
                dt_steps = [0.0]
            else:
                n_full = int(target_elapsed_sec // 5.0)
                rem = round(target_elapsed_sec - (n_full * 5.0), 3)
                dt_steps = [5.0] * n_full + ([rem] if rem > 0 else [])
        else:
            dt_steps = [dt_sec]

        raw_frame = None
        tracks: list[SwimmerTrack] = []
        objects = []
        sys1_trace = None
        sys2_inspections = []
        tool_logs = []
        thoughts = []
        roi_crops: dict[int, Any] = {}
        roi_inspections: dict[int, dict[str, Any]] = {}

        for step_dt in dt_steps:
            self.elapsed_sec = round(self.elapsed_sec + step_dt, 2)
            raw_frame, tracks, objects = self.detector.process_scenario(
                scenario=self.current_scenario,
                elapsed_sec=self.elapsed_sec,
            )

            def _verifier(
                tr: SwimmerTrack,
                cur_frame: Any = raw_frame,
                cur_objs: Any = objects,
            ) -> Any:
                res, zoomed = verify_attire_or_item(cur_frame, tr, cur_objs, allow_vlm=True)
                roi_crops[tr.track_id] = zoomed
                roi_inspections[tr.track_id] = res.model_dump()
                return res

            sys1_trace, step_sys2, step_tools, step_thoughts = self.state_machine.step(
                tracks=tracks,
                dt_sec=step_dt,
                objects=objects,
                roi_verifier=_verifier,
            )
            sys2_inspections.extend(step_sys2)
            tool_logs.extend(step_tools)
            thoughts.extend(step_thoughts)

        assert raw_frame is not None and sys1_trace is not None

        # Ensure any track with a suspected violation also has a live Tier-1 face-masked ROI preview
        for tr in tracks:
            if tr.suspected_violation != ViolationType.NONE and tr.track_id not in roi_crops:
                res_preview, zoomed_preview = verify_attire_or_item(
                    raw_frame, tr, objects, allow_vlm=True
                )
                roi_crops[tr.track_id] = zoomed_preview
                roi_inspections[tr.track_id] = res_preview.model_dump()

        silhouette_frame = render_tier2_silhouette_frame(
            tracks=tracks,
            objects=objects,
            overall_state=sys1_trace.overall_state,
        )
        water_report, annotated_water_frame = inspect_water_clarity(raw_frame)

        cotton_count = sum(
            1 for t in tracks if t.suspected_violation == ViolationType.COTTON_ATTIRE
        )
        food_count = sum(
            1 for t in tracks if t.suspected_violation == ViolationType.FOOD_DRINK_POOLSIDE
        )
        animal_count = sum(1 for o in objects if o.label in {"dog", "cat", "bird"})
        esg_metrics = compute_instantaneous_esg_metrics(
            bather_count=len(tracks),
            cotton_violations=cotton_count,
            food_drink_events=food_count,
            animal_events=animal_count,
        )
        resident_status = self.forecaster.build_resident_comfort_status(
            tracks=tracks,
            water_report=water_report,
        )

        snapshot = {
            "scenario": self.current_scenario.value,
            "elapsed_sec": self.elapsed_sec,
            "privacy_mode": privacy_mode.value,
            "tracks": [t.model_dump() for t in tracks],
            "detected_objects": [o.model_dump() for o in objects],
            "system1_trace": sys1_trace.model_dump(),
            "system2_inspections": [s.model_dump() for s in sys2_inspections],
            "tool_logs": [tl.model_dump(mode="json") for tl in tool_logs],
            "reasoning_thoughts": thoughts,
            "esg_metrics": esg_metrics.model_dump(),
            "water_report": water_report.model_dump(),
            "resident_comfort": resident_status.model_dump(),
            # In-memory numpy frames for direct Streamlit rendering
            "_frames": {
                "silhouette_bgr": silhouette_frame,
                "raw_bgr": raw_frame,
                "water_annotated_bgr": annotated_water_frame,
                "roi_crops_bgr": roi_crops,
                "roi_inspections": roi_inspections,
            },
        }
        self.last_snapshot = snapshot
        return snapshot


_RUNTIME_SERVICE: AquaPulseRuntimeService | None = None


def get_runtime_service() -> AquaPulseRuntimeService:
    """Return singleton `AquaPulseRuntimeService` instance."""
    global _RUNTIME_SERVICE
    if _RUNTIME_SERVICE is None:
        _RUNTIME_SERVICE = AquaPulseRuntimeService()
    return _RUNTIME_SERVICE


app = FastAPI(
    title="AquaPulse API — Privacy-First Agentic Vision & ESG Pool Monitoring",
    version="0.1.0",
    description=(
        "Sime Darby Property University Hackathon ('Township of Tomorrow') — "
        "Dual-Path System 1 (<30ms Life-Safety Reflex) & System 2 (Tier-1 Face-Masked ROI Governance) "
        "+ Bather-Load VFD Filtration Pump Eco-Drive."
    ),
)

app.include_router(video_router)
app.include_router(calibration_router)


@app.get("/health")
def health_check() -> dict[str, Any]:
    """Return backend health, 30-day SQLite row count, and System 1 latency budget."""
    svc = get_runtime_service()
    summary = fetch_30d_esg_summary(svc.conn)
    return {
        "status": "ok",
        "service": "aquapulse",
        "total_seeded_hours": summary["total_hours"],
        "current_scenario": svc.current_scenario.value,
        "elapsed_sec": svc.elapsed_sec,
        "system1_latency_budget_ms": SYS1_MAX_LATENCY_MS,
    }


@app.post("/api/v1/vision/step")
def api_vision_step(req: StepVisionRequest) -> dict[str, Any]:
    """Step the Vision + System 1/2 Agent simulation and return JSON telemetry."""
    svc = get_runtime_service()
    snap = svc.step_simulation(
        scenario=req.scenario,
        dt_sec=req.dt_sec,
        target_elapsed_sec=req.target_elapsed_sec,
        reset=req.reset,
        privacy_mode=req.privacy_mode,
    )
    output = {k: v for k, v in snap.items() if k != "_frames"}
    if req.include_frames and "_frames" in snap:
        frames_dict = snap["_frames"]
        encoded: dict[str, str] = {}
        for key in ("silhouette_bgr", "raw_bgr", "water_annotated_bgr"):
            if key in frames_dict and frames_dict[key] is not None:
                _, buf = cv2.imencode(".jpg", frames_dict[key], [cv2.IMWRITE_JPEG_QUALITY, 80])
                encoded[key] = f"data:image/jpeg;base64,{base64.b64encode(buf).decode('ascii')}"
        output["rendered_frames"] = encoded
    return output


@app.get("/api/v1/agent/state")
def api_agent_state() -> dict[str, Any]:
    """Return current System 1/2 state machine snapshot, reasoning logs, and SQLite incidents."""
    svc = get_runtime_service()
    if svc.last_snapshot is None:
        svc.step_simulation(scenario=ScenarioName.NORMAL_LAP_AND_FAMILY, dt_sec=0.0, reset=True)
    snap = svc.last_snapshot or {}
    return {
        "scenario": svc.current_scenario.value,
        "elapsed_sec": svc.elapsed_sec,
        "system1_trace": snap.get("system1_trace"),
        "system2_inspections": snap.get("system2_inspections", []),
        "recent_reasoning": svc.reasoning_logger.logs[-20:],
        "recent_incidents_db": fetch_recent_incidents(svc.conn, limit=15),
    }


@app.get("/api/v1/esg/summary")
def api_esg_summary() -> dict[str, Any]:
    """Return 30-day SQLite ESG savings, Pump Affinity Law curve, and 24-hour optimized schedule."""
    svc = get_runtime_service()
    summary_30d = fetch_30d_esg_summary(svc.conn)
    affinity_curve = generate_affinity_law_curve()
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
    schedule_24h = optimize_24h_vfd_schedule(typical_bathers)
    return {
        "summary_30d": summary_30d,
        "affinity_law_curve": affinity_curve,
        "schedule_24h": schedule_24h,
        "telemetry_recent_24h": fetch_hourly_telemetry(svc.conn, limit=24),
    }


@app.get("/api/v1/water/inspect")
def api_water_inspect(
    scenario: ScenarioName = ScenarioName.MONSOON_DEBRIS_AND_ALGAE,
) -> dict[str, Any]:
    """Run OpenCV water clarity & monsoon debris inspection and return JMB cleaner tickets."""
    svc = get_runtime_service()
    frame, _, _ = svc.detector.process_scenario(scenario=scenario, elapsed_sec=0.0)
    report, _ = inspect_water_clarity(frame)
    return {
        "scenario": scenario.value,
        "report": report.model_dump(),
        "maintenance_tickets": fetch_maintenance_tickets(svc.conn, limit=15),
    }


@app.get("/api/v1/resident/comfort")
def api_resident_comfort(day_of_week: int = 5) -> dict[str, Any]:
    """Return anonymous Resident 'Crowd & Comfort' widget status and 24h diurnal forecast."""
    svc = get_runtime_service()
    dow = max(0, min(6, day_of_week))
    if svc.last_snapshot is None:
        svc.step_simulation(scenario=ScenarioName.NORMAL_LAP_AND_FAMILY, dt_sec=0.0, reset=True)
    _, tracks, _ = svc.detector.process_scenario(
        scenario=svc.current_scenario,
        elapsed_sec=svc.elapsed_sec,
    )
    frame, _, _ = svc.detector.process_scenario(
        scenario=svc.current_scenario,
        elapsed_sec=svc.elapsed_sec,
    )
    water_rep, _ = inspect_water_clarity(frame)
    comfort = svc.forecaster.build_resident_comfort_status(
        tracks=tracks,
        water_report=water_rep,
        day_of_week=dow,
    )
    forecast_24h = svc.forecaster.predict_24h_profile(day_of_week=dow)
    return {
        "day_of_week": dow,
        "resident_comfort": comfort.model_dump(),
        "forecast_24h": forecast_24h,
    }


# ---------------------------------------------------------------------------
# Mount Vue 3 Production Frontend (Single-Page App)
# ---------------------------------------------------------------------------
_frontend_candidates = [
    Path(os.environ.get("AQUAPULSE_FRONTEND_DIST", "")),
    Path.cwd() / "frontend" / "dist",
    Path("/app/frontend/dist"),
    Path(__file__).resolve().parents[3] / "frontend" / "dist",
]
_frontend_dist = next((p for p in _frontend_candidates if p and p.exists() and (p / "index.html").exists()), None)
if _frontend_dist:
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
