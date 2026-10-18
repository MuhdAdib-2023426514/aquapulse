"""Dynamic Bather-Load VFD Filtration Pump & Chemical Eco-Drive Optimizer.

Applies:
1. Real-time Biological & Contamination Load Score:
   Contamination Score = (Swimmer Count * Duration_Hours) + w1*(Cotton Violations) + w2*(Food/Drink Events)
2. Pump Affinity Law:
   P_vfd = P_rated * (N_vfd / N_rated)^3
3. Minimum Daily Turnover Floor:
   Daily Volume Circulated >= 3.5 * Pool Volume (1,575.0 m³/day for a 450 m³ pool)
"""

from __future__ import annotations

from typing import Any

from aquapulse.config import DEFAULT_CONFIG, PoolConfig
from aquapulse.schemas import ESGPumpMetrics


def compute_contamination_score(
    bather_count: int,
    cotton_violations: int = 0,
    food_drink_events: int = 0,
    animal_events: int = 0,
    duration_hours: float = 1.0,
    config: PoolConfig = DEFAULT_CONFIG,
) -> float:
    """Compute the real-time Biological & Contamination Load Score."""
    score = (
        float(max(0, bather_count)) * max(0.1, duration_hours)
        + config.contamination_w_cotton * float(max(0, cotton_violations))
        + config.contamination_w_food_drink * float(max(0, food_drink_events))
        + config.contamination_w_animal * float(max(0, animal_events))
    )
    return round(score, 2)


def recommend_vfd_speed_pct(
    contamination_score: float,
    bather_count: int,
    previous_contamination_score: float = 0.0,
    animal_events: int = 0,
    config: PoolConfig = DEFAULT_CONFIG,
) -> float:
    """Map bather load and contamination score to continuous VFD pump speed (40%..100%)."""
    # Animal / pet in pool or post-peak surge triggers immediate 100% high-filtration bio-purge
    if animal_events > 0 or (previous_contamination_score >= 18.0 and bather_count <= 6):
        return config.vfd_purge_max_pct  # 100.0%

    # Zero-occupancy eco-throttle window
    if bather_count == 0 and contamination_score == 0.0:
        return config.vfd_eco_min_pct  # 40.0%

    # Smooth continuous modulation from 70% (light load) up to 100% (heavy load)
    raw_pct = 70.0 + min(30.0, contamination_score * 1.35)
    return round(min(config.vfd_purge_max_pct, max(config.vfd_eco_min_pct, raw_pct)), 1)


def compute_pump_affinity_power_kw(
    vfd_speed_pct: float,
    rated_kw: float = DEFAULT_CONFIG.pump_rated_kw,
) -> float:
    """Calculate instantaneous VFD pump power (kW) via the Pump Affinity Law: P2 = P1 * (N2/N1)^3."""
    ratio = max(0.0, min(1.0, vfd_speed_pct / 100.0))
    return round(rated_kw * (ratio**3), 3)


def compute_instantaneous_esg_metrics(
    bather_count: int,
    cotton_violations: int = 0,
    food_drink_events: int = 0,
    animal_events: int = 0,
    *,
    previous_contamination_score: float = 0.0,
    override_vfd_speed_pct: float | None = None,
    config: PoolConfig = DEFAULT_CONFIG,
) -> ESGPumpMetrics:
    """Compute real-time `ESGPumpMetrics` for the current pool state."""
    c_score = compute_contamination_score(
        bather_count=bather_count,
        cotton_violations=cotton_violations,
        food_drink_events=food_drink_events,
        animal_events=animal_events,
        config=config,
    )
    vfd_pct = (
        round(
            min(config.vfd_purge_max_pct, max(config.vfd_eco_min_pct, override_vfd_speed_pct)),
            1,
        )
        if override_vfd_speed_pct is not None
        else recommend_vfd_speed_pct(
            contamination_score=c_score,
            bather_count=bather_count,
            previous_contamination_score=previous_contamination_score,
            animal_events=animal_events,
            config=config,
        )
    )

    speed_ratio = vfd_pct / 100.0
    flow_m3h = round(config.pump_rated_flow_m3h * speed_ratio, 2)
    fixed_kw = round(config.pump_rated_kw, 3)
    vfd_kw = compute_pump_affinity_power_kw(vfd_pct, rated_kw=config.pump_rated_kw)

    kwh_saved = round(max(0.0, fixed_kw - vfd_kw), 3)
    rm_saved = round(kwh_saved * config.tnb_tariff_rm_per_kwh, 3)
    co2_saved = round(kwh_saved * config.my_grid_kg_co2_per_kwh, 3)

    # Projected daily turnovers combining this active window with the 24h floor controller
    instant_24h_turnovers = (flow_m3h * 24.0) / config.pool_volume_m3
    projected_turnovers = round(max(config.min_daily_turnovers, instant_24h_turnovers), 2)

    return ESGPumpMetrics(
        bather_count=max(0, bather_count),
        cotton_violations=max(0, cotton_violations),
        food_drink_events=max(0, food_drink_events),
        animal_events=max(0, animal_events),
        contamination_score=c_score,
        recommended_vfd_speed_pct=vfd_pct,
        flow_rate_m3h=flow_m3h,
        fixed_pump_kw=fixed_kw,
        vfd_pump_kw=vfd_kw,
        hourly_kwh_saved=kwh_saved,
        hourly_rm_saved=rm_saved,
        hourly_co2_saved_kg=co2_saved,
        projected_daily_turnovers=projected_turnovers,
        turnover_floor_compliant=projected_turnovers >= config.min_daily_turnovers,
    )


def optimize_24h_vfd_schedule(
    hourly_bathers: list[int],
    hourly_cotton: list[int] | None = None,
    hourly_food: list[int] | None = None,
    config: PoolConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Optimize a 24-hour VFD pump schedule while strictly enforcing `>= 3.5 turnovers/day`."""
    if len(hourly_bathers) != 24:
        raise ValueError("hourly_bathers must contain exactly 24 hourly values.")

    cottons = hourly_cotton if hourly_cotton and len(hourly_cotton) == 24 else [0] * 24
    foods = hourly_food if hourly_food and len(hourly_food) == 24 else [0] * 24

    schedule: list[dict[str, Any]] = []
    prev_score = 0.0

    for hour in range(24):
        bathers = max(0, int(hourly_bathers[hour]))
        c_viol = max(0, int(cottons[hour]))
        f_viol = max(0, int(foods[hour]))
        score = compute_contamination_score(bathers, c_viol, f_viol, config=config)

        # Deep night (00:00..04:59) with 0 bathers uses 40% eco-mode
        if bathers == 0 and prev_score < 15.0 and 0 <= hour <= 4:
            vfd_pct = config.vfd_eco_min_pct
        else:
            vfd_pct = recommend_vfd_speed_pct(
                contamination_score=score,
                bather_count=bathers,
                previous_contamination_score=prev_score,
                config=config,
            )

        prev_score = score
        schedule.append(
            {
                "hour": hour,
                "bather_count": bathers,
                "cotton_violations": c_viol,
                "food_drink_events": f_viol,
                "contamination_score": score,
                "vfd_speed_pct": vfd_pct,
            }
        )

    # Enforce Minimum Daily Turnover Floor (>= 3.5 turnovers/day = 1,575 m³/day)
    min_daily_volume_m3 = config.pool_volume_m3 * config.min_daily_turnovers
    current_volume_m3 = sum(
        config.pump_rated_flow_m3h * (item["vfd_speed_pct"] / 100.0) for item in schedule
    )

    if current_volume_m3 < min_daily_volume_m3:
        deficit_m3 = (min_daily_volume_m3 - current_volume_m3) + 12.0  # safety margin above 3.5x
        # Boost daytime/shoulder hours (05:00..22:59) first so deep-night 40% eco-mode stays preserved
        candidates = [
            item for item in schedule if item["hour"] >= 5 and item["vfd_speed_pct"] < 98.0
        ]
        if not candidates:
            candidates = [item for item in schedule if item["vfd_speed_pct"] < 100.0]

        if candidates:
            pct_bump = (deficit_m3 / len(candidates)) / config.pump_rated_flow_m3h * 100.0
            for item in candidates:
                item["vfd_speed_pct"] = min(100.0, round(item["vfd_speed_pct"] + pct_bump, 1))

        # Second pass if still slightly below floor (e.g., 100% empty 24h day where 19h hit 100%)
        current_volume_m3 = sum(
            config.pump_rated_flow_m3h * (item["vfd_speed_pct"] / 100.0) for item in schedule
        )
        if current_volume_m3 < min_daily_volume_m3:
            rem_deficit = (min_daily_volume_m3 - current_volume_m3) + 5.0
            rem_candidates = [item for item in schedule if item["vfd_speed_pct"] < 100.0]
            if rem_candidates:
                pct_bump2 = (rem_deficit / len(rem_candidates)) / config.pump_rated_flow_m3h * 100.0
                for item in rem_candidates:
                    item["vfd_speed_pct"] = min(100.0, round(item["vfd_speed_pct"] + pct_bump2, 1))

    # Finalize hourly power, flow, RM, and CO2 metrics
    total_fixed_kwh = 0.0
    total_vfd_kwh = 0.0
    total_volume_m3 = 0.0

    for item in schedule:
        vfd_pct = item["vfd_speed_pct"]
        flow_m3h = round(config.pump_rated_flow_m3h * (vfd_pct / 100.0), 2)
        fixed_kw = round(config.pump_rated_kw, 3)
        vfd_kw = compute_pump_affinity_power_kw(vfd_pct, rated_kw=config.pump_rated_kw)
        saved_kwh = round(max(0.0, fixed_kw - vfd_kw), 3)

        item["flow_rate_m3h"] = flow_m3h
        item["fixed_pump_kw"] = fixed_kw
        item["vfd_pump_kw"] = vfd_kw
        item["kwh_saved"] = saved_kwh
        item["rm_saved"] = round(saved_kwh * config.tnb_tariff_rm_per_kwh, 3)
        item["co2_saved_kg"] = round(saved_kwh * config.my_grid_kg_co2_per_kwh, 3)

        total_fixed_kwh += fixed_kw
        total_vfd_kwh += vfd_kw
        total_volume_m3 += flow_m3h

    total_saved_kwh = max(0.0, total_fixed_kwh - total_vfd_kwh)
    reduction_pct = (total_saved_kwh / total_fixed_kwh * 100.0) if total_fixed_kwh > 0 else 0.0
    daily_turnovers = round(total_volume_m3 / config.pool_volume_m3, 2)

    return {
        "hourly_schedule": schedule,
        "daily_fixed_kwh": round(total_fixed_kwh, 2),
        "daily_vfd_kwh": round(total_vfd_kwh, 2),
        "daily_kwh_saved": round(total_saved_kwh, 2),
        "energy_reduction_pct": round(reduction_pct, 2),
        "daily_rm_saved": round(total_saved_kwh * config.tnb_tariff_rm_per_kwh, 2),
        "daily_co2_saved_kg": round(total_saved_kwh * config.my_grid_kg_co2_per_kwh, 2),
        "daily_volume_m3": round(total_volume_m3, 1),
        "daily_turnovers": daily_turnovers,
        "turnover_floor_compliant": daily_turnovers >= config.min_daily_turnovers,
    }


def generate_affinity_law_curve(
    config: PoolConfig = DEFAULT_CONFIG,
) -> list[dict[str, float]]:
    """Return Pump Affinity Law points from 40% to 100% VFD speed for Plotly visualization."""
    points: list[dict[str, float]] = []
    for pct in range(40, 105, 5):
        vfd_kw = compute_pump_affinity_power_kw(float(pct), rated_kw=config.pump_rated_kw)
        flow_m3h = round(config.pump_rated_flow_m3h * (pct / 100.0), 2)
        hourly_rm = round(vfd_kw * config.tnb_tariff_rm_per_kwh, 3)
        points.append(
            {
                "vfd_speed_pct": float(pct),
                "vfd_power_kw": vfd_kw,
                "fixed_power_kw": config.pump_rated_kw,
                "flow_rate_m3h": flow_m3h,
                "hourly_cost_rm": hourly_rm,
            }
        )
    return points
