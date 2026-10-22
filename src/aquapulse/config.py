"""Centralized configuration constants for AquaPulse (`swimming_pool_monitoring_system`).

Aligned with Malaysian strata condominium pool standards, TNB commercial electricity
tariffs, Peninsular Malaysia grid carbon emission factors, and the Dual-Path System 1/2
agentic monitoring thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Automatically load environment variables from .env if present
try:
    from dotenv import load_dotenv

    _env_file = Path(__file__).resolve().parents[2] / ".env"
    if _env_file.exists():
        load_dotenv(_env_file)
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Project & Asset Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
ASSETS_DIR: Path = PROJECT_ROOT / "assets"
MODELS_DIR: Path = ASSETS_DIR / "models"
DEFAULT_DB_PATH: Path = ASSETS_DIR / "aquapulse.db"

# Pre-trained YOLO26 model weight filenames (stored in assets/models/ if downloaded)
YOLO26_POSE_MODEL_NAME: str = "yolo26n-pose.pt"
YOLO26_DETECT_MODEL_NAME: str = "yolo26n.pt"

# ---------------------------------------------------------------------------
# Physical Pool & VFD Filtration Pump Constants (25m x 12m Malaysian Condo Pool)
# ---------------------------------------------------------------------------
POOL_LENGTH_M: float = 25.0
POOL_WIDTH_M: float = 12.0
POOL_AVG_DEPTH_M: float = 1.5
POOL_VOLUME_M3: float = 450.0  # 25m * 12m * 1.5m = 450 m³

PUMP_RATED_KW: float = 5.5  # 100% Fixed-Speed filtration pump power (kW)
PUMP_RATED_FLOW_M3H: float = 85.0  # 85 m³/h at 100% speed -> 2,040 m³/day (4.53 turnovers/day)
VFD_ECO_MIN_PCT: float = 40.0  # 40% minimum speed during verified 0-occupancy eco-windows
VFD_PURGE_MAX_PCT: float = 100.0  # 100% high-filtration purge cycle after peak crowd surge
MIN_DAILY_TURNOVERS: float = 3.5  # Minimum daily water turnover floor (>= 3.5 turnovers/day)
MIN_DAILY_CIRCULATION_M3: float = POOL_VOLUME_M3 * MIN_DAILY_TURNOVERS  # 1,575.0 m³/day

# ---------------------------------------------------------------------------
# Malaysian ESG, TNB Tariff & Contamination Load Constants
# ---------------------------------------------------------------------------
TNB_TARIFF_RM_PER_KWH: float = 0.51  # TNB Commercial / Strata Common-Area Tariff (RM/kWh)
MY_GRID_KG_CO2_PER_KWH: float = 0.758  # Peninsular Malaysia grid emission factor (kg CO2/kWh)

# Biological & Contamination Load Score weights:
# Contamination Score = (Swimmer Count * Duration_Hours) + w1*(Cotton Violations) + w2*(Food/Drink Events) + w3*(Animal Events)
CONTAMINATION_W_COTTON: float = 2.5
CONTAMINATION_W_FOOD_DRINK: float = 3.0
CONTAMINATION_W_ANIMAL: float = 5.0

# ---------------------------------------------------------------------------
# System 1 (Fast Edge Reflex <30ms) & System 2 (Deliberative Agentic Vision)
# ---------------------------------------------------------------------------
SYS1_VERIFY_SEC: float = 10.0  # t = 10s motionless/submerged OR unaccompanied toddler near deep end
SYS1_CRITICAL_EMERGENCY_SEC: float = 20.0  # t = 20s confirmed distress -> siren + TTS + guard route
SYS1_SUPERVISION_RADIUS_M: float = 1.5  # Adult-to-toddler / bystander interaction radius (meters)
SYS1_MAX_LATENCY_MS: float = 30.0  # Hard real-time local execution budget (<30ms)

SYS2_NUDGE_REQUIRED_SEC: float = (
    15.0  # >15s continuous rule violation -> System 2 ROI verify -> TTS nudge
)
SYS2_GUARD_TICKET_NUDGE_COUNT: int = (
    2  # Open JMB/Guard ticket only after 2 consecutive ignored nudges
)
SYS2_TIMEOUT_SEC: float = 2.0  # Strict timeout for optional Gemini Vision before OpenCV fallback

# ---------------------------------------------------------------------------
# Pool Zone Geometry (640 x 360 Reference Frame Canvas & Physical Meter Bounds)
# ---------------------------------------------------------------------------
CANVAS_WIDTH_PX: int = 640
CANVAS_HEIGHT_PX: int = 360
DEEP_END_BOUNDARY_X_M: float = 12.5  # X >= 12.5m transitions from Zone A Shallow to Zone B Deep End
TODDLER_DEEP_BOUNDARY_BUFFER_M: float = (
    1.5  # Toddler within 1.5m of deep-end line triggers supervision check
)

ZONE_POLYGONS_PX: dict[str, list[tuple[int, int]]] = {
    "ZONE_A_SHALLOW": [(40, 60), (310, 60), (310, 300), (40, 300)],
    "ZONE_B_DEEP_END": [(310, 60), (600, 60), (600, 300), (310, 300)],
    "POOL_DECK": [(0, 0), (640, 0), (640, 360), (0, 360)],
}


@dataclass(frozen=True)
class PoolConfig:
    """Immutable configuration bundle for dependency injection and testing."""

    pool_length_m: float = POOL_LENGTH_M
    pool_width_m: float = POOL_WIDTH_M
    pool_avg_depth_m: float = POOL_AVG_DEPTH_M
    pool_volume_m3: float = POOL_VOLUME_M3
    pump_rated_kw: float = PUMP_RATED_KW
    pump_rated_flow_m3h: float = PUMP_RATED_FLOW_M3H
    vfd_eco_min_pct: float = VFD_ECO_MIN_PCT
    vfd_purge_max_pct: float = VFD_PURGE_MAX_PCT
    min_daily_turnovers: float = MIN_DAILY_TURNOVERS
    tnb_tariff_rm_per_kwh: float = TNB_TARIFF_RM_PER_KWH
    my_grid_kg_co2_per_kwh: float = MY_GRID_KG_CO2_PER_KWH
    contamination_w_cotton: float = CONTAMINATION_W_COTTON
    contamination_w_food_drink: float = CONTAMINATION_W_FOOD_DRINK
    contamination_w_animal: float = CONTAMINATION_W_ANIMAL
    sys1_verify_sec: float = SYS1_VERIFY_SEC
    sys1_critical_emergency_sec: float = SYS1_CRITICAL_EMERGENCY_SEC
    sys1_supervision_radius_m: float = SYS1_SUPERVISION_RADIUS_M
    sys1_max_latency_ms: float = SYS1_MAX_LATENCY_MS
    sys2_nudge_required_sec: float = SYS2_NUDGE_REQUIRED_SEC
    sys2_guard_ticket_nudge_count: int = SYS2_GUARD_TICKET_NUDGE_COUNT
    sys2_timeout_sec: float = SYS2_TIMEOUT_SEC


DEFAULT_CONFIG = PoolConfig()
