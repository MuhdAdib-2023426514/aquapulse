"""Milestone 5 verification tests: FastAPI REST endpoints & end-to-end scenario progression."""

from __future__ import annotations

from fastapi.testclient import TestClient

from aquapulse.api.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    """Verify /health returns 200 OK and 720 pre-seeded hourly SQLite rows."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["total_seeded_hours"] == 720
    assert data["system1_latency_budget_ms"] == 30.0


def test_vision_step_system1_flailing_to_submersion_rescue() -> None:
    """Verify /api/v1/vision/step progresses SILENT_DROWNING_RESCUE 0s -> 10s VERIFY -> 20s CRITICAL."""
    # Jump to 10.0s -> VERIFY
    r10 = client.post(
        "/api/v1/vision/step",
        json={
            "scenario": "SILENT_DROWNING_RESCUE",
            "target_elapsed_sec": 10.0,
            "reset": True,
        },
    )
    assert r10.status_code == 200
    d10 = r10.json()
    assert d10["elapsed_sec"] == 10.0
    assert d10["system1_trace"]["within_latency_budget"] is True
    assert d10["system1_trace"]["overall_state"] == "VERIFY"

    # Jump to 20.0s -> CRITICAL_EMERGENCY
    r20 = client.post(
        "/api/v1/vision/step",
        json={
            "scenario": "SILENT_DROWNING_RESCUE",
            "target_elapsed_sec": 20.0,
            "reset": True,
        },
    )
    assert r20.status_code == 200
    d20 = r20.json()
    assert d20["system1_trace"]["overall_state"] == "CRITICAL_EMERGENCY"
    tool_names = [t["tool_name"] for t in d20["tool_logs"]]
    assert "trigger_emergency_siren_and_tts" in tool_names


def test_vision_step_system2_cotton_and_food_governance() -> None:
    """Verify /api/v1/vision/step progresses COTTON_TSHIRT_AND_FOOD_NUDGE to 15s Nudge and 30s Ticket."""
    r15 = client.post(
        "/api/v1/vision/step",
        json={
            "scenario": "COTTON_TSHIRT_AND_FOOD_NUDGE",
            "target_elapsed_sec": 15.0,
            "reset": True,
        },
    )
    assert r15.status_code == 200
    d15 = r15.json()
    assert d15["system1_trace"]["overall_state"] == "NUDGE_REQUIRED"
    assert len(d15["system2_inspections"]) >= 1
    assert all(ins["tier1_face_redacted"] is True for ins in d15["system2_inspections"])

    r30 = client.post(
        "/api/v1/vision/step",
        json={
            "scenario": "COTTON_TSHIRT_AND_FOOD_NUDGE",
            "target_elapsed_sec": 30.0,
            "reset": True,
        },
    )
    assert r30.status_code == 200
    d30 = r30.json()
    assert d30["system1_trace"]["overall_state"] == "ESCALATED_GUARD_TICKET"


def test_agent_esg_water_and_resident_endpoints() -> None:
    """Verify /api/v1/agent/state, /api/v1/esg/summary, /api/v1/water/inspect, and /api/v1/resident/comfort."""
    r_agent = client.get("/api/v1/agent/state")
    assert r_agent.status_code == 200
    assert "recent_incidents_db" in r_agent.json()

    r_esg = client.get("/api/v1/esg/summary")
    assert r_esg.status_code == 200
    esg_data = r_esg.json()
    assert esg_data["summary_30d"]["min_daily_turnovers"] >= 3.5
    assert len(esg_data["affinity_law_curve"]) == 13
    assert esg_data["schedule_24h"]["turnover_floor_compliant"] is True

    r_water = client.get("/api/v1/water/inspect?scenario=MONSOON_DEBRIS_AND_ALGAE")
    assert r_water.status_code == 200
    water_data = r_water.json()
    assert water_data["report"]["status"] == "MONSOON_DEBRIS_ALERT"
    assert water_data["report"]["floating_debris_count"] >= 10

    r_res = client.get("/api/v1/resident/comfort?day_of_week=5")
    assert r_res.status_code == 200
    res_data = r_res.json()
    assert len(res_data["forecast_24h"]) == 24
    assert len(res_data["resident_comfort"]["recommended_quiet_hours"]) == 3
