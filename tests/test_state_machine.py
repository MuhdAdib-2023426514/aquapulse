"""Milestone 2 verification tests: System 1 (<30ms Reflex), Active Flailing -> Submersion Continuity, System 2 Governance, and Offline WAV Audio."""

from __future__ import annotations

from pathlib import Path

from aquapulse.agent.state_machine import AquaPulseStateMachine
from aquapulse.agent.tools import PoolsideToolActuator, synthesize_alert_wav
from aquapulse.db.database import fetch_maintenance_tickets, fetch_recent_incidents, init_db
from aquapulse.schemas import (
    AgentState,
    DetectedObject,
    PoolZone,
    PostureState,
    SwimmerRole,
    SwimmerTrack,
    ViolationType,
    WaterClarityReport,
)


def _make_swimmer(
    track_id: int,
    *,
    role: SwimmerRole = SwimmerRole.ADULT,
    zone: PoolZone = PoolZone.ZONE_B_DEEP_END,
    posture: PostureState = PostureState.ACTIVE_SWIM,
    coords_m: tuple[float, float] = (18.0, 6.0),
    is_flailing: bool = False,
    is_submerged: bool = False,
    near_deep_boundary: bool = False,
    violation: ViolationType = ViolationType.NONE,
) -> SwimmerTrack:
    return SwimmerTrack(
        track_id=track_id,
        role=role,
        zone=zone,
        posture=posture,
        bbox=(300, 120, 360, 200),
        pool_coords_m=coords_m,
        is_flailing=is_flailing,
        is_submerged=is_submerged,
        near_deep_boundary=near_deep_boundary,
        suspected_violation=violation,
    )


def test_system1_silent_drowning_and_sub30ms_latency() -> None:
    """Verify 0s -> 5s VERIFY -> 8s CRITICAL_EMERGENCY and <30ms latency budget."""
    sm = AquaPulseStateMachine()
    swimmer = _make_swimmer(
        101,
        zone=PoolZone.ZONE_B_DEEP_END,
        posture=PostureState.HORIZONTAL_SUBMERGED,
        is_submerged=True,
        coords_m=(19.0, 6.0),
    )

    # Tick 1: t = 3.0s -> still NORMAL
    trace1, tools1, _, _ = sm.step([swimmer], dt_sec=3.0)
    assert trace1.within_latency_budget is True
    assert trace1.execution_latency_ms < 30.0
    assert trace1.overall_state == AgentState.NORMAL
    assert len(tools1) == 0

    # Tick 2: t = 5.0s -> VERIFY + yellow caution beacon
    trace2, _, tools2, _ = sm.step([swimmer], dt_sec=2.0)
    assert trace2.within_latency_budget is True
    assert trace2.overall_state == AgentState.VERIFY
    assert len(tools2) == 1
    assert tools2[0].tool_name == "trigger_caution_beacon"
    assert tools2[0].system_path == "SYSTEM_1"

    # Tick 3: t = 8.0s -> CRITICAL_EMERGENCY + siren + bilingual TTS + guard route
    trace3, _, tools3, thoughts3 = sm.step([swimmer], dt_sec=3.0)
    assert trace3.within_latency_budget is True
    assert trace3.overall_state == AgentState.CRITICAL_EMERGENCY
    assert len(tools3) == 1
    assert tools3[0].tool_name == "trigger_emergency_siren_and_tts"
    assert "KECEMASAN" in (tools3[0].audio_tts_text or "")
    assert tools3[0].guard_route_hint is not None
    assert len(thoughts3) >= 1


def test_system1_active_flailing_to_submersion_continuity() -> None:
    """Verify Active Surface Flailing (5s VERIFY) seamlessly carries into Silent Submersion (8s CRITICAL)."""
    sm = AquaPulseStateMachine()

    # Phase 1: Swimmer is actively flailing at the surface for 5.0s -> VERIFY
    flailing_swimmer = _make_swimmer(
        205,
        zone=PoolZone.ZONE_B_DEEP_END,
        posture=PostureState.ACTIVE_FLAILING,
        is_flailing=True,
        is_submerged=False,
        coords_m=(16.5, 5.0),
    )
    trace1, _, tools1, _ = sm.step([flailing_swimmer], dt_sec=5.0)
    assert trace1.overall_state == AgentState.VERIFY
    assert sm.track_states[205].submersion_sec == 5.0
    assert sm.track_states[205].is_flailing is True
    assert len(tools1) == 1
    assert "ACTIVE_FLAILING_DISTRESS" in tools1[0].message

    # Phase 2: Swimmer exhausts and sinks motionless underwater for another 3.0s (total 8.0s)
    # Timer MUST NOT reset — escalates immediately to CRITICAL_EMERGENCY at t=8.0s!
    submerged_swimmer = _make_swimmer(
        205,
        zone=PoolZone.ZONE_B_DEEP_END,
        posture=PostureState.HORIZONTAL_SUBMERGED,
        is_flailing=False,
        is_submerged=True,
        coords_m=(16.5, 5.0),
    )
    trace2, _, tools2, _ = sm.step([submerged_swimmer], dt_sec=3.0)
    assert trace2.overall_state == AgentState.CRITICAL_EMERGENCY
    assert sm.track_states[205].submersion_sec == 8.0
    assert sm.track_states[205].is_flailing is True
    assert sm.track_states[205].is_submerged is True
    assert len(tools2) == 1
    assert tools2[0].tool_name == "trigger_emergency_siren_and_tts"
    assert "FLAILING_TO_SUBMERGED_DISTRESS" in tools2[0].message


def test_system1_bystander_rescue_hold_and_recovery() -> None:
    """Verify an adult within 1.5m holds VERIFY (suppresses 8s siren) until posture recovers."""
    sm = AquaPulseStateMachine()
    victim = _make_swimmer(
        301,
        posture=PostureState.HORIZONTAL_SUBMERGED,
        is_submerged=True,
        coords_m=(20.0, 6.0),
    )

    # Reach 5.0s VERIFY alone
    trace1, _, _, _ = sm.step([victim], dt_sec=5.0)
    assert trace1.overall_state == AgentState.VERIFY

    # Adult rescuer enters within 1.1m (<= 1.5m radius) while victim is still at t=10.0s
    rescuer = _make_swimmer(
        302,
        role=SwimmerRole.ADULT,
        posture=PostureState.ACTIVE_SWIM,
        coords_m=(20.8, 6.7),  # hypot(0.8, 0.7) = 1.063m <= 1.5m
    )
    trace2, _, tools2, _ = sm.step([victim, rescuer], dt_sec=5.0)
    assert trace2.overall_state == AgentState.VERIFY
    assert sm.track_states[301].is_supervised is True
    assert len(tools2) == 0  # 8s siren suppressed because rescuer is assisting

    # Victim recovers posture -> resets to NORMAL
    recovered_victim = _make_swimmer(
        301,
        posture=PostureState.VERTICAL_TREADING,
        is_submerged=False,
        coords_m=(20.0, 6.0),
    )
    trace3, _, _, _ = sm.step([recovered_victim, rescuer], dt_sec=2.0)
    assert trace3.overall_state == AgentState.NORMAL
    assert sm.track_states[301].submersion_sec == 0.0


def test_system1_unaccompanied_toddler_and_parent_supervision_reset() -> None:
    """Verify toddler near deep-end triggers VERIFY at 5s and immediately resets when parent is <=1.5m."""
    sm = AquaPulseStateMachine()
    toddler = _make_swimmer(
        401,
        role=SwimmerRole.TODDLER,
        zone=PoolZone.ZONE_A_SHALLOW,
        posture=PostureState.VERTICAL_TREADING,
        near_deep_boundary=True,
        coords_m=(12.0, 5.0),
    )
    distant_parent = _make_swimmer(
        402,
        role=SwimmerRole.ADULT,
        zone=PoolZone.ZONE_A_SHALLOW,
        coords_m=(5.0, 5.0),  # 7.0m away (> 1.5m)
    )

    # 5.0s unsupervised -> VERIFY
    trace1, _, tools1, _ = sm.step([toddler, distant_parent], dt_sec=5.0)
    assert trace1.overall_state == AgentState.VERIFY
    assert len(tools1) == 1
    assert tools1[0].tool_name == "trigger_caution_beacon"

    # Parent moves within 1.0m (<= 1.5m) -> immediate reset to NORMAL (0.0s)
    close_parent = _make_swimmer(
        402,
        role=SwimmerRole.ADULT,
        zone=PoolZone.ZONE_A_SHALLOW,
        coords_m=(11.2, 5.0),  # 0.8m away (<= 1.5m)
    )
    trace2, _, _, _ = sm.step([toddler, close_parent], dt_sec=2.0)
    assert trace2.overall_state == AgentState.NORMAL
    assert sm.track_states[401].unaccompanied_infant_sec == 0.0


def test_system2_two_strike_polite_nudge_and_guard_ticket_escalation(tmp_path: Path) -> None:
    """Verify 5.0s Nudge #1 (Tier-1 Face Masked ROI) and 8.0s Nudge #2 + Guard Ticket escalation."""
    conn = init_db(tmp_path / "sys2_test.db", auto_seed=False)
    actuator = PoolsideToolActuator(db_conn=conn)
    sm = AquaPulseStateMachine(actuator=actuator)

    violator = _make_swimmer(
        501,
        zone=PoolZone.ZONE_A_SHALLOW,
        violation=ViolationType.COTTON_ATTIRE,
    )

    # At t = 3.0s -> still NORMAL (below 5s threshold)
    trace1, sys2_1, tools1, _ = sm.step([violator], dt_sec=3.0)
    assert trace1.overall_state == AgentState.NORMAL
    assert len(sys2_1) == 0
    assert len(tools1) == 0

    # At t = 5.0s -> Tier-1 face-masked ROI verified -> NUDGE_REQUIRED (Nudge #1)
    trace2, sys2_2, tools2, _ = sm.step([violator], dt_sec=2.0)
    assert trace2.overall_state == AgentState.NUDGE_REQUIRED
    assert len(sys2_2) == 1
    assert sys2_2[0].tier1_face_redacted is True
    assert sys2_2[0].verified_violation is True
    assert sm.track_states[501].nudge_count == 1
    assert len(tools2) == 1
    assert tools2[0].tool_name == "trigger_polite_speaker_nudge"

    # At t = 8.0s (ignored 2nd nudge window) -> ESCALATED_GUARD_TICKET (Nudge #2 + Guard Ticket)
    trace3, _, tools3, _ = sm.step([violator], dt_sec=3.0)
    assert trace3.overall_state == AgentState.ESCALATED_GUARD_TICKET
    assert sm.track_states[501].nudge_count == 2
    assert len(tools3) == 2
    assert {t.tool_name for t in tools3} == {
        "trigger_polite_speaker_nudge",
        "dispatch_guard_governance_ticket",
    }

    incidents = fetch_recent_incidents(conn)
    assert len(incidents) == 2
    assert all(inc["pdpa_mode"] == "SILHOUETTE" for inc in incidents)

    # Resident complies -> decays to NORMAL via Leaky Bucket
    compliant = _make_swimmer(
        501,
        zone=PoolZone.ZONE_A_SHALLOW,
        violation=ViolationType.NONE,
    )
    # 8.0s violation with 0.25 decay rate takes 32s to fully drain
    trace4, _, _, _ = sm.step([compliant], dt_sec=35.0)
    assert trace4.overall_state == AgentState.NORMAL
    assert sm.track_states[501].violation_sec == 0.0
    conn.close()


def test_leaky_bucket_sip_and_swim_lap_accumulation() -> None:
    """Verify Leaky Bucket accumulates repeated sips across laps and triggers 5.0s nudge."""
    sm = AquaPulseStateMachine()
    violator = _make_swimmer(501, zone=PoolZone.ZONE_A_SHALLOW, violation=ViolationType.FOOD_DRINK_POOLSIDE)
    swimming = _make_swimmer(501, zone=PoolZone.ZONE_A_SHALLOW, violation=ViolationType.NONE)

    # Lap 1: 3.0s sip at pool coping -> violation_sec = 3.0s
    sm.step([violator], dt_sec=3.0)
    assert sm.track_states[501].violation_sec == 3.0
    assert sm.track_states[501].agent_state == AgentState.NORMAL

    # Swimmer does a 4.0s lap -> decays by 4.0 * 0.25 = 1.0s -> timer = 2.0s (does not reset to 0!)
    sm.step([swimming], dt_sec=4.0)
    assert sm.track_states[501].violation_sec == 2.0

    # Lap 2: 3.0s sip at pool coping -> 2.0 + 3.0 = 5.0s -> Nudge #1 triggers!
    trace, _, tools, _ = sm.step([violator], dt_sec=3.0)
    assert sm.track_states[501].violation_sec == 5.0
    assert trace.overall_state == AgentState.NUDGE_REQUIRED
    assert len(tools) == 1
    assert tools[0].tool_name == "trigger_polite_speaker_nudge"


def test_unattended_poolside_object_escalation(tmp_path: Path) -> None:
    """Verify unattended coping objects: 5s hazard badge -> 8s audio nudge -> 20s cleaner ticket."""
    conn = init_db(tmp_path / "unatt_test.db", auto_seed=False)
    actuator = PoolsideToolActuator(db_conn=conn)
    sm = AquaPulseStateMachine(actuator=actuator)

    # Food bowl placed on pool coping with no person nearby
    bowl = DetectedObject(
        label="bowl",
        confidence=0.92,
        bbox=(200, 50, 230, 80),
        zone=PoolZone.POOL_DECK,
    )

    # Step at t = 5.0s -> Hazard badge activated
    trace1, _, tools1, _ = sm.step(tracks=[], dt_sec=5.0, objects=[bowl])
    assert len(trace1.unattended_objects) == 1
    assert trace1.unattended_objects[0].is_hazard is True
    assert trace1.unattended_objects[0].unattended_sec == 5.0
    assert len(tools1) == 0

    # Step to t = 8.0s -> Ambient audio nudge fired
    _, _, tools2, _ = sm.step(tracks=[], dt_sec=3.0, objects=[bowl])
    assert len(tools2) == 1
    assert tools2[0].tool_name == "trigger_unattended_item_nudge"

    # Step to t = 20.0s -> Housekeeping cleaner ticket dispatched
    _, _, tools3, _ = sm.step(tracks=[], dt_sec=12.0, objects=[bowl])
    assert len(tools3) == 1
    assert tools3[0].tool_name == "dispatch_unattended_item_housekeeping_ticket"
    conn.close()


def test_offline_wav_synthesizer_and_cleaner_ticket(tmp_path: Path) -> None:
    """Verify pure-NumPy WAV bytes have valid RIFF WAVE headers and cleaner tickets persist."""
    for kind in ("verify_beacon", "critical_siren", "polite_nudge"):
        wav_bytes = synthesize_alert_wav(kind)  # type: ignore[arg-type]
        assert wav_bytes[:4] == b"RIFF"
        assert wav_bytes[8:12] == b"WAVE"
        assert len(wav_bytes) > 10000

    conn = init_db(tmp_path / "cleaner_test.db", auto_seed=False)
    actuator = PoolsideToolActuator(db_conn=conn)
    report = WaterClarityReport(
        turbidity_score=74.5,
        algae_green_index=39.8,
        floating_debris_count=18,
        status="MONSOON_DEBRIS_ALERT",
        cleaner_ticket_opened=True,
        recommended_action="Skim 18 monsoon storm leaves and dose shock chlorine.",
    )
    log = actuator.create_jmb_cleaner_ticket(report)
    assert log.tool_name == "create_jmb_cleaner_ticket"
    tickets = fetch_maintenance_tickets(conn)
    assert len(tickets) == 1
    assert tickets[0]["debris_count"] == 18
    conn.close()
