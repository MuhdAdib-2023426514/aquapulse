"""Deterministic 30-day (720-hour) Malaysian strata condo pool telemetry seeder."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import numpy as np

from aquapulse.config import (
    CONTAMINATION_W_COTTON,
    CONTAMINATION_W_FOOD_DRINK,
    MIN_DAILY_CIRCULATION_M3,
    MY_GRID_KG_CO2_PER_KWH,
    PUMP_RATED_FLOW_M3H,
    PUMP_RATED_KW,
    TNB_TARIFF_RM_PER_KWH,
    VFD_ECO_MIN_PCT,
    VFD_PURGE_MAX_PCT,
)

MONSOON_STORM_DAYS = {6, 15, 23}  # 0-indexed days (Days 7, 16, and 24 of the 30-day window)


def seed_30_days_if_empty(conn: sqlite3.Connection, seed: int = 42) -> bool:
    """Populate `hourly_telemetry`, `incident_logs`, and `maintenance_tickets` if empty.

    Returns True if seeding was performed, or False if data was already present.
    """
    existing_count = conn.execute("SELECT COUNT(*) FROM hourly_telemetry").fetchone()[0]
    if existing_count > 0:
        return False

    rng = np.random.default_rng(seed)
    base_start = datetime(2026, 9, 18, 0, 0, 0, tzinfo=UTC)

    telemetry_rows: list[tuple] = []

    for day_idx in range(30):
        day_dt = base_start + timedelta(days=day_idx)
        day_of_week = day_dt.weekday()  # 0=Mon .. 6=Sun
        is_weekend = 1 if day_of_week >= 5 else 0
        is_monsoon_day = day_idx in MONSOON_STORM_DAYS

        day_drafts: list[dict] = []
        prev_contamination = 0.0

        for hour in range(24):
            ts_str = (day_dt + timedelta(hours=hour)).isoformat()

            # 1. Realistic Malaysian strata condo hourly swimmer profile
            if 0 <= hour <= 5 or hour >= 22:
                swimmer_count = 0
                lap_swimmers = 0
                family_swimmers = 0
                toddler_count = 0
                senior_count = 0
                cotton_violations = 0
                food_drink_events = 0
            elif 6 <= hour <= 8:
                base = int(rng.integers(6, 13)) if not is_weekend else int(rng.integers(8, 16))
                swimmer_count = base
                lap_swimmers = max(1, int(round(base * 0.65)))
                senior_count = max(0, int(round(base * 0.20)))
                family_swimmers = max(0, base - lap_swimmers - senior_count)
                toddler_count = 1 if is_weekend and base >= 10 else 0
                cotton_violations = 1 if (is_weekend and rng.random() < 0.20) else 0
                food_drink_events = 0
            elif 9 <= hour <= 11:
                if is_weekend:
                    base = int(rng.integers(14, 25))
                    lap_swimmers = int(round(base * 0.20))
                    toddler_count = int(round(base * 0.22))
                    senior_count = int(round(base * 0.12))
                    family_swimmers = max(0, base - lap_swimmers - toddler_count - senior_count)
                    cotton_violations = int(rng.integers(0, 3))
                    food_drink_events = int(rng.integers(0, 2))
                else:
                    base = int(rng.integers(2, 6))
                    lap_swimmers = 1
                    senior_count = max(1, base - 2)
                    toddler_count = 1 if base >= 4 else 0
                    family_swimmers = max(0, base - lap_swimmers - senior_count - toddler_count)
                    cotton_violations = 0
                    food_drink_events = 0
                swimmer_count = base
            elif 12 <= hour <= 15:
                # Midday tropical UV lull
                base = int(rng.integers(0, 4)) if not is_weekend else int(rng.integers(3, 9))
                swimmer_count = base
                lap_swimmers = min(base, 1)
                family_swimmers = max(0, base - lap_swimmers)
                toddler_count = 0
                senior_count = 0
                cotton_violations = 1 if (base >= 5 and rng.random() < 0.25) else 0
                food_drink_events = 1 if (base >= 4 and rng.random() < 0.25) else 0
            elif 16 <= hour <= 20:
                # Afternoon / evening peak
                base = int(rng.integers(10, 19)) if not is_weekend else int(rng.integers(16, 28))
                swimmer_count = base
                lap_swimmers = int(round(base * 0.35))
                toddler_count = int(round(base * 0.18))
                senior_count = int(round(base * 0.08))
                family_swimmers = max(0, base - lap_swimmers - toddler_count - senior_count)
                cotton_violations = 1 if rng.random() < (0.45 if is_weekend else 0.25) else 0
                food_drink_events = 1 if rng.random() < (0.40 if is_weekend else 0.20) else 0
            else:
                # 21:00 wind-down hour
                base = int(rng.integers(2, 6))
                swimmer_count = base
                lap_swimmers = max(1, base - 1)
                family_swimmers = max(0, base - lap_swimmers)
                toddler_count = 0
                senior_count = 0
                cotton_violations = 0
                food_drink_events = 0

            # 2. Biological & Contamination Load Score
            contamination_score = round(
                float(swimmer_count)
                + CONTAMINATION_W_COTTON * float(cotton_violations)
                + CONTAMINATION_W_FOOD_DRINK * float(food_drink_events),
                2,
            )

            # 3. Initial VFD speed selection before daily turnover floor check
            if swimmer_count == 0 and prev_contamination < 12.0:
                if 0 <= hour <= 4:
                    vfd_speed_pct = VFD_ECO_MIN_PCT  # 40% deep-night eco mode
                else:
                    vfd_speed_pct = 72.0  # Low-power baseline circulation
            elif prev_contamination >= 18.0 and swimmer_count <= 6:
                # Post-peak high-filtration purge cycle
                vfd_speed_pct = VFD_PURGE_MAX_PCT
            elif contamination_score >= 20.0:
                vfd_speed_pct = 98.0
            elif contamination_score >= 12.0:
                vfd_speed_pct = 90.0
            elif contamination_score >= 5.0:
                vfd_speed_pct = 82.0
            else:
                vfd_speed_pct = 75.0

            prev_contamination = contamination_score

            # 4. Water Clarity & Monsoon Debris metrics
            if is_monsoon_day and 14 <= hour <= 20:
                debris_count = int(rng.integers(14, 24))
                turbidity_score = round(float(rng.uniform(72.0, 81.0)), 1)
                algae_green_index = round(float(rng.uniform(36.0, 44.0)), 1)
            else:
                debris_count = int(rng.integers(0, 3))
                turbidity_score = round(
                    float(rng.uniform(91.0, 98.5)) - 0.15 * min(swimmer_count, 20),
                    1,
                )
                algae_green_index = round(float(rng.uniform(14.0, 24.0)), 1)

            day_drafts.append(
                {
                    "timestamp": ts_str,
                    "day_index": day_idx,
                    "day_of_week": day_of_week,
                    "hour": hour,
                    "is_weekend": is_weekend,
                    "swimmer_count": swimmer_count,
                    "lap_swimmers": lap_swimmers,
                    "family_swimmers": family_swimmers,
                    "toddler_count": toddler_count,
                    "senior_count": senior_count,
                    "cotton_violations": cotton_violations,
                    "food_drink_events": food_drink_events,
                    "contamination_score": contamination_score,
                    "vfd_speed_pct": vfd_speed_pct,
                    "turbidity_score": turbidity_score,
                    "algae_green_index": algae_green_index,
                    "debris_count": debris_count,
                }
            )

        # 5. Enforce Minimum Daily Turnover Floor (>= 3.5 turnovers/day = 1,575 m³/day)
        # while preserving 40% eco-mode windows during deep night (hours 0..3)
        daily_flow = sum(PUMP_RATED_FLOW_M3H * (d["vfd_speed_pct"] / 100.0) for d in day_drafts)
        if daily_flow < MIN_DAILY_CIRCULATION_M3:
            deficit_m3 = MIN_DAILY_CIRCULATION_M3 - daily_flow + 15.0  # safety margin above 3.5x
            adjustable = [d for d in day_drafts if d["hour"] >= 4 and d["vfd_speed_pct"] < 96.0]
            if adjustable:
                pct_bump = (deficit_m3 / len(adjustable)) / PUMP_RATED_FLOW_M3H * 100.0
                for d in adjustable:
                    d["vfd_speed_pct"] = min(100.0, round(d["vfd_speed_pct"] + pct_bump, 1))

        # 6. Compute Pump Affinity Law (P2 = P1 * (N2/N1)^3), kWh, RM, and CO2 savings
        for d in day_drafts:
            speed_ratio = d["vfd_speed_pct"] / 100.0
            flow_rate_m3h = round(PUMP_RATED_FLOW_M3H * speed_ratio, 2)
            fixed_kwh = round(PUMP_RATED_KW, 3)
            vfd_kwh = round(PUMP_RATED_KW * (speed_ratio**3), 3)
            kwh_saved = round(max(0.0, fixed_kwh - vfd_kwh), 3)
            rm_saved = round(kwh_saved * TNB_TARIFF_RM_PER_KWH, 3)
            co2_saved_kg = round(kwh_saved * MY_GRID_KG_CO2_PER_KWH, 3)

            telemetry_rows.append(
                (
                    d["timestamp"],
                    d["day_index"],
                    d["day_of_week"],
                    d["hour"],
                    d["is_weekend"],
                    d["swimmer_count"],
                    d["lap_swimmers"],
                    d["family_swimmers"],
                    d["toddler_count"],
                    d["senior_count"],
                    d["cotton_violations"],
                    d["food_drink_events"],
                    d["contamination_score"],
                    d["vfd_speed_pct"],
                    flow_rate_m3h,
                    fixed_kwh,
                    vfd_kwh,
                    kwh_saved,
                    rm_saved,
                    co2_saved_kg,
                    d["turbidity_score"],
                    d["algae_green_index"],
                    d["debris_count"],
                )
            )

    conn.executemany(
        """
        INSERT INTO hourly_telemetry (
            timestamp, day_index, day_of_week, hour, is_weekend,
            swimmer_count, lap_swimmers, family_swimmers, toddler_count, senior_count,
            cotton_violations, food_drink_events, contamination_score,
            vfd_speed_pct, flow_rate_m3h, fixed_pump_kwh, vfd_pump_kwh,
            kwh_saved, rm_saved, co2_saved_kg,
            turbidity_score, algae_green_index, debris_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        telemetry_rows,
    )

    # Seed representative historical incident logs (System 1 & System 2)
    incident_rows = [
        (
            (base_start + timedelta(days=5, hours=17, minutes=20)).isoformat(),
            "SYSTEM_2",
            104,
            "COTTON_ATTIRE",
            "NUDGE_REQUIRED",
            "ZONE_A_SHALLOW",
            16.5,
            "Tier-1 face-masked ROI verified opaque cotton t-shirt; played polite directional speaker audio nudge. Resident complied.",
            "SILHOUETTE",
        ),
        (
            (base_start + timedelta(days=12, hours=10, minutes=45)).isoformat(),
            "SYSTEM_1",
            209,
            "UNACCOMPANIED_TODDLER_NEAR_DEEP_END",
            "VERIFY",
            "ZONE_A_SHALLOW",
            10.2,
            "System 1 (<30ms) flagged toddler within 1.2m of deep-end line; yellow caution beacon flashed; parent re-entered 1.5m supervision radius at t=12.4s.",
            "SILHOUETTE",
        ),
        (
            (base_start + timedelta(days=19, hours=18, minutes=10)).isoformat(),
            "SYSTEM_2",
            312,
            "FOOD_DRINK_POOLSIDE",
            "NUDGE_REQUIRED",
            "POOL_DECK",
            18.0,
            "Tier-1 face-masked ROI verified poolside beverage containers; played polite directional voice reminder.",
            "SILHOUETTE",
        ),
        (
            (base_start + timedelta(days=26, hours=16, minutes=5)).isoformat(),
            "SYSTEM_1",
            418,
            "SILENT_SUBMERSION_DRILL",
            "CRITICAL_EMERGENCY",
            "ZONE_B_DEEP_END",
            20.1,
            "System 1 (<30ms) triggered poolside siren + directional TTS broadcast at t=20.0s and dispatched fastest Gate 2 entry map to Guardhouse smartphone.",
            "SILHOUETTE",
        ),
    ]
    conn.executemany(
        """
        INSERT INTO incident_logs (
            timestamp, system_path, track_id, event_type,
            agent_state, zone, duration_sec, action_taken, pdpa_mode
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        incident_rows,
    )

    # Seed 3 Tropical Monsoon Storm Debris & Algae Warning tickets (Days 7, 16, 24)
    ticket_rows = [
        (
            (base_start + timedelta(days=6, hours=15)).isoformat(),
            "MONSOON_DEBRIS_ALERT",
            "HIGH",
            76.4,
            38.2,
            19,
            "RESOLVED",
            "JMB Morning Pool Cleaning Crew",
            "Post-monsoon storm surface leaves/twigs detected (19 contours) + slight green tint drift. Skimmed & backwashed prior to 07:00 AM opening.",
        ),
        (
            (base_start + timedelta(days=15, hours=16)).isoformat(),
            "MONSOON_DEBRIS_ALERT",
            "MEDIUM",
            78.9,
            37.1,
            16,
            "RESOLVED",
            "JMB Morning Pool Cleaning Crew",
            "Heavy afternoon squall deposited palm fronds & leaves in Zone B Deep End. Auto-scheduled skimmer dispatch.",
        ),
        (
            (base_start + timedelta(days=23, hours=17)).isoformat(),
            "ALGAE_AND_DEBRIS_WARNING",
            "HIGH",
            74.2,
            41.5,
            22,
            "OPEN",
            "JMB Pool Maintenance Team",
            "Monsoon debris surge (22 floating objects) + HSV green-index drift (41.5). Proactive chlorine dosing & skimming ticket opened before algae bloom requires costly pool drainage.",
        ),
    ]
    conn.executemany(
        """
        INSERT INTO maintenance_tickets (
            timestamp, ticket_type, severity, turbidity_score,
            algae_green_index, debris_count, status, assigned_to, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ticket_rows,
    )

    conn.commit()
    return True
