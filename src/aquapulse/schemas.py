"""Pydantic v2 data contracts for AquaPulse Vision, System 1/2 Agent, ESG, and API layers."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class PoolZone(StrEnum):
    """Designated pool monitoring zones in a Malaysian strata condominium pool."""

    ZONE_A_SHALLOW = "ZONE_A_SHALLOW"
    ZONE_B_DEEP_END = "ZONE_B_DEEP_END"
    POOL_DECK = "POOL_DECK"


class SwimmerRole(StrEnum):
    """Anonymous demographic/activity profile derived from pose scale & trajectory."""

    ADULT = "ADULT"
    TODDLER = "TODDLER"
    SENIOR = "SENIOR"
    LAP_SWIMMER = "LAP_SWIMMER"


class PostureState(StrEnum):
    """Skeletal posture state extracted from 17 COCO keypoints."""

    ACTIVE_SWIM = "ACTIVE_SWIM"
    VERTICAL_TREADING = "VERTICAL_TREADING"
    ACTIVE_FLAILING = "ACTIVE_FLAILING"
    HORIZONTAL_SUBMERGED = "HORIZONTAL_SUBMERGED"
    DECK_STANDING = "DECK_STANDING"
    DECK_LOUNGING = "DECK_LOUNGING"


class AgentState(StrEnum):
    """Stateful escalation states across System 1 (Life Safety) and System 2 (Governance)."""

    NORMAL = "NORMAL"
    VERIFY = "VERIFY"
    CRITICAL_EMERGENCY = "CRITICAL_EMERGENCY"
    NUDGE_REQUIRED = "NUDGE_REQUIRED"
    ESCALATED_GUARD_TICKET = "ESCALATED_GUARD_TICKET"


class ViolationType(StrEnum):
    """Strata pool by-law governance violation categories."""

    NONE = "NONE"
    COTTON_ATTIRE = "COTTON_ATTIRE"
    FOOD_DRINK_POOLSIDE = "FOOD_DRINK_POOLSIDE"
    SMOKING_VAPING = "SMOKING_VAPING"
    PET_OR_STRAY_ANIMAL = "PET_OR_STRAY_ANIMAL"


class PrivacyMode(StrEnum):
    """Two-Tier Malaysia PDPA 2010 & PDPA (Amendment) Act 2024 redaction modes."""

    SILHOUETTE = "SILHOUETTE"
    TIER1_FACE_MASKED = "TIER1_FACE_MASKED"


class ScenarioName(StrEnum):
    """Deterministic pitch scenario triggers controllable from Streamlit & FastAPI."""

    NORMAL_LAP_AND_FAMILY = "NORMAL_LAP_AND_FAMILY"
    SILENT_DROWNING_RESCUE = "SILENT_DROWNING_RESCUE"
    UNACCOMPANIED_TODDLER_DEEP_END = "UNACCOMPANIED_TODDLER_DEEP_END"
    COTTON_TSHIRT_AND_FOOD_NUDGE = "COTTON_TSHIRT_AND_FOOD_NUDGE"
    PET_AND_STRAY_ANIMAL_POOL = "PET_AND_STRAY_ANIMAL_POOL"
    MONSOON_DEBRIS_AND_ALGAE = "MONSOON_DEBRIS_AND_ALGAE"
    PEAK_CROWD_SURGE_ECO_DRIVE = "PEAK_CROWD_SURGE_ECO_DRIVE"


class Keypoint2D(BaseModel):
    """Single 2D COCO skeletal keypoint in pixel coordinates."""

    x: float = Field(..., description="Pixel X coordinate on 640x360 canvas")
    y: float = Field(..., description="Pixel Y coordinate on 640x360 canvas")
    conf: float = Field(default=0.95, ge=0.0, le=1.0, description="Keypoint confidence score")


class SwimmerTrack(BaseModel):
    """Persistent tracked person (`track_id`) with 17 COCO keypoints and pool coordinates."""

    track_id: int = Field(..., ge=1, description="Persistent multi-target tracking ID")
    role: SwimmerRole = Field(default=SwimmerRole.ADULT)
    zone: PoolZone = Field(default=PoolZone.ZONE_A_SHALLOW)
    posture: PostureState = Field(default=PostureState.ACTIVE_SWIM)
    bbox: tuple[int, int, int, int] = Field(
        ..., description="(x1, y1, x2, y2) bounding box in pixel coordinates"
    )
    pool_coords_m: tuple[float, float] = Field(
        ..., description="(x_m, y_m) physical pool coordinates in meters (25m x 12m)"
    )
    keypoints: list[Keypoint2D] = Field(
        default_factory=list,
        description="17 COCO keypoints; indices 0..4 (nose, eyes, ears) define Tier-1 face mask",
    )
    is_flailing: bool = Field(
        default=False,
        description="True when swimmer exhibits active surface distress / flailing",
    )
    is_submerged: bool = Field(
        default=False, description="True when swimmer is motionless & submerged"
    )
    near_deep_boundary: bool = Field(
        default=False,
        description="True when toddler/infant is within 1.5m of Zone B deep-end boundary",
    )
    suspected_violation: ViolationType = Field(default=ViolationType.NONE)
    detected_violations: list[ViolationType] = Field(
        default_factory=list,
        description="All suspected/verified rule violations active for this track",
    )


class DetectedObject(BaseModel):
    """Poolside or surface object detected by YOLO26 / OpenCV contour analysis."""

    label: str = Field(
        ..., description="COCO class or debris type (e.g., bottle, cup, leaf_debris)"
    )
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    bbox: tuple[int, int, int, int] = Field(..., description="(x1, y1, x2, y2) pixel bounding box")
    zone: PoolZone = Field(default=PoolZone.POOL_DECK)


class UnattendedObjectTrack(BaseModel):
    """Stationary poolside object (drink, food, vape) tracked over time on pool coping."""

    object_id: str = Field(..., description="Unique ID for tracked stationary object")
    label: str = Field(..., description="Object label (e.g., bottle, cup, bowl, vape)")
    bbox: tuple[int, int, int, int] = Field(..., description="(x1, y1, x2, y2) bounding box")
    pool_coords_m: tuple[float, float] = Field(
        default=(0.0, 0.0), description="Physical coordinates (x_m, y_m)"
    )
    zone: PoolZone = Field(default=PoolZone.POOL_DECK)
    unattended_sec: float = Field(default=0.0, ge=0.0)
    associated_track_id: int | None = Field(default=None)
    is_hazard: bool = Field(default=False)
    nudge_sent: bool = Field(default=False)
    ticket_dispatched: bool = Field(default=False)


class TrackTemporalState(BaseModel):
    """Per-`track_id` temporal state maintained by `state_machine.py` across ticks."""

    track_id: int = Field(..., ge=1)
    role: SwimmerRole = Field(default=SwimmerRole.ADULT)
    zone: PoolZone = Field(default=PoolZone.ZONE_A_SHALLOW)
    submersion_sec: float = Field(default=0.0, ge=0.0)
    is_flailing: bool = Field(default=False)
    is_submerged: bool = Field(default=False)
    unaccompanied_infant_sec: float = Field(default=0.0, ge=0.0)
    violation_sec: float = Field(default=0.0, ge=0.0)
    nearest_adult_m: float | None = Field(default=None)
    is_supervised: bool = Field(default=True)
    violation_type: ViolationType = Field(default=ViolationType.NONE)
    system2_verified: bool = Field(default=False)
    nudge_count: int = Field(default=0, ge=0)
    agent_state: AgentState = Field(default=AgentState.NORMAL)
    last_vlm_call_t: float = Field(
        default=-999.0, description="Timestamp of last background VLM query"
    )
    vlm_in_flight: bool = Field(
        default=False, description="True if a background VLM query is currently in flight"
    )


class System1ReflexTrace(BaseModel):
    """Telemetry from System 1 Fast Edge Reflex (<30ms synchronous life-safety loop)."""

    execution_latency_ms: float = Field(
        ...,
        ge=0.0,
        description="Measured synchronous execution time in milliseconds (<30ms target)",
    )
    within_latency_budget: bool = Field(
        default=True, description="True if execution_latency_ms < 30.0ms"
    )
    overall_state: AgentState = Field(default=AgentState.NORMAL)
    tracks_evaluated: int = Field(default=0, ge=0)
    active_alerts: list[str] = Field(default_factory=list)
    track_states: list[TrackTemporalState] = Field(default_factory=list)
    unattended_objects: list[UnattendedObjectTrack] = Field(default_factory=list)


class GeminiVLMInspectionSchema(BaseModel):
    """Structured JSON schema returned by Gemini VLM Agentic Vision Judge."""

    verified_violation: bool = Field(
        default=False,
        description="True if the cropped ROI shows any pool rule violation",
    )
    primary_violation: ViolationType = Field(
        default=ViolationType.NONE,
        description="Primary rule violation detected in the ROI",
    )
    detected_violations: list[ViolationType] = Field(
        default_factory=list,
        description="All rule violations visible in the ROI (e.g. FOOD_DRINK_POOLSIDE, SMOKING_VAPING, COTTON_ATTIRE)",
    )
    wearing_cotton: bool = Field(
        default=False,
        description="True if the person is wearing a cotton t-shirt or street clothing instead of swimwear",
    )
    bringing_food_or_drink: bool = Field(
        default=False,
        description="True if food bowls, snacks, bottles, or drink cups are present poolside",
    )
    smoking_or_vaping: bool = Field(
        default=False,
        description="True if the person is holding a vape/e-cigarette/cigarette or exhaling vapor/smoke",
    )
    confidence: float = Field(default=0.95, ge=0.0, le=1.0)
    reasoning_summary: str = Field(
        default="",
        description="Concise 1-2 sentence visual judgment explaining all detected violations.",
    )


class System2InspectionResult(BaseModel):
    """Result from System 2 Deliberative Agentic Vision (Tier-1 Face-Masked ROI Inspector)."""

    track_id: int | None = Field(default=None)
    target_type: str = Field(..., description="Attire, food/drink, smoking, or water surface ROI")
    tier1_face_redacted: bool = Field(
        default=True,
        description="Must be True: keypoints 0..4 redacted before ROI inspection",
    )
    verified_violation: bool = Field(default=False)
    violation_type: ViolationType = Field(default=ViolationType.NONE)
    detected_violations: list[ViolationType] = Field(
        default_factory=list,
        description="All verified rule violations in this ROI crop",
    )
    confidence: float = Field(default=0.92, ge=0.0, le=1.0)
    inspector_backend: Literal["opencv_heuristic", "gemini_3.8_flash"] = Field(
        default="opencv_heuristic"
    )
    vlm_used: bool = Field(
        default=False,
        description="True when Gemini VLM was invoked on the Tier-1 face-masked ROI",
    )
    visual_tool_steps: list[str] = Field(
        default_factory=list,
        description="Ordered trace of visual tools executed during System 2 inspection",
    )
    reasoning_summary: str = Field(...)
    inspection_latency_ms: float = Field(default=12.0, ge=0.0)


class ToolExecutionLog(BaseModel):
    """Autonomous tool actuation record (Strobe, Directional TTS Speaker, Guard Dispatch, Cleaner)."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tool_name: str = Field(...)
    system_path: Literal["SYSTEM_1", "SYSTEM_2"] = Field(...)
    zone: PoolZone = Field(...)
    track_id: int | None = Field(default=None)
    message: str = Field(...)
    audio_tts_text: str | None = Field(default=None)
    guard_route_hint: str | None = Field(default=None)


class WaterClarityReport(BaseModel):
    """Visual water clarity & monsoon storm debris analysis report."""

    turbidity_score: float = Field(
        ..., ge=0.0, le=100.0, description="0-100 clarity index (higher is clearer)"
    )
    algae_green_index: float = Field(
        ..., ge=0.0, le=100.0, description="HSV green-channel drift index (warning if > 35.0)"
    )
    floating_debris_count: int = Field(..., ge=0)
    status: Literal[
        "CRYSTAL_CLEAR",
        "SLIGHT_TURBIDITY",
        "ALGAE_WARNING",
        "MONSOON_DEBRIS_ALERT",
    ] = Field(default="CRYSTAL_CLEAR")
    cleaner_ticket_opened: bool = Field(default=False)
    recommended_action: str = Field(default="No maintenance required; water clarity optimal.")


class ESGPumpMetrics(BaseModel):
    """Real-time Planet Track VFD filtration pump & TNB electricity/carbon savings metrics."""

    bather_count: int = Field(..., ge=0)
    cotton_violations: int = Field(default=0, ge=0)
    food_drink_events: int = Field(default=0, ge=0)
    animal_events: int = Field(default=0, ge=0)
    contamination_score: float = Field(..., ge=0.0)
    recommended_vfd_speed_pct: float = Field(..., ge=40.0, le=100.0)
    flow_rate_m3h: float = Field(..., ge=0.0)
    fixed_pump_kw: float = Field(..., ge=0.0)
    vfd_pump_kw: float = Field(..., ge=0.0)
    hourly_kwh_saved: float = Field(..., ge=0.0)
    hourly_rm_saved: float = Field(..., ge=0.0)
    hourly_co2_saved_kg: float = Field(..., ge=0.0)
    projected_daily_turnovers: float = Field(..., ge=0.0)
    turnover_floor_compliant: bool = Field(
        default=True, description="True when projected_daily_turnovers >= 3.5"
    )


class ResidentComfortStatus(BaseModel):
    """Anonymous live payload for the Resident Township App 'Crowd & Comfort' widget."""

    live_headcount: int = Field(..., ge=0)
    crowd_level: Literal["QUIET", "MODERATE", "BUSY"] = Field(...)
    lap_swimmers: int = Field(default=0, ge=0)
    family_swimmers: int = Field(default=0, ge=0)
    toddler_count: int = Field(default=0, ge=0)
    senior_count: int = Field(default=0, ge=0)
    water_clarity_label: str = Field(default="Crystal Clear (96/100)")
    recommended_quiet_hours: list[str] = Field(default_factory=list)
    senior_toddler_safe_window: str = Field(
        default="08:30 – 10:30 AM (Calm Shallow Zone & Low Lap Traffic)"
    )
