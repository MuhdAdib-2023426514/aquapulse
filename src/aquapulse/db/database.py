"""SQLite connection, schema initialization, and query helpers for AquaPulse."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from aquapulse.config import DEFAULT_DB_PATH

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

CREATE INDEX IF NOT EXISTS idx_hourly_telemetry_day ON hourly_telemetry(day_index, hour);
CREATE INDEX IF NOT EXISTS idx_hourly_telemetry_dow_hour ON hourly_telemetry(day_of_week, hour);
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
    db_path: Path | str = DEFAULT_DB_PATH,
    auto_seed: bool = True,
) -> sqlite3.Connection:
    """Initialize SQLite tables and optionally seed 30 days (720 hours) if empty."""
    conn = get_connection(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()

    if auto_seed:
        from aquapulse.db.seed import seed_30_days_if_empty

        seed_30_days_if_empty(conn)

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
