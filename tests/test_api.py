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
    """Verify /api/v1/vision/step progresses SILENT_DROWNING_RESCUE 0s -> 5s VERIFY -> 8s CRITICAL."""
    # Jump to 5.0s -> VERIFY
    r5 = client.post(
        "/api/v1/vision/step",
        json={
            "scenario": "SILENT_DROWNING_RESCUE",
            "target_elapsed_sec": 5.0,
            "reset": True,
        },
    )
    assert r5.status_code == 200
    d5 = r5.json()
    assert d5["elapsed_sec"] == 5.0
    assert d5["system1_trace"]["within_latency_budget"] is True
    assert d5["system1_trace"]["overall_state"] == "VERIFY"

    # Jump to 8.0s -> CRITICAL_EMERGENCY
    r8 = client.post(
        "/api/v1/vision/step",
        json={
            "scenario": "SILENT_DROWNING_RESCUE",
            "target_elapsed_sec": 8.0,
            "reset": True,
        },
    )
    assert r8.status_code == 200
    d8 = r8.json()
    assert d8["elapsed_sec"] == 8.0
    assert d8["system1_trace"]["overall_state"] == "CRITICAL_EMERGENCY"
    tool_names = [t["tool_name"] for t in d8["tool_logs"]]
    assert "trigger_emergency_siren_and_tts" in tool_names


def test_vision_step_system2_cotton_and_food_governance() -> None:
    """Verify /api/v1/vision/step progresses COTTON_TSHIRT_AND_FOOD_NUDGE to 5s Nudge and 8s Ticket."""
    r5 = client.post(
        "/api/v1/vision/step",
        json={
            "scenario": "COTTON_TSHIRT_AND_FOOD_NUDGE",
            "target_elapsed_sec": 5.0,
            "reset": True,
        },
    )
    assert r5.status_code == 200
    d5 = r5.json()
    assert d5["system1_trace"]["overall_state"] == "NUDGE_REQUIRED"
    assert len(d5["system2_inspections"]) >= 1
    assert all(ins["tier1_face_redacted"] is True for ins in d5["system2_inspections"])

    r8 = client.post(
        "/api/v1/vision/step",
        json={
            "scenario": "COTTON_TSHIRT_AND_FOOD_NUDGE",
            "target_elapsed_sec": 8.0,
            "reset": True,
        },
    )
    assert r8.status_code == 200
    d8 = r8.json()
    assert d8["system1_trace"]["overall_state"] == "ESCALATED_GUARD_TICKET"


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


def test_vision_step_pet_and_stray_animal_governance_and_purge() -> None:
    """Verify PET_AND_STRAY_ANIMAL_POOL detects dog/cat, triggers Strata Nudge at 5s, and 100% VFD bio-purge."""
    r5 = client.post(
        "/api/v1/vision/step",
        json={
            "scenario": "PET_AND_STRAY_ANIMAL_POOL",
            "target_elapsed_sec": 5.0,
            "reset": True,
        },
    )
    assert r5.status_code == 200
    d5 = r5.json()
    detected_labels = {o["label"] for o in d5["detected_objects"]}
    assert {"dog", "cat"}.issubset(detected_labels)
    assert d5["system1_trace"]["overall_state"] == "NUDGE_REQUIRED"
    assert d5["esg_metrics"]["animal_events"] == 2
    assert d5["esg_metrics"]["recommended_vfd_speed_pct"] == 100.0
    assert any("Haiwan peliharaan" in (t.get("audio_tts_text") or "") for t in d5["tool_logs"])


def test_system_capabilities_and_audio_endpoints() -> None:
    """Verify /api/v1/system/capabilities and /api/v1/audio/{kind}.wav."""
    r_cap = client.get("/api/v1/system/capabilities")
    assert r_cap.status_code == 200
    cap_data = r_cap.json()
    assert "yolo26_pose_available" in cap_data
    assert cap_data["audio_synthesis_available"] is True

    r_audio = client.get("/api/v1/audio/critical_siren.wav")
    assert r_audio.status_code == 200
    assert r_audio.headers["content-type"] == "audio/wav"
    assert len(r_audio.content) > 1000


def test_vision_step_include_frames() -> None:
    """Verify /api/v1/vision/step returns base64 JPEGs when include_frames is True."""
    resp = client.post(
        "/api/v1/vision/step",
        json={
            "scenario": "NORMAL_LAP_AND_FAMILY",
            "dt_sec": 0.0,
            "reset": True,
            "include_frames": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "rendered_frames" in data
    assert "silhouette_bgr" in data["rendered_frames"]
    assert data["rendered_frames"]["silhouette_bgr"].startswith("data:image/jpeg;base64,")
