"""Milestone 4 verification tests: Bather-Load VFD Pump Optimizer, Turnover Floor, Pump Affinity Law, and Scikit-Learn Crowd Forecaster."""

from __future__ import annotations

from pathlib import Path

from aquapulse.db.database import init_db
from aquapulse.esg.forecaster import DiurnalCrowdForecaster
from aquapulse.esg.pump_optimizer import (
    compute_contamination_score,
    compute_instantaneous_esg_metrics,
    compute_pump_affinity_power_kw,
    generate_affinity_law_curve,
    optimize_24h_vfd_schedule,
)
from aquapulse.schemas import ScenarioName
from aquapulse.vision.detector import synthesize_scenario_frame


def test_contamination_score_and_pump_affinity_law_math() -> None:
    """Verify Contamination Score weights and cubic Pump Affinity Law (P2 = P1 * (N2/N1)^3)."""
    # 10 bathers + 2 cotton violations (2 * 2.5 = 5.0) + 1 food/drink (1 * 3.0 = 3.0) = 18.0
    score = compute_contamination_score(bather_count=10, cotton_violations=2, food_drink_events=1)
    assert score == 18.0

    # At 40% eco-speed, power draw is 5.5 * (0.4)^3 = 0.352 kW (93.6% instantaneous reduction)
    eco_kw = compute_pump_affinity_power_kw(40.0, rated_kw=5.5)
    assert eco_kw == 0.352

    eco_metrics = compute_instantaneous_esg_metrics(
        bather_count=0,
        cotton_violations=0,
        food_drink_events=0,
    )
    assert eco_metrics.recommended_vfd_speed_pct == 40.0
    assert eco_metrics.vfd_pump_kw == 0.352
    assert eco_metrics.hourly_kwh_saved == 5.148
    assert eco_metrics.hourly_rm_saved == round(5.148 * 0.51, 3)
    assert eco_metrics.hourly_co2_saved_kg == round(5.148 * 0.758, 3)
    assert eco_metrics.turnover_floor_compliant is True

    # Post-peak high-filtration purge cycle when previous_contamination_score >= 18.0
    purge_metrics = compute_instantaneous_esg_metrics(
        bather_count=2,
        previous_contamination_score=22.0,
    )
    assert purge_metrics.recommended_vfd_speed_pct == 100.0
    assert purge_metrics.vfd_pump_kw == 5.5


def test_24h_schedule_enforces_minimum_daily_turnover_floor() -> None:
    """Verify optimize_24h_vfd_schedule strictly maintains >= 3.5 turnovers/day even on a 0-bather day."""
    # Case 1: Zero bathers all 24 hours (without floor enforcement, 40% speed = 1.81 turnovers/day)
    zero_day = optimize_24h_vfd_schedule([0] * 24)
    assert zero_day["turnover_floor_compliant"] is True
    assert zero_day["daily_turnovers"] >= 3.5
    assert zero_day["energy_reduction_pct"] >= 30.0
    # Deep night hours (0..4) remain at 40% eco-mode
    assert zero_day["hourly_schedule"][0]["vfd_speed_pct"] == 40.0

    # Case 2: Realistic peak condo day
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
    typical_day = optimize_24h_vfd_schedule(typical_bathers)
    assert typical_day["turnover_floor_compliant"] is True
    assert typical_day["daily_turnovers"] >= 3.5
    assert 22.0 <= typical_day["energy_reduction_pct"] <= 48.0
    assert typical_day["daily_rm_saved"] > 15.0

    curve = generate_affinity_law_curve()
    assert len(curve) == 13
    assert curve[0]["vfd_speed_pct"] == 40.0
    assert curve[-1]["vfd_speed_pct"] == 100.0


def test_scikit_learn_diurnal_forecaster_and_resident_widget(tmp_path: Path) -> None:
    """Verify DiurnalCrowdForecaster fits on SQLite, forecasts 24h profile, and builds ResidentComfortStatus."""
    conn = init_db(tmp_path / "forecaster_test.db", auto_seed=True)
    forecaster = DiurnalCrowdForecaster(conn=conn)
    assert forecaster.is_fitted is True

    sat_profile = forecaster.predict_24h_profile(day_of_week=5)  # Saturday
    assert len(sat_profile) == 24
    # Deep night should predict 0 swimmers and 40% VFD eco-speed
    assert sat_profile[2]["predicted_swimmers"] == 0
    assert sat_profile[2]["recommended_vfd_pct"] == 40.0
    # Afternoon peak (17:00..19:00) should predict higher crowd than midday lull (13:00)
    assert sat_profile[18]["predicted_swimmers"] > sat_profile[13]["predicted_swimmers"]

    quiet_windows = forecaster.recommend_quiet_hours(day_of_week=5, top_k=3)
    assert len(quiet_windows) == 3
    # Quiet hours must only come from daytime open hours (06:00..20:00), never 00:00..05:00
    for w in quiet_windows:
        start_hr = int(w[:2])
        assert 6 <= start_hr <= 20

    _, tracks, _ = synthesize_scenario_frame(
        ScenarioName.PEAK_CROWD_SURGE_ECO_DRIVE, elapsed_sec=5.0
    )
    widget = forecaster.build_resident_comfort_status(tracks=tracks, day_of_week=5)
    assert widget.live_headcount == 14
    assert widget.crowd_level == "BUSY"
    assert len(widget.recommended_quiet_hours) == 3
    conn.close()
