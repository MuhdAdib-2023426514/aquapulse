"""SQLite connection, schema initialization, and query helpers for AquaPulse."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aquapulse.config import DEFAULT_DB_PATH
from aquapulse.schemas import (
    CalibrationProfile,
    CalibrationProfileCreate,
    CalibrationStatus,
    Camera,
    CameraCreate,
    Pool,
    PoolCreate,
)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS hourly_telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    day_index INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    hour INTEGER NOT NULL,
    is_weekend INTEGER NOT NULL,
    swimmer_count INTEGER NOT NULL,
    lap_swimmers INTEGER NOT NULL,
    family_swimmers INTEGER NOT NULL,
    toddler_count INTEGER NOT NULL,
    senior_count INTEGER NOT NULL,
    cotton_violations INTEGER NOT NULL,
    food_drink_events INTEGER NOT NULL,
    contamination_score REAL NOT NULL,
    vfd_speed_pct REAL NOT NULL,
    flow_rate_m3h REAL NOT NULL,
    fixed_pump_kwh REAL NOT NULL,
    vfd_pump_kwh REAL NOT NULL,
    kwh_saved REAL NOT NULL,
    rm_saved REAL NOT NULL,
    co2_saved_kg REAL NOT NULL,
    turbidity_score REAL NOT NULL,
    algae_green_index REAL NOT NULL,
    debris_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS incident_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    system_path TEXT NOT NULL,
    track_id INTEGER,
    event_type TEXT NOT NULL,
    agent_state TEXT NOT NULL,
    zone TEXT NOT NULL,
    duration_sec REAL NOT NULL,
    action_taken TEXT NOT NULL,
    pdpa_mode TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS maintenance_tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    ticket_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    turbidity_score REAL NOT NULL,
    algae_green_index REAL NOT NULL,
    debris_count INTEGER NOT NULL,
    status TEXT NOT NULL,
    assigned_to TEXT NOT NULL,
    notes TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pools (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    length_m REAL NOT NULL DEFAULT 25.0,
    width_m REAL NOT NULL DEFAULT 12.0,
    shallow_depth_m REAL NOT NULL DEFAULT 0.8,
    deep_depth_m REAL NOT NULL DEFAULT 1.8,
    depth_boundary_m REAL NOT NULL DEFAULT 12.5,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cameras (
    id TEXT PRIMARY KEY,
    pool_id TEXT NOT NULL,
    name TEXT NOT NULL,
    location_description TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(pool_id) REFERENCES pools(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS calibration_profiles (
    id TEXT PRIMARY KEY,
    pool_id TEXT NOT NULL,
    camera_id TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'draft',
    deep_end_side TEXT NOT NULL DEFAULT 'right',
    deck_margin_norm REAL NOT NULL DEFAULT 0.04,
    length_m REAL NOT NULL DEFAULT 25.0,
    width_m REAL NOT NULL DEFAULT 12.0,
    shallow_depth_m REAL NOT NULL DEFAULT 0.8,
    deep_depth_m REAL NOT NULL DEFAULT 1.8,
    depth_boundary_m REAL NOT NULL DEFAULT 12.5,
    corners_json TEXT NOT NULL,
    reference_frame_path TEXT,
    is_active INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(pool_id) REFERENCES pools(id) ON DELETE CASCADE,
    FOREIGN KEY(camera_id) REFERENCES cameras(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_hourly_telemetry_day ON hourly_telemetry(day_index, hour);
CREATE INDEX IF NOT EXISTS idx_hourly_telemetry_dow_hour ON hourly_telemetry(day_of_week, hour);
CREATE INDEX IF NOT EXISTS idx_cameras_pool_id ON cameras(pool_id);
CREATE INDEX IF NOT EXISTS idx_calibrations_camera_version ON calibration_profiles(camera_id, version);
CREATE INDEX IF NOT EXISTS idx_calibrations_camera_active ON calibration_profiles(camera_id, is_active);
"""


def get_connection(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Return a SQLite connection configured with Row factory and WAL mode."""
    path_str = str(db_path)
    if path_str != ":memory:":
        path_obj = Path(path_str)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path_str, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    if path_str != ":memory:":
        conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db(
    db_path: Path | str | sqlite3.Connection = DEFAULT_DB_PATH,
    auto_seed: bool = True,
) -> sqlite3.Connection:
    """Initialize SQLite tables and optionally seed 30 days (720 hours) if empty."""
    if isinstance(db_path, sqlite3.Connection):
        conn = db_path
    else:
        conn = get_connection(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()

    if auto_seed:
        from aquapulse.db.seed import seed_30_days_if_empty

        seed_30_days_if_empty(conn)
        seed_demo_pool_if_empty(conn)

    return conn


def fetch_hourly_telemetry(
    conn: sqlite3.Connection,
    limit: int = 720,
) -> list[dict[str, Any]]:
    """Fetch up to `limit` chronological rows from `hourly_telemetry`."""
    rows = conn.execute(
        """
        SELECT * FROM (
            SELECT * FROM hourly_telemetry ORDER BY id DESC LIMIT ?
        ) ORDER BY id ASC
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_30d_esg_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    """Compute aggregate 30-day ESG energy, TNB RM tariff, and CO2 savings metrics."""
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS total_hours,
            SUM(fixed_pump_kwh) AS total_fixed_kwh,
            SUM(vfd_pump_kwh) AS total_vfd_kwh,
            SUM(kwh_saved) AS total_kwh_saved,
            SUM(rm_saved) AS total_rm_saved,
            SUM(co2_saved_kg) AS total_co2_saved_kg,
            AVG(vfd_speed_pct) AS avg_vfd_speed_pct,
            SUM(flow_rate_m3h) AS total_volume_circulated_m3
        FROM hourly_telemetry
        """
    ).fetchone()

    if not row or not row["total_hours"]:
        return {
            "total_hours": 0,
            "total_fixed_kwh": 0.0,
            "total_vfd_kwh": 0.0,
            "total_kwh_saved": 0.0,
            "energy_reduction_pct": 0.0,
            "total_rm_saved": 0.0,
            "projected_annual_rm_saved": 0.0,
            "total_co2_saved_kg": 0.0,
            "projected_annual_co2_saved_kg": 0.0,
            "avg_daily_turnovers": 0.0,
            "min_daily_turnovers": 0.0,
        }

    total_fixed = float(row["total_fixed_kwh"] or 0.0)
    total_vfd = float(row["total_vfd_kwh"] or 0.0)
    total_saved = float(row["total_kwh_saved"] or 0.0)
    reduction_pct = (total_saved / total_fixed * 100.0) if total_fixed > 0 else 0.0

    daily_rows = conn.execute(
        """
        SELECT day_index, SUM(flow_rate_m3h) / 450.0 AS daily_turnovers
        FROM hourly_telemetry
        GROUP BY day_index
        """
    ).fetchall()
    turnovers = [float(r["daily_turnovers"]) for r in daily_rows] if daily_rows else [0.0]

    total_rm = float(row["total_rm_saved"] or 0.0)
    total_co2 = float(row["total_co2_saved_kg"] or 0.0)

    return {
        "total_hours": int(row["total_hours"]),
        "total_fixed_kwh": round(total_fixed, 2),
        "total_vfd_kwh": round(total_vfd, 2),
        "total_kwh_saved": round(total_saved, 2),
        "energy_reduction_pct": round(reduction_pct, 2),
        "total_rm_saved": round(total_rm, 2),
        "projected_annual_rm_saved": round(total_rm * (365.0 / 30.0), 2),
        "total_co2_saved_kg": round(total_co2, 2),
        "projected_annual_co2_saved_kg": round(total_co2 * (365.0 / 30.0), 2),
        "avg_daily_turnovers": round(sum(turnovers) / len(turnovers), 2),
        "min_daily_turnovers": round(min(turnovers), 2),
    }


def fetch_recent_incidents(
    conn: sqlite3.Connection,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Return recent System 1 & System 2 incident log entries."""
    rows = conn.execute(
        "SELECT * FROM incident_logs ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_maintenance_tickets(
    conn: sqlite3.Connection,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Return recent JMB/MC water clarity and monsoon debris cleaner tickets."""
    rows = conn.execute(
        "SELECT * FROM maintenance_tickets ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def insert_incident_log(
    conn: sqlite3.Connection,
    *,
    timestamp: str,
    system_path: str,
    track_id: int | None,
    event_type: str,
    agent_state: str,
    zone: str,
    duration_sec: float,
    action_taken: str,
    pdpa_mode: str = "SILHOUETTE",
) -> int:
    """Insert a new System 1 or System 2 incident log record and return its row ID."""
    cur = conn.execute(
        """
        INSERT INTO incident_logs (
            timestamp, system_path, track_id, event_type,
            agent_state, zone, duration_sec, action_taken, pdpa_mode
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp,
            system_path,
            track_id,
            event_type,
            agent_state,
            zone,
            duration_sec,
            action_taken,
            pdpa_mode,
        ),
    )
    conn.commit()
    return int(cur.lastrowid or 0)


def insert_maintenance_ticket(
    conn: sqlite3.Connection,
    *,
    timestamp: str,
    ticket_type: str,
    severity: str,
    turbidity_score: float,
    algae_green_index: float,
    debris_count: int,
    status: str = "OPEN",
    assigned_to: str = "JMB Pool Maintenance Team",
    notes: str = "",
) -> int:
    """Insert a new JMB cleaner/water maintenance ticket and return its row ID."""
    cur = conn.execute(
        """
        INSERT INTO maintenance_tickets (
            timestamp, ticket_type, severity, turbidity_score,
            algae_green_index, debris_count, status, assigned_to, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp,
            ticket_type,
            severity,
            turbidity_score,
            algae_green_index,
            debris_count,
            status,
            assigned_to,
            notes,
        ),
    )
    conn.commit()
    return int(cur.lastrowid or 0)


# =========================================================================
# Reusable Pool & Camera Calibration Infrastructure
# =========================================================================


def seed_demo_pool_if_empty(conn: sqlite3.Connection) -> None:
    """Seed the default AquaPulse Demo Pool and Main Pool CCTV calibration profile if empty."""
    row = conn.execute("SELECT COUNT(*) FROM pools").fetchone()
    if row and row[0] > 0:
        return

    now = datetime.now(UTC).isoformat()
    pool_id = "demo_pool_1"
    camera_id = "demo_camera_cctv_1"
    cal_id = "demo_calibration_v1"

    conn.execute(
        """
        INSERT INTO pools (id, name, length_m, width_m, shallow_depth_m, deep_depth_m, depth_boundary_m, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (pool_id, "AquaPulse Demo Pool", 25.0, 12.0, 0.8, 1.8, 12.5, now, now),
    )

    conn.execute(
        """
        INSERT INTO cameras (id, pool_id, name, location_description, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (camera_id, pool_id, "Main Pool CCTV", "Fixed overhead CCTV on North Gantry", 1, now, now),
    )

    corners = [(0.05, 0.15), (0.95, 0.15), (0.95, 0.85), (0.05, 0.85)]
    conn.execute(
        """
        INSERT INTO calibration_profiles (
            id, pool_id, camera_id, version, status, deep_end_side, deck_margin_norm,
            length_m, width_m, shallow_depth_m, deep_depth_m, depth_boundary_m,
            corners_json, reference_frame_path, is_active, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cal_id,
            pool_id,
            camera_id,
            1,
            "active",
            "right",
            0.04,
            25.0,
            12.0,
            0.8,
            1.8,
            12.5,
            json.dumps(corners),
            None,
            1,
            now,
            now,
        ),
    )
    conn.commit()


def create_pool(
    conn: sqlite3.Connection,
    pool_data: PoolCreate,
    pool_id: str | None = None,
) -> Pool:
    """Create a new swimming pool record."""
    pid = pool_id or pool_data.id or f"pool_{uuid.uuid4().hex[:8]}"
    now = datetime.now(UTC).isoformat()
    conn.execute(
        """
        INSERT INTO pools (id, name, length_m, width_m, shallow_depth_m, deep_depth_m, depth_boundary_m, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            pid,
            pool_data.name,
            pool_data.length_m,
            pool_data.width_m,
            pool_data.shallow_depth_m,
            pool_data.deep_depth_m,
            pool_data.depth_boundary_m,
            now,
            now,
        ),
    )
    conn.commit()
    return Pool(
        id=pid,
        name=pool_data.name,
        length_m=pool_data.length_m,
        width_m=pool_data.width_m,
        shallow_depth_m=pool_data.shallow_depth_m,
        deep_depth_m=pool_data.deep_depth_m,
        depth_boundary_m=pool_data.depth_boundary_m,
        created_at=now,
        updated_at=now,
    )


def get_pool(conn: sqlite3.Connection, pool_id: str) -> Pool | None:
    """Fetch a single pool by ID."""
    row = conn.execute("SELECT * FROM pools WHERE id = ?", (pool_id,)).fetchone()
    if not row:
        return None
    return Pool(
        id=row["id"],
        name=row["name"],
        length_m=float(row["length_m"]),
        width_m=float(row["width_m"]),
        shallow_depth_m=float(row["shallow_depth_m"]),
        deep_depth_m=float(row["deep_depth_m"]),
        depth_boundary_m=float(row["depth_boundary_m"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def list_pools(conn: sqlite3.Connection) -> list[Pool]:
    """List all registered pools ordered by creation date."""
    rows = conn.execute("SELECT * FROM pools ORDER BY created_at ASC").fetchall()
    return [
        Pool(
            id=r["id"],
            name=r["name"],
            length_m=float(r["length_m"]),
            width_m=float(r["width_m"]),
            shallow_depth_m=float(r["shallow_depth_m"]),
            deep_depth_m=float(r["deep_depth_m"]),
            depth_boundary_m=float(r["depth_boundary_m"]),
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
        for r in rows
    ]


def create_camera(
    conn: sqlite3.Connection,
    camera_data: CameraCreate,
    camera_id: str | None = None,
) -> Camera:
    """Register a new camera associated with a pool."""
    cid = camera_id or camera_data.id or f"cam_{uuid.uuid4().hex[:8]}"
    now = datetime.now(UTC).isoformat()
    conn.execute(
        """
        INSERT INTO cameras (id, pool_id, name, location_description, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cid,
            camera_data.pool_id,
            camera_data.name,
            camera_data.location_description,
            1 if camera_data.is_active else 0,
            now,
            now,
        ),
    )
    conn.commit()
    return Camera(
        id=cid,
        pool_id=camera_data.pool_id,
        name=camera_data.name,
        location_description=camera_data.location_description,
        is_active=camera_data.is_active,
        created_at=now,
        updated_at=now,
    )


def get_camera(conn: sqlite3.Connection, camera_id: str) -> Camera | None:
    """Fetch camera by ID including active calibration profile metadata."""
    row = conn.execute(
        """
        SELECT c.*, cp.id AS active_calibration_id, cp.version AS active_calibration_version
        FROM cameras c
        LEFT JOIN calibration_profiles cp ON cp.camera_id = c.id AND cp.is_active = 1
        WHERE c.id = ?
        """,
        (camera_id,),
    ).fetchone()
    if not row:
        return None
    return Camera(
        id=row["id"],
        pool_id=row["pool_id"],
        name=row["name"],
        location_description=row["location_description"],
        is_active=bool(row["is_active"]),
        active_calibration_id=row["active_calibration_id"],
        active_calibration_version=row["active_calibration_version"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def list_cameras(conn: sqlite3.Connection, pool_id: str | None = None) -> list[Camera]:
    """List cameras, optionally filtered by pool_id."""
    if pool_id:
        rows = conn.execute(
            """
            SELECT c.*, cp.id AS active_calibration_id, cp.version AS active_calibration_version
            FROM cameras c
            LEFT JOIN calibration_profiles cp ON cp.camera_id = c.id AND cp.is_active = 1
            WHERE c.pool_id = ?
            ORDER BY c.created_at ASC
            """,
            (pool_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT c.*, cp.id AS active_calibration_id, cp.version AS active_calibration_version
            FROM cameras c
            LEFT JOIN calibration_profiles cp ON cp.camera_id = c.id AND cp.is_active = 1
            ORDER BY c.created_at ASC
            """
        ).fetchall()

    return [
        Camera(
            id=r["id"],
            pool_id=r["pool_id"],
            name=r["name"],
            location_description=r["location_description"],
            is_active=bool(r["is_active"]),
            active_calibration_id=r["active_calibration_id"],
            active_calibration_version=r["active_calibration_version"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
        for r in rows
    ]


def _row_to_calibration_profile(row: sqlite3.Row) -> CalibrationProfile:
    corners = json.loads(row["corners_json"])
    pool_corners = [(float(pt[0]), float(pt[1])) for pt in corners]
    return CalibrationProfile(
        id=row["id"],
        pool_id=row["pool_id"],
        camera_id=row["camera_id"],
        version=int(row["version"]),
        status=CalibrationStatus(row["status"]),
        deep_end_side=row["deep_end_side"],
        deck_margin_norm=float(row["deck_margin_norm"]),
        length_m=float(row["length_m"]),
        width_m=float(row["width_m"]),
        shallow_depth_m=float(row["shallow_depth_m"]),
        deep_depth_m=float(row["deep_depth_m"]),
        depth_boundary_m=float(row["depth_boundary_m"]),
        pool_corners_norm=pool_corners,
        reference_frame_path=row["reference_frame_path"],
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create_calibration_profile(
    conn: sqlite3.Connection,
    data: CalibrationProfileCreate,
    profile_id: str | None = None,
) -> CalibrationProfile:
    """Create a new calibration profile in 'draft' status."""
    cal_id = profile_id or f"cal_{uuid.uuid4().hex[:10]}"
    now = datetime.now(UTC).isoformat()

    # Determine initial version for this camera
    max_ver_row = conn.execute(
        "SELECT MAX(version) FROM calibration_profiles WHERE camera_id = ?",
        (data.camera_id,),
    ).fetchone()
    version = (max_ver_row[0] or 0) + 1 if max_ver_row else 1

    conn.execute(
        """
        INSERT INTO calibration_profiles (
            id, pool_id, camera_id, version, status, deep_end_side, deck_margin_norm,
            length_m, width_m, shallow_depth_m, deep_depth_m, depth_boundary_m,
            corners_json, reference_frame_path, is_active, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cal_id,
            data.pool_id,
            data.camera_id,
            version,
            CalibrationStatus.DRAFT.value,
            data.deep_end_side,
            data.deck_margin_norm,
            data.length_m,
            data.width_m,
            data.shallow_depth_m,
            data.deep_depth_m,
            data.depth_boundary_m,
            json.dumps(data.pool_corners_norm),
            data.reference_frame_path,
            0,
            now,
            now,
        ),
    )
    conn.commit()
    profile = get_calibration_profile(conn, cal_id)
    if profile is None:
        raise RuntimeError("Failed to retrieve newly created calibration profile")
    return profile


def get_calibration_profile(
    conn: sqlite3.Connection,
    profile_id: str,
) -> CalibrationProfile | None:
    """Fetch calibration profile by ID."""
    row = conn.execute(
        "SELECT * FROM calibration_profiles WHERE id = ?",
        (profile_id,),
    ).fetchone()
    if not row:
        return None
    return _row_to_calibration_profile(row)


def get_active_calibration_for_camera(
    conn: sqlite3.Connection,
    camera_id: str,
) -> CalibrationProfile | None:
    """Fetch the currently active calibration profile for a camera."""
    row = conn.execute(
        "SELECT * FROM calibration_profiles WHERE camera_id = ? AND is_active = 1 LIMIT 1",
        (camera_id,),
    ).fetchone()
    if not row:
        return None
    return _row_to_calibration_profile(row)


def list_calibration_profiles(
    conn: sqlite3.Connection,
    camera_id: str | None = None,
    pool_id: str | None = None,
) -> list[CalibrationProfile]:
    """List calibration profiles, optionally filtered by camera_id or pool_id."""
    query = "SELECT * FROM calibration_profiles WHERE 1=1"
    params: list[Any] = []
    if camera_id:
        query += " AND camera_id = ?"
        params.append(camera_id)
    if pool_id:
        query += " AND pool_id = ?"
        params.append(pool_id)
    query += " ORDER BY camera_id, version DESC"

    rows = conn.execute(query, params).fetchall()
    return [_row_to_calibration_profile(r) for r in rows]


def update_calibration_profile(
    conn: sqlite3.Connection,
    profile_id: str,
    updates: dict[str, Any],
) -> CalibrationProfile | None:
    """Update fields on a calibration profile."""
    existing = get_calibration_profile(conn, profile_id)
    if not existing:
        return None

    allowed_fields = {
        "deep_end_side",
        "deck_margin_norm",
        "length_m",
        "width_m",
        "shallow_depth_m",
        "deep_depth_m",
        "depth_boundary_m",
        "reference_frame_path",
        "status",
    }
    set_clauses: list[str] = []
    params: list[Any] = []

    for field, val in updates.items():
        if field == "pool_corners_norm" and val is not None:
            set_clauses.append("corners_json = ?")
            params.append(json.dumps(val))
        elif field in allowed_fields and val is not None:
            set_clauses.append(f"{field} = ?")
            params.append(val)

    if not set_clauses:
        return existing

    set_clauses.append("updated_at = ?")
    params.append(datetime.now(UTC).isoformat())
    params.append(profile_id)

    conn.execute(
        f"UPDATE calibration_profiles SET {', '.join(set_clauses)} WHERE id = ?",
        params,
    )
    conn.commit()
    return get_calibration_profile(conn, profile_id)


def activate_calibration_profile(
    conn: sqlite3.Connection,
    profile_id: str,
) -> CalibrationProfile | None:
    """Activate a calibration profile after validating its geometry.

    Ensures only ONE profile per camera is marked active at any time.
    """
    profile = get_calibration_profile(conn, profile_id)
    if not profile:
        return None

    # Validate geometry prior to activation (FR-07: Never activate invalid geometry)
    from aquapulse.vision.calibration import PoolCalibration

    cal = PoolCalibration(
        pool_corners_norm=profile.pool_corners_norm,
        deep_end_side=profile.deep_end_side,
        deck_margin_norm=profile.deck_margin_norm,
        length_m=profile.length_m,
        width_m=profile.width_m,
        shallow_depth_m=profile.shallow_depth_m,
        deep_depth_m=profile.deep_depth_m,
        depth_boundary_m=profile.depth_boundary_m,
    )
    res = cal.validate_geometry()
    if not res.is_valid:
        raise ValueError(f"Cannot activate calibration profile: {', '.join(res.errors)}")

    now = datetime.now(UTC).isoformat()
    # Transactional activation: deactivate all versions for this camera, then activate target
    conn.execute(
        "UPDATE calibration_profiles SET is_active = 0, updated_at = ? WHERE camera_id = ?",
        (now, profile.camera_id),
    )
    conn.execute(
        "UPDATE calibration_profiles SET is_active = 1, status = ?, updated_at = ? WHERE id = ?",
        (CalibrationStatus.ACTIVE.value, now, profile_id),
    )
    conn.commit()
    return get_calibration_profile(conn, profile_id)


def create_calibration_version(
    conn: sqlite3.Connection,
    profile_id: str,
    new_params: dict[str, Any] | None = None,
) -> CalibrationProfile | None:
    """Create a revised version of an existing calibration profile without mutating history."""
    source = get_calibration_profile(conn, profile_id)
    if not source:
        return None

    params = new_params or {}
    new_id = f"cal_{uuid.uuid4().hex[:10]}"
    now = datetime.now(UTC).isoformat()

    max_ver_row = conn.execute(
        "SELECT MAX(version) FROM calibration_profiles WHERE camera_id = ?",
        (source.camera_id,),
    ).fetchone()
    next_version = ((max_ver_row[0] if max_ver_row else 0) or source.version) + 1

    corners = params.get("pool_corners_norm", source.pool_corners_norm)
    conn.execute(
        """
        INSERT INTO calibration_profiles (
            id, pool_id, camera_id, version, status, deep_end_side, deck_margin_norm,
            length_m, width_m, shallow_depth_m, deep_depth_m, depth_boundary_m,
            corners_json, reference_frame_path, is_active, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id,
            source.pool_id,
            source.camera_id,
            next_version,
            CalibrationStatus.DRAFT.value,
            params.get("deep_end_side", source.deep_end_side),
            params.get("deck_margin_norm", source.deck_margin_norm),
            params.get("length_m", source.length_m),
            params.get("width_m", source.width_m),
            params.get("shallow_depth_m", source.shallow_depth_m),
            params.get("deep_depth_m", source.deep_depth_m),
            params.get("depth_boundary_m", source.depth_boundary_m),
            json.dumps(corners),
            params.get("reference_frame_path", source.reference_frame_path),
            0,  # Drafts start inactive
            now,
            now,
        ),
    )
    conn.commit()
    return get_calibration_profile(conn, new_id)
