"""Autonomous poolside tool actuators and 100% offline WAV audio synthesizer."""

from __future__ import annotations

import io
import sqlite3
import wave
from pathlib import Path
from typing import Literal

import numpy as np

from aquapulse.config import ASSETS_DIR
from aquapulse.db.database import insert_incident_log, insert_maintenance_ticket
from aquapulse.schemas import (
    AgentState,
    PoolZone,
    ToolExecutionLog,
    ViolationType,
    WaterClarityReport,
)

AlertAudioType = Literal["verify_beacon", "critical_siren", "polite_nudge"]

_WAV_CACHE: dict[AlertAudioType, bytes] = {}

ZONE_ENTRY_ROUTES: dict[PoolZone, str] = {
    PoolZone.ZONE_A_SHALLOW: (
        "Gate 1 (South Clubhouse) -> Shallow Wading Steps -> Zone A Deck (Est. 45s from Guardhouse)"
    ),
    PoolZone.ZONE_B_DEEP_END: (
        "Gate 2 (North Emergency Access) -> Deep End Ladder #2 -> Zone B Deck (Est. 35s from Guardhouse)"
    ),
    PoolZone.POOL_DECK: (
        "Gate 1 (Main Poolside Walkway) -> Pergola Lounge Area (Est. 40s from Guardhouse)"
    ),
    PoolZone.UNKNOWN: (
        "Gate 1 (South Clubhouse) -> General Pool Basin Perimeter (Est. 45s from Guardhouse)"
    ),
}


def synthesize_alert_wav(
    alert_type: AlertAudioType,
    *,
    save_to_assets: bool = False,
    sample_rate: int = 22050,
) -> bytes:
    """Synthesize playable 16-bit PCM WAV bytes offline using pure NumPy + standard library `wave`."""
    if alert_type in _WAV_CACHE and not save_to_assets:
        return _WAV_CACHE[alert_type]

    if alert_type == "verify_beacon":
        # Two-pulse yellow caution chime (880 Hz -> 1046.5 Hz, 0.7s total)
        duration = 0.7
        t = np.linspace(0.0, duration, int(sample_rate * duration), endpoint=False)
        freq = np.where(t < 0.35, 880.0, 1046.5)
        env = np.exp(-3.5 * (t % 0.35))
        signal = 0.45 * np.sin(2.0 * np.pi * freq * t) * env
    elif alert_type == "critical_siren":
        # Urgent alternating hi-lo poolside emergency siren (960 Hz <-> 1440 Hz, 1.4s total)
        duration = 1.4
        t = np.linspace(0.0, duration, int(sample_rate * duration), endpoint=False)
        cycle = (t * 4.0).astype(int) % 2
        freq = np.where(cycle == 0, 960.0, 1440.0)
        signal = 0.65 * (
            0.75 * np.sin(2.0 * np.pi * freq * t) + 0.25 * np.sin(4.0 * np.pi * freq * t)
        )
    else:
        # Soft two-note polite chime (523.25 Hz C5 -> 659.25 Hz E5, 0.8s total)
        duration = 0.8
        t = np.linspace(0.0, duration, int(sample_rate * duration), endpoint=False)
        freq = np.where(t < 0.4, 523.25, 659.25)
        env = np.exp(-4.0 * (t % 0.4))
        signal = 0.35 * np.sin(2.0 * np.pi * freq * t) * env

    pcm16 = np.clip(signal * 32767.0, -32768, 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm16.tobytes())

    wav_bytes = buf.getvalue()
    _WAV_CACHE[alert_type] = wav_bytes

    if save_to_assets:
        audio_dir: Path = ASSETS_DIR / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        (audio_dir / f"{alert_type}.wav").write_bytes(wav_bytes)

    return wav_bytes


class PoolsideToolActuator:
    """Executes System 1 life-safety reflexes and System 2 governance/maintenance tools."""

    def __init__(self, db_conn: sqlite3.Connection | None = None) -> None:
        self.db_conn = db_conn
        self.execution_history: list[ToolExecutionLog] = []
        # Pre-warm audio cache in memory so System 1 (<30ms) has zero synthesis overhead
        for alert_kind in ("verify_beacon", "critical_siren", "polite_nudge"):
            synthesize_alert_wav(alert_kind)  # type: ignore[arg-type]

    def trigger_caution_beacon(
        self,
        *,
        track_id: int,
        zone: PoolZone,
        reason: str,
        duration_sec: float = 5.0,
    ) -> ToolExecutionLog:
        """System 1 (5.0s VERIFY): Flash poolside yellow caution beacon & pre-alert security."""
        route = ZONE_ENTRY_ROUTES.get(zone, ZONE_ENTRY_ROUTES[PoolZone.ZONE_A_SHALLOW])
        log = ToolExecutionLog(
            tool_name="trigger_caution_beacon",
            system_path="SYSTEM_1",
            zone=zone,
            track_id=track_id,
            message=(
                f"[VERIFY @ {duration_sec:.1f}s] Yellow poolside caution beacon activated in {zone.value} "
                f"for Track #{track_id} ({reason}). Pre-alert sent to Guardhouse."
            ),
            audio_tts_text=(
                f"Caution in {zone.value}: Please check on swimmer #{track_id} near the water."
            ),
            guard_route_hint=route,
        )
        self.execution_history.append(log)
        return log

    def trigger_emergency_siren_and_tts(
        self,
        *,
        track_id: int,
        zone: PoolZone,
        reason: str,
        duration_sec: float = 8.0,
    ) -> ToolExecutionLog:
        """System 1 (8.0s CRITICAL_EMERGENCY): Fire directional siren, bilingual TTS & guard route."""
        route = ZONE_ENTRY_ROUTES.get(zone, ZONE_ENTRY_ROUTES[PoolZone.ZONE_B_DEEP_END])
        tts_script = (
            f"EMERGENCY IN {zone.value}! {reason} — Nearby residents please assist immediately! "
            f"/ KECEMASAN DI {zone.value}! Perenang dalam bahaya — penduduk berhampiran sila bantu segera!"
        )
        log = ToolExecutionLog(
            tool_name="trigger_emergency_siren_and_tts",
            system_path="SYSTEM_1",
            zone=zone,
            track_id=track_id,
            message=(
                f"[CRITICAL_EMERGENCY @ {duration_sec:.1f}s] Directional siren + bilingual TTS broadcast "
                f"fired in {zone.value} for Track #{track_id} ({reason}). Live entry map dispatched to Guardhouse."
            ),
            audio_tts_text=tts_script,
            guard_route_hint=route,
        )
        self.execution_history.append(log)
        if self.db_conn is not None:
            insert_incident_log(
                self.db_conn,
                timestamp=log.timestamp.isoformat(),
                system_path="SYSTEM_1",
                track_id=track_id,
                event_type=reason,
                agent_state=AgentState.CRITICAL_EMERGENCY.value,
                zone=zone.value,
                duration_sec=duration_sec,
                action_taken=log.message,
                pdpa_mode="SILHOUETTE",
            )
        return log

    def trigger_polite_speaker_nudge(
        self,
        *,
        track_id: int,
        zone: PoolZone,
        violation_type: ViolationType,
        nudge_number: int,
        duration_sec: float,
    ) -> ToolExecutionLog:
        """System 2 (>15s NUDGE_REQUIRED): Play polite localized directional voice reminder."""
        if violation_type == ViolationType.COTTON_ATTIRE:
            tts = (
                "Friendly reminder from Township Management: For everyone's water hygiene and filter efficiency, "
                "kindly wear proper Lycra swimwear instead of cotton streetwear in the pool. Thank you! "
                "/ Peringatan mesra: Sila gunakan pakaian renang yang sesuai di dalam kolam."
            )
        elif violation_type == ViolationType.FOOD_DRINK_POOLSIDE:
            tts = (
                "Friendly reminder: Kindly enjoy food and beverages at the designated pergola dining tables "
                "away from the pool edge to keep our water crystal clear. Thank you!"
            )
        elif violation_type == ViolationType.PET_OR_STRAY_ANIMAL:
            tts = (
                "Friendly reminder from Township Management: Under Strata Management by-laws, pets and animals "
                "are not permitted in the swimming pool or pool deck area for community hygiene and filter protection. "
                "Kindly relocate your pet to the designated township pet park. Thank you! "
                "/ Peringatan mesra: Haiwan peliharaan tidak dibenarkan di kawasan kolam renang mengikut undang-undang kecil strata."
            )
        else:
            tts = (
                "Friendly reminder: The pool deck is a smoke-free and vape-free family zone. "
                "Thank you for keeping our community air fresh!"
            )

        log = ToolExecutionLog(
            tool_name="trigger_polite_speaker_nudge",
            system_path="SYSTEM_2",
            zone=zone,
            track_id=track_id,
            message=(
                f"[NUDGE #{nudge_number} @ {duration_sec:.1f}s] Tier-1 face-masked ROI verified "
                f"{violation_type.value} for Track #{track_id} in {zone.value}. Played polite directional speaker nudge."
            ),
            audio_tts_text=tts,
            guard_route_hint=None,
        )
        self.execution_history.append(log)
        if self.db_conn is not None and nudge_number == 1:
            insert_incident_log(
                self.db_conn,
                timestamp=log.timestamp.isoformat(),
                system_path="SYSTEM_2",
                track_id=track_id,
                event_type=violation_type.value,
                agent_state=AgentState.NUDGE_REQUIRED.value,
                zone=zone.value,
                duration_sec=duration_sec,
                action_taken=log.message,
                pdpa_mode="SILHOUETTE",
            )
        return log

    def dispatch_guard_governance_ticket(
        self,
        *,
        track_id: int,
        zone: PoolZone,
        violation_type: ViolationType,
        duration_sec: float,
    ) -> ToolExecutionLog:
        """System 2 (After 2 ignored nudges): Open PDPA-anonymized Guardhouse/JMB ticket."""
        route = ZONE_ENTRY_ROUTES.get(zone, ZONE_ENTRY_ROUTES[PoolZone.POOL_DECK])
        log = ToolExecutionLog(
            tool_name="dispatch_guard_governance_ticket",
            system_path="SYSTEM_2",
            zone=zone,
            track_id=track_id,
            message=(
                f"[ESCALATED_GUARD_TICKET @ {duration_sec:.1f}s] Track #{track_id} ignored 2 polite audio nudges "
                f"for {violation_type.value} in {zone.value}. Dispatched PDPA skeletal silhouette ticket to Guardhouse."
            ),
            audio_tts_text=None,
            guard_route_hint=route,
        )
        self.execution_history.append(log)
        if self.db_conn is not None:
            insert_incident_log(
                self.db_conn,
                timestamp=log.timestamp.isoformat(),
                system_path="SYSTEM_2",
                track_id=track_id,
                event_type=violation_type.value,
                agent_state=AgentState.ESCALATED_GUARD_TICKET.value,
                zone=zone.value,
                duration_sec=duration_sec,
                action_taken=log.message,
                pdpa_mode="SILHOUETTE",
            )
        return log

    def create_jmb_cleaner_ticket(
        self,
        report: WaterClarityReport,
    ) -> ToolExecutionLog:
        """System 2 Off-Peak Water QA: Auto-open JMB cleaner work order for debris or algae drift."""
        severity = "HIGH" if report.status == "MONSOON_DEBRIS_ALERT" else "MEDIUM"
        log = ToolExecutionLog(
            tool_name="create_jmb_cleaner_ticket",
            system_path="SYSTEM_2",
            zone=PoolZone.ZONE_B_DEEP_END,
            track_id=None,
            message=(
                f"[JMB CLEANER TICKET] {report.status}: Turbidity={report.turbidity_score:.1f}/100, "
                f"GreenIndex={report.algae_green_index:.1f}, Debris={report.floating_debris_count}. "
                f"Action: {report.recommended_action}"
            ),
            audio_tts_text=None,
            guard_route_hint="JMB Facility Maintenance Store -> Skimmer & Backwash Manifold",
        )
        self.execution_history.append(log)
        if self.db_conn is not None:
            insert_maintenance_ticket(
                self.db_conn,
                timestamp=log.timestamp.isoformat(),
                ticket_type=report.status,
                severity=severity,
                turbidity_score=report.turbidity_score,
                algae_green_index=report.algae_green_index,
                debris_count=report.floating_debris_count,
                status="OPEN",
                assigned_to="JMB Morning Pool Cleaning Crew",
                notes=report.recommended_action,
            )
        return log

    def trigger_unattended_item_nudge(
        self,
        *,
        object_id: str,
        zone: PoolZone,
        label: str,
        duration_sec: float,
    ) -> ToolExecutionLog:
        """System 2 (Unattended Object): Play ambient audio nudge for unattended items near pool coping."""
        tts = (
            f"Notice from Township Pool Management: Unattended {label} detected at the {zone.value} pool edge. "
            f"For community safety and water hygiene, please place items at designated deck lounge tables. Thank you!"
        )
        log = ToolExecutionLog(
            tool_name="trigger_unattended_item_nudge",
            system_path="SYSTEM_2",
            zone=zone,
            track_id=None,
            message=(
                f"[UNATTENDED_OBJECT_NUDGE @ {duration_sec:.1f}s] Unattended {label} (ID: {object_id}) "
                f"at {zone.value} pool coping for {duration_sec:.1f}s. Played ambient audio reminder."
            ),
            audio_tts_text=tts,
            guard_route_hint=None,
        )
        self.execution_history.append(log)
        return log

    def dispatch_unattended_item_housekeeping_ticket(
        self,
        *,
        object_id: str,
        zone: PoolZone,
        label: str,
        duration_sec: float,
    ) -> ToolExecutionLog:
        """System 2 (Unattended Object >20s): Dispatch housekeeping ticket to clear hazardous items."""
        route = ZONE_ENTRY_ROUTES.get(zone, ZONE_ENTRY_ROUTES[PoolZone.POOL_DECK])
        log = ToolExecutionLog(
            tool_name="dispatch_unattended_item_housekeeping_ticket",
            system_path="SYSTEM_2",
            zone=zone,
            track_id=None,
            message=(
                f"[HOUSEKEEPING_TICKET @ {duration_sec:.1f}s] Unattended {label} (ID: {object_id}) "
                f"uncollected at {zone.value} coping for {duration_sec:.1f}s. Dispatched housekeeping cleaner ticket."
            ),
            audio_tts_text=None,
            guard_route_hint=route,
        )
        self.execution_history.append(log)
        if self.db_conn is not None:
            insert_maintenance_ticket(
                self.db_conn,
                timestamp=log.timestamp.isoformat(),
                ticket_type="UNATTENDED_POOLSIDE_HAZARD",
                severity="LOW",
                turbidity_score=0.0,
                algae_green_index=0.0,
                debris_count=1,
                status="OPEN",
                assigned_to="JMB Pool Deck Housekeeping Crew",
                notes=f"Clear unattended {label} from {zone.value} pool coping (ID: {object_id}).",
            )
        return log
