"""Milestone 1 verification tests: Config, Pydantic v2 Schemas, and 30-Day SQLite Seeder."""

from __future__ import annotations

from pathlib import Path

from aquapulse.config import (
    DEFAULT_CONFIG,
    MIN_DAILY_TURNOVERS,
    MY_GRID_KG_CO2_PER_KWH,
    POOL_VOLUME_M3,
    PUMP_RATED_KW,
    SYS1_CRITICAL_EMERGENCY_SEC,
    SYS1_MAX_LATENCY_MS,
    SYS1_VERIFY_SEC,
    SYS2_NUDGE_REQUIRED_SEC,
    TNB_TARIFF_RM_PER_KWH,
    ZONE_POLYGONS_PX,
)
from aquapulse.db.database import (
    fetch_30d_esg_summary,
    fetch_hourly_telemetry,
    fetch_maintenance_tickets,
    fetch_recent_incidents,
    init_db,
    insert_incident_log,
    insert_maintenance_ticket,
)
from aquapulse.schemas import (
    AgentState,
    ESGPumpMetrics,
    Keypoint2D,
    PoolZone,
    PostureState,
    SwimmerRole,
    SwimmerTrack,
    System1ReflexTrace,
    System2InspectionResult,
    ViolationType,
)


def test_config_constants_and_zones() -> None:
    """Verify physical pool, Malaysian TNB tariff, and System 1/2 temporal constants."""
    assert POOL_VOLUME_M3 == 450.0
    assert PUMP_RATED_KW == 5.5
    assert TNB_TARIFF_RM_PER_KWH == 0.51
    assert MY_GRID_KG_CO2_PER_KWH == 0.758
    assert MIN_DAILY_TURNOVERS == 3.5
    assert SYS1_VERIFY_SEC == 10.0
    assert SYS1_CRITICAL_EMERGENCY_SEC == 20.0
    assert SYS1_MAX_LATENCY_MS == 30.0
    assert SYS2_NUDGE_REQUIRED_SEC == 15.0
    assert DEFAULT_CONFIG.pool_volume_m3 == 450.0
    assert set(ZONE_POLYGONS_PX.keys()) == {"ZONE_A_SHALLOW", "ZONE_B_DEEP_END", "POOL_DECK"}


def test_pydantic_schemas_validation() -> None:
    """Verify Pydantic v2 models for SwimmerTrack, System 1/2 traces, and ESG metrics."""
    kp = [Keypoint2D(x=120.0 + i, y=180.0 + i, conf=0.95) for i in range(17)]
    track = SwimmerTrack(
        track_id=101,
        role=SwimmerRole.TODDLER,
        zone=PoolZone.ZONE_A_SHALLOW,
        posture=PostureState.VERTICAL_TREADING,
        bbox=(100, 150, 140, 210),
        pool_coords_m=(11.8, 5.2),
        keypoints=kp,
        is_submerged=False,
        near_deep_boundary=True,
        suspected_violation=ViolationType.NONE,
    )
    assert track.track_id == 101
    assert len(track.keypoints) == 17
    assert track.near_deep_boundary is True

    sys1_trace = System1ReflexTrace(
        execution_latency_ms=4.2,
        within_latency_budget=True,
        overall_state=AgentState.VERIFY,
        tracks_evaluated=3,
        active_alerts=["Track #101 unaccompanied toddler near Zone B deep end (t=10.2s)"],
    )
    assert sys1_trace.execution_latency_ms < SYS1_MAX_LATENCY_MS
    assert sys1_trace.overall_state == AgentState.VERIFY

    sys2_res = System2InspectionResult(
        track_id=202,
        target_type="torso_attire_roi",
        tier1_face_redacted=True,
        verified_violation=True,
        violation_type=ViolationType.COTTON_ATTIRE,
        confidence=0.94,
        inspector_backend="opencv_heuristic",
        reasoning_summary="Opaque high-saturation cotton street t-shirt verified after Tier-1 face masking.",
    )
    assert sys2_res.tier1_face_redacted is True
    assert sys2_res.verified_violation is True

    esg = ESGPumpMetrics(
        bather_count=0,
        cotton_violations=0,
        food_drink_events=0,
        contamination_score=0.0,
        recommended_vfd_speed_pct=40.0,
        flow_rate_m3h=34.0,
        fixed_pump_kw=5.5,
        vfd_pump_kw=round(5.5 * (0.4**3), 3),
        hourly_kwh_saved=round(5.5 - 5.5 * (0.4**3), 3),
        hourly_rm_saved=round((5.5 - 5.5 * (0.4**3)) * 0.51, 3),
        hourly_co2_saved_kg=round((5.5 - 5.5 * (0.4**3)) * 0.758, 3),
        projected_daily_turnovers=3.6,
        turnover_floor_compliant=True,
    )
    assert esg.vfd_pump_kw == 0.352
    assert esg.turnover_floor_compliant is True


def test_sqlite_30_day_auto_seeding_and_invariants(tmp_path: Path) -> None:
    """Verify 3-table creation, 720-hour deterministic seeding, and >=3.5 daily turnovers."""
    db_file = tmp_path / "test_aquapulse.db"
    conn = init_db(db_file, auto_seed=True)

    rows = fetch_hourly_telemetry(conn, limit=1000)
    assert len(rows) == 720  # 30 days * 24 hours

    # Verify idempotency: calling seed again does not duplicate rows
    from aquapulse.db.seed import seed_30_days_if_empty

    assert seed_30_days_if_empty(conn) is False
    assert len(fetch_hourly_telemetry(conn, limit=1000)) == 720

    # Verify 30-day ESG summary and Minimum Daily Turnover Floor (>= 3.5 turnovers/day)
    summary = fetch_30d_esg_summary(conn)
    assert summary["total_hours"] == 720
    assert summary["min_daily_turnovers"] >= 3.5
    assert 25.0 <= summary["energy_reduction_pct"] <= 48.0
    assert summary["total_rm_saved"] > 500.0
    assert summary["total_co2_saved_kg"] > 750.0

    # Verify pre-seeded incident_logs and maintenance_tickets (3 monsoon storm alerts)
    incidents = fetch_recent_incidents(conn)
    assert len(incidents) >= 4
    assert all(inc["pdpa_mode"] == "SILHOUETTE" for inc in incidents)

    tickets = fetch_maintenance_tickets(conn)
    assert len(tickets) == 3

    # Test inserting new incident and maintenance ticket records
    new_inc_id = insert_incident_log(
        conn,
        timestamp="2026-10-18T12:00:00+00:00",
        system_path="SYSTEM_1",
        track_id=999,
        event_type="SILENT_DROWNING_TEST",
        agent_state="CRITICAL_EMERGENCY",
        zone="ZONE_B_DEEP_END",
        duration_sec=20.0,
        action_taken="Triggered directional siren + TTS",
    )
    assert new_inc_id > 0

    new_tkt_id = insert_maintenance_ticket(
        conn,
        timestamp="2026-10-18T12:05:00+00:00",
        ticket_type="MONSOON_DEBRIS_ALERT",
        severity="HIGH",
        turbidity_score=75.0,
        algae_green_index=39.0,
        debris_count=18,
        notes="Automated test ticket",
    )
    assert new_tkt_id > 0
    conn.close()
