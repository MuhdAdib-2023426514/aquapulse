"""Diurnal Crowd & Quiet-Hour Forecaster (`scikit-learn`) + Resident App Comfort Widget."""

from __future__ import annotations

import math
import sqlite3
from typing import Any, Literal

import numpy as np
from sklearn.ensemble import RandomForestRegressor

from aquapulse.db.database import fetch_hourly_telemetry, init_db
from aquapulse.esg.pump_optimizer import optimize_24h_vfd_schedule
from aquapulse.schemas import (
    ResidentComfortStatus,
    SwimmerRole,
    SwimmerTrack,
    WaterClarityReport,
)


def _encode_diurnal_features(day_of_week: int, hour: int) -> list[float]:
    """Encode `(day_of_week, hour)` with cyclical sin/cos time features."""
    is_weekend = 1.0 if day_of_week >= 5 else 0.0
    angle = 2.0 * math.pi * float(hour) / 24.0
    return [
        float(day_of_week),
        float(hour),
        is_weekend,
        math.sin(angle),
        math.cos(angle),
    ]


def _format_hour_window(hour: int, est_swimmers: int) -> str:
    """Format a 1-hour daytime window as e.g. `13:00 – 14:00 (~2 swimmers)`."""
    next_h = (hour + 1) % 24
    return f"{hour:02d}:00 – {next_h:02d}:00 (~{est_swimmers} swimmers)"


class DiurnalCrowdForecaster:
    """Forecasts 24-hour condo pool bather load, VFD schedule, and daytime quiet swim windows."""

    def __init__(self, conn: sqlite3.Connection | None = None) -> None:
        self._swimmer_model = RandomForestRegressor(
            n_estimators=40,
            max_depth=8,
            random_state=42,
        )
        self._contamination_model = RandomForestRegressor(
            n_estimators=40,
            max_depth=8,
            random_state=42,
        )
        self.is_fitted: bool = False
        if conn is not None:
            self.fit_from_db(conn)

    def fit_from_db(self, conn: sqlite3.Connection | None = None) -> bool:
        """Fit the scikit-learn regressors on the 30-day `hourly_telemetry` table."""
        owns_conn = False
        if conn is None:
            conn = init_db()
            owns_conn = True

        rows = fetch_hourly_telemetry(conn, limit=720)
        if owns_conn:
            conn.close()

        if not rows:
            return False

        x_rows: list[list[float]] = []
        y_swimmers: list[float] = []
        y_contam: list[float] = []

        for r in rows:
            x_rows.append(_encode_diurnal_features(int(r["day_of_week"]), int(r["hour"])))
            y_swimmers.append(float(r["swimmer_count"]))
            y_contam.append(float(r["contamination_score"]))

        x_mat = np.array(x_rows, dtype=np.float64)
        self._swimmer_model.fit(x_mat, np.array(y_swimmers, dtype=np.float64))
        self._contamination_model.fit(x_mat, np.array(y_contam, dtype=np.float64))
        self.is_fitted = True
        return True

    def predict_24h_profile(self, day_of_week: int = 5) -> list[dict[str, Any]]:
        """Predict 24-hour swimmer headcount, contamination score, and optimal VFD speed."""
        if not self.is_fitted:
            self.fit_from_db()

        x_query = np.array(
            [_encode_diurnal_features(day_of_week, h) for h in range(24)],
            dtype=np.float64,
        )
        pred_swimmers_raw = self._swimmer_model.predict(x_query)
        pred_contam_raw = self._contamination_model.predict(x_query)

        hourly_bathers: list[int] = []
        for h in range(24):
            if 0 <= h <= 5 or h >= 22:
                hourly_bathers.append(0)
            else:
                hourly_bathers.append(max(0, int(round(float(pred_swimmers_raw[h])))))

        vfd_plan = optimize_24h_vfd_schedule(hourly_bathers)
        schedule_items = vfd_plan["hourly_schedule"]

        profile: list[dict[str, Any]] = []
        for h in range(24):
            bathers = hourly_bathers[h]
            if bathers <= 4:
                band = "QUIET"
            elif bathers <= 11:
                band = "MODERATE"
            else:
                band = "BUSY"

            profile.append(
                {
                    "hour": h,
                    "hour_label": f"{h:02d}:00",
                    "predicted_swimmers": bathers,
                    "predicted_contamination": round(
                        0.0 if bathers == 0 else max(float(bathers), float(pred_contam_raw[h])),
                        1,
                    ),
                    "recommended_vfd_pct": schedule_items[h]["vfd_speed_pct"],
                    "vfd_pump_kw": schedule_items[h]["vfd_pump_kw"],
                    "crowd_band": band,
                }
            )
        return profile

    def recommend_quiet_hours(self, day_of_week: int = 5, top_k: int = 3) -> list[str]:
        """Return the `top_k` quietest daytime open pool hours (`06:00..20:00`)."""
        profile = self.predict_24h_profile(day_of_week=day_of_week)
        daytime_open = [p for p in profile if 6 <= p["hour"] <= 20]
        daytime_open.sort(key=lambda item: (item["predicted_swimmers"], item["hour"]))
        selected = sorted(daytime_open[:top_k], key=lambda item: item["hour"])
        return [_format_hour_window(int(p["hour"]), int(p["predicted_swimmers"])) for p in selected]

    def build_resident_comfort_status(
        self,
        tracks: list[SwimmerTrack],
        water_report: WaterClarityReport | None = None,
        day_of_week: int = 5,
    ) -> ResidentComfortStatus:
        """Construct the anonymous live payload for Tab 4's Resident Township App Widget."""
        headcount = len(tracks)
        lap_count = sum(1 for t in tracks if t.role == SwimmerRole.LAP_SWIMMER)
        toddler_count = sum(1 for t in tracks if t.role == SwimmerRole.TODDLER)
        senior_count = sum(1 for t in tracks if t.role == SwimmerRole.SENIOR)
        family_count = max(0, headcount - lap_count)

        crowd_level: Literal["QUIET", "MODERATE", "BUSY"]
        if headcount <= 4:
            crowd_level = "QUIET"
        elif headcount <= 10:
            crowd_level = "MODERATE"
        else:
            crowd_level = "BUSY"

        if water_report is not None:
            clarity_label = f"{water_report.status.replace('_', ' ').title()} ({water_report.turbidity_score:.0f}/100)"
        else:
            clarity_label = "Crystal Clear (96/100)"

        quiet_windows = self.recommend_quiet_hours(day_of_week=day_of_week, top_k=3)
        safe_window = (
            "09:00 – 11:00 AM & 02:00 – 04:00 PM (Low Lap Traffic & Calm Shallow Zone)"
            if day_of_week < 5
            else "08:00 – 09:30 AM & 01:00 – 03:00 PM (Designated Family & Senior Calm Window)"
        )

        return ResidentComfortStatus(
            live_headcount=headcount,
            crowd_level=crowd_level,
            lap_swimmers=lap_count,
            family_swimmers=family_count,
            toddler_count=toddler_count,
            senior_count=senior_count,
            water_clarity_label=clarity_label,
            recommended_quiet_hours=quiet_windows,
            senior_toddler_safe_window=safe_window,
        )
