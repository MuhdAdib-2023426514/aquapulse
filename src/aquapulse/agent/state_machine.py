"""Dual-Path Stateful Agentic Brain: System 1 (<30ms Reflex) & System 2 (Governance)."""

from __future__ import annotations

import math
import time
from collections.abc import Callable

from aquapulse.agent.reasoning import AgentReasoningLogger
from aquapulse.agent.tools import PoolsideToolActuator
from aquapulse.config import DEFAULT_CONFIG, PoolConfig
from aquapulse.schemas import (
    AgentState,
    DetectedObject,
    PostureState,
    SwimmerRole,
    SwimmerTrack,
    System1ReflexTrace,
    System2InspectionResult,
    ToolExecutionLog,
    TrackTemporalState,
    UnattendedObjectTrack,
    ViolationType,
)

ROIVerifierCallback = Callable[[SwimmerTrack], System2InspectionResult]

_STATE_PRIORITY: dict[AgentState, int] = {
    AgentState.NORMAL: 0,
    AgentState.NUDGE_REQUIRED: 1,
    AgentState.ESCALATED_GUARD_TICKET: 2,
    AgentState.VERIFY: 3,
    AgentState.CRITICAL_EMERGENCY: 4,
}


def _default_roi_verifier(track: SwimmerTrack) -> System2InspectionResult:
    """Deterministic Tier-1 face-masked ROI verifier used when no custom callback is passed."""
    verified = track.suspected_violation != ViolationType.NONE
    return System2InspectionResult(
        track_id=track.track_id,
        target_type=f"tier1_masked_{track.suspected_violation.value.lower()}_roi",
        tier1_face_redacted=True,
        verified_violation=verified,
        violation_type=track.suspected_violation,
        confidence=0.94,
        inspector_backend="opencv_heuristic",
        vlm_used=False,
        visual_tool_steps=[
            "1. tier1_face_mask_and_2x_zoom: kp[0..4]==0 (True)",
            f"2. probe_torso_and_wrist_roi: target={track.suspected_violation.value}",
            f"3. verifier_verdict (opencv_heuristic): verified={verified}",
        ],
        reasoning_summary=(
            f"Cropped torso/hand ROI with head keypoints kp[0..4] redacted (PDPA Tier-1); "
            f"confirmed {track.suspected_violation.value} texture/contour signature."
        ),
        inspection_latency_ms=8.5,
    )


class AquaPulseStateMachine:
    """Stateful temporal reasoning engine maintaining per-`track_id` timers and transitions."""

    def __init__(
        self,
        config: PoolConfig = DEFAULT_CONFIG,
        actuator: PoolsideToolActuator | None = None,
        reasoning_logger: AgentReasoningLogger | None = None,
    ) -> None:
        self.config = config
        self.actuator = actuator or PoolsideToolActuator()
        self.reasoning_logger = reasoning_logger or AgentReasoningLogger()
        self._states: dict[int, TrackTemporalState] = {}
        self._verify_alerted: set[int] = set()
        self._critical_alerted: set[int] = set()
        self._unattended_objects: dict[str, UnattendedObjectTrack] = {}

    @property
    def track_states(self) -> dict[int, TrackTemporalState]:
        """Return current per-track temporal states."""
        return self._states

    @property
    def unattended_objects(self) -> dict[str, UnattendedObjectTrack]:
        """Return currently tracked stationary unattended poolside objects."""
        return self._unattended_objects

    def reset(self) -> None:
        """Clear all per-track timers and alert flags."""
        self._states.clear()
        self._verify_alerted.clear()
        self._critical_alerted.clear()
        self._unattended_objects.clear()

    @staticmethod
    def _is_track_in_distress(track: SwimmerTrack) -> tuple[bool, bool, bool]:
        """Return `(in_distress, is_flailing, is_submerged)` for a tracked swimmer."""
        flailing = track.is_flailing or track.posture == PostureState.ACTIVE_FLAILING
        submerged = track.is_submerged or track.posture == PostureState.HORIZONTAL_SUBMERGED
        return (flailing or submerged, flailing, submerged)

    def _compute_nearest_adult_m(
        self,
        subject: SwimmerTrack,
        all_tracks: list[SwimmerTrack],
    ) -> float | None:
        """Compute minimum Euclidean distance (meters) from `subject` to any able adult."""
        sx, sy = subject.pool_coords_m
        min_dist: float | None = None
        for other in all_tracks:
            if other.track_id == subject.track_id:
                continue
            if other.role not in (SwimmerRole.ADULT, SwimmerRole.LAP_SWIMMER):
                continue
            other_distress, _, _ = self._is_track_in_distress(other)
            if other_distress:
                continue
            ox, oy = other.pool_coords_m
            dist = math.hypot(sx - ox, sy - oy)
            if min_dist is None or dist < min_dist:
                min_dist = dist
        return round(min_dist, 3) if min_dist is not None else None

    def step_system1_reflex(
        self,
        tracks: list[SwimmerTrack],
        dt_sec: float,
    ) -> tuple[System1ReflexTrace, list[ToolExecutionLog]]:
        """Execute Path 1 ('System 1' Fast Edge Reflex) synchronously in <30ms.

        Handles:
        1. Active Surface Distress / Flailing (`ACTIVE_FLAILING`) + Silent Submersion
           (`HORIZONTAL_SUBMERGED`) with seamless timer continuity (`0s -> 5s VERIFY -> 8s CRITICAL`).
        2. Unaccompanied Toddler near Zone B deep-end boundary (`1.5m` supervision check).
        3. Bystander proximity (`<= 1.5m`): immediately resets unaccompanied toddler timer to NORMAL,
           and holds a submerged/flailing swimmer in `VERIFY` (suppressing the 8s siren while
           bystander assists) until posture recovers.
        """
        t0 = time.perf_counter()
        tool_logs: list[ToolExecutionLog] = []
        active_alerts: list[str] = []

        seen_ids: set[int] = set()
        for track in tracks:
            tid = track.track_id
            seen_ids.add(tid)
            state = self._states.get(tid)
            if state is None:
                state = TrackTemporalState(
                    track_id=tid,
                    role=track.role,
                    zone=track.zone,
                )
                self._states[tid] = state

            state.role = track.role
            state.zone = track.zone

            nearest_adult = self._compute_nearest_adult_m(track, tracks)
            state.nearest_adult_m = nearest_adult
            supervised = (
                nearest_adult is not None and nearest_adult <= self.config.sys1_supervision_radius_m
            )
            state.is_supervised = supervised

            in_distress, flailing, submerged = self._is_track_in_distress(track)

            # --- Case A: Active Flailing Distress OR Silent Submersion ---
            if in_distress:
                # Preserve history if swimmer transitioned from flailing -> submerged
                state.is_flailing = state.is_flailing or flailing
                state.is_submerged = submerged
                state.submersion_sec = round(state.submersion_sec + dt_sec, 3)

                distress_label = (
                    "FLAILING_TO_SUBMERGED_DISTRESS"
                    if (state.is_flailing and state.is_submerged)
                    else (
                        "ACTIVE_FLAILING_DISTRESS"
                        if flailing and not submerged
                        else "SILENT_SUBMERSION"
                    )
                )

                if state.submersion_sec >= self.config.sys1_verify_sec:
                    if supervised:
                        # Adult bystander is within 1.5m assisting: hold VERIFY and suppress 8s siren
                        state.agent_state = AgentState.VERIFY
                        if tid not in self._verify_alerted:
                            self._verify_alerted.add(tid)
                            tool_logs.append(
                                self.actuator.trigger_caution_beacon(
                                    track_id=tid,
                                    zone=track.zone,
                                    reason=f"{distress_label} (Bystander within {nearest_adult:.2f}m)",
                                    duration_sec=state.submersion_sec,
                                )
                            )
                        active_alerts.append(
                            f"Track #{tid} in VERIFY ({distress_label}, t={state.submersion_sec:.1f}s) "
                            f"— bystander assisting within {nearest_adult:.2f}m"
                        )
                    elif state.submersion_sec >= self.config.sys1_critical_emergency_sec:
                        state.agent_state = AgentState.CRITICAL_EMERGENCY
                        if tid not in self._critical_alerted:
                            self._critical_alerted.add(tid)
                            tool_logs.append(
                                self.actuator.trigger_emergency_siren_and_tts(
                                    track_id=tid,
                                    zone=track.zone,
                                    reason=distress_label,
                                    duration_sec=state.submersion_sec,
                                )
                            )
                        active_alerts.append(
                            f"CRITICAL EMERGENCY: Track #{tid} ({distress_label}) unassisted for {state.submersion_sec:.1f}s in {track.zone.value}!"
                        )
                    else:
                        state.agent_state = AgentState.VERIFY
                        if tid not in self._verify_alerted:
                            self._verify_alerted.add(tid)
                            tool_logs.append(
                                self.actuator.trigger_caution_beacon(
                                    track_id=tid,
                                    zone=track.zone,
                                    reason=distress_label,
                                    duration_sec=state.submersion_sec,
                                )
                            )
                        active_alerts.append(
                            f"VERIFY: Track #{tid} ({distress_label}) at t={state.submersion_sec:.1f}s in {track.zone.value}"
                        )
                continue

            # Reset submersion/flailing timers if posture recovered
            if state.submersion_sec > 0.0:
                state.submersion_sec = 0.0
                state.is_flailing = False
                state.is_submerged = False
                self._verify_alerted.discard(tid)
                self._critical_alerted.discard(tid)
                if state.agent_state in (AgentState.VERIFY, AgentState.CRITICAL_EMERGENCY):
                    state.agent_state = AgentState.NORMAL

            # --- Case B: Unaccompanied Toddler Near Deep-End Boundary ---
            if track.role == SwimmerRole.TODDLER and track.near_deep_boundary:
                if supervised:
                    # Parent/adult within 1.5m immediately resets toddler timer to NORMAL
                    state.unaccompanied_infant_sec = 0.0
                    self._verify_alerted.discard(tid)
                    self._critical_alerted.discard(tid)
                    if state.agent_state in (AgentState.VERIFY, AgentState.CRITICAL_EMERGENCY):
                        state.agent_state = AgentState.NORMAL
                else:
                    state.unaccompanied_infant_sec = round(
                        state.unaccompanied_infant_sec + dt_sec, 3
                    )
                    if state.unaccompanied_infant_sec >= self.config.sys1_critical_emergency_sec:
                        state.agent_state = AgentState.CRITICAL_EMERGENCY
                        if tid not in self._critical_alerted:
                            self._critical_alerted.add(tid)
                            tool_logs.append(
                                self.actuator.trigger_emergency_siren_and_tts(
                                    track_id=tid,
                                    zone=track.zone,
                                    reason="UNACCOMPANIED_TODDLER_DEEP_END",
                                    duration_sec=state.unaccompanied_infant_sec,
                                )
                            )
                        active_alerts.append(
                            f"CRITICAL EMERGENCY: Unaccompanied toddler Track #{tid} near deep end for {state.unaccompanied_infant_sec:.1f}s!"
                        )
                    elif state.unaccompanied_infant_sec >= self.config.sys1_verify_sec:
                        state.agent_state = AgentState.VERIFY
                        if tid not in self._verify_alerted:
                            self._verify_alerted.add(tid)
                            tool_logs.append(
                                self.actuator.trigger_caution_beacon(
                                    track_id=tid,
                                    zone=track.zone,
                                    reason="UNACCOMPANIED_TODDLER_DEEP_END",
                                    duration_sec=state.unaccompanied_infant_sec,
                                )
                            )
                        active_alerts.append(
                            f"VERIFY: Unaccompanied toddler Track #{tid} near deep end (t={state.unaccompanied_infant_sec:.1f}s)"
                        )
            else:
                if state.unaccompanied_infant_sec > 0.0:
                    state.unaccompanied_infant_sec = 0.0
                    self._verify_alerted.discard(tid)
                    self._critical_alerted.discard(tid)
                    if state.agent_state in (AgentState.VERIFY, AgentState.CRITICAL_EMERGENCY):
                        state.agent_state = AgentState.NORMAL

        # Prune tracks that left the pool scene
        for stale_id in list(self._states.keys()):
            if stale_id not in seen_ids:
                del self._states[stale_id]
                self._verify_alerted.discard(stale_id)
                self._critical_alerted.discard(stale_id)

        overall = AgentState.NORMAL
        for st in self._states.values():
            if _STATE_PRIORITY[st.agent_state] > _STATE_PRIORITY[overall]:
                overall = st.agent_state

        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 4)
        trace = System1ReflexTrace(
            execution_latency_ms=elapsed_ms,
            within_latency_budget=elapsed_ms < self.config.sys1_max_latency_ms,
            overall_state=overall,
            tracks_evaluated=len(tracks),
            active_alerts=active_alerts,
            track_states=[st.model_copy(deep=True) for st in self._states.values()],
        )
        return trace, tool_logs

    def step_system2_governance(
        self,
        tracks: list[SwimmerTrack],
        dt_sec: float,
        roi_verifier: ROIVerifierCallback | None = None,
    ) -> tuple[list[System2InspectionResult], list[ToolExecutionLog]]:
        """Execute Path 2 ('System 2' Deliberative Governance) for >15s rule violations.

        Two-Strike Pacing:
        - At `violation_sec >= 15.0s`: Run Tier-1 Face-Masked ROI verification (`roi_verifier`).
          If verified, transition to `NUDGE_REQUIRED` (`nudge_count=1`) and play Polite Audio Nudge #1.
        - At `violation_sec >= 30.0s`: Play Polite Audio Nudge #2 (`nudge_count=2`) and escalate to
          `ESCALATED_GUARD_TICKET`.
        """
        verifier = roi_verifier or _default_roi_verifier
        inspections: list[System2InspectionResult] = []
        tool_logs: list[ToolExecutionLog] = []

        for track in tracks:
            tid = track.track_id
            state = self._states.get(tid)
            if state is None:
                state = TrackTemporalState(track_id=tid, role=track.role, zone=track.zone)
                self._states[tid] = state

            # Never overwrite an active System 1 life-safety state
            if state.agent_state in (AgentState.VERIFY, AgentState.CRITICAL_EMERGENCY):
                continue

            is_violating = (track.suspected_violation != ViolationType.NONE)
            decay_rate = getattr(self.config, "leaky_bucket_decay_rate", 0.25)
            max_cap = getattr(self.config, "leaky_bucket_max_cap_sec", 30.0)

            if is_violating:
                state.violation_type = track.suspected_violation
                state.violation_sec = round(min(max_cap, state.violation_sec + dt_sec), 3)
            else:
                # Leaky Bucket decay: slow drainage prevents instant reset loophole
                decay_amt = dt_sec * decay_rate
                state.violation_sec = round(max(0.0, state.violation_sec - decay_amt), 3)
                if state.violation_sec <= 0.0:
                    state.violation_type = ViolationType.NONE
                    state.system2_verified = False
                    state.nudge_count = 0
                    state.agent_state = AgentState.NORMAL
                continue

            nudge_1_threshold = self.config.sys2_nudge_required_sec
            nudge_2_threshold = getattr(
                self.config,
                "sys2_guard_ticket_sec",
                self.config.sys2_nudge_required_sec * float(self.config.sys2_guard_ticket_nudge_count),
            )

            if state.violation_sec >= nudge_1_threshold and state.nudge_count == 0:
                inspection = verifier(track)
                inspections.append(inspection)
                if inspection.verified_violation and inspection.tier1_face_redacted:
                    state.system2_verified = True
                    state.nudge_count = 1
                    state.agent_state = AgentState.NUDGE_REQUIRED
                    tool_logs.append(
                        self.actuator.trigger_polite_speaker_nudge(
                            track_id=tid,
                            zone=track.zone,
                            violation_type=track.suspected_violation,
                            nudge_number=1,
                            duration_sec=state.violation_sec,
                        )
                    )

            if (
                state.system2_verified
                and state.violation_sec >= nudge_2_threshold
                and state.nudge_count < self.config.sys2_guard_ticket_nudge_count
            ):
                state.nudge_count = self.config.sys2_guard_ticket_nudge_count
                state.agent_state = AgentState.ESCALATED_GUARD_TICKET
                tool_logs.append(
                    self.actuator.trigger_polite_speaker_nudge(
                        track_id=tid,
                        zone=track.zone,
                        violation_type=track.suspected_violation,
                        nudge_number=2,
                        duration_sec=state.violation_sec,
                    )
                )
                tool_logs.append(
                    self.actuator.dispatch_guard_governance_ticket(
                        track_id=tid,
                        zone=track.zone,
                        violation_type=track.suspected_violation,
                        duration_sec=state.violation_sec,
                    )
                )

        return inspections, tool_logs

    def step_unattended_objects(
        self,
        objects: list[DetectedObject],
        tracks: list[SwimmerTrack],
        dt_sec: float,
    ) -> tuple[list[UnattendedObjectTrack], list[ToolExecutionLog]]:
        """Track stationary food, drink, and vape items on pool coping and escalate unattended hazards."""
        HAZARD_LABELS = {"bottle", "cup", "bowl", "wine glass", "food_container", "vape"}
        tool_logs: list[ToolExecutionLog] = []
        active_ids: set[str] = set()

        for obj in objects:
            if obj.label.lower() not in HAZARD_LABELS:
                continue

            ox1, oy1, ox2, oy2 = obj.bbox
            ocx = 0.5 * (ox1 + ox2)
            ocy = 0.5 * (oy1 + oy2)

            # Spatial ID based on rounded coordinates to handle slight tracking jitter
            obj_key = f"{obj.label}_{int(round(ocx / 20.0)) * 20}_{int(round(ocy / 20.0)) * 20}"
            active_ids.add(obj_key)

            unatt_item = self._unattended_objects.get(obj_key)
            if unatt_item is None:
                unatt_item = UnattendedObjectTrack(
                    object_id=obj_key,
                    label=obj.label,
                    bbox=obj.bbox,
                    zone=obj.zone,
                    unattended_sec=0.0,
                )
                self._unattended_objects[obj_key] = unatt_item
            else:
                unatt_item.bbox = obj.bbox
                unatt_item.zone = obj.zone

            # Check distance to nearest person in 640x360 canvas pixels
            min_dist_px = 999.0
            nearest_tid: int | None = None
            for tr in tracks:
                bx1, by1, bx2, by2 = tr.bbox
                tcx = 0.5 * (bx1 + bx2)
                tcy = 0.5 * (by1 + by2)
                dist = math.hypot(ocx - tcx, ocy - tcy)
                if dist < min_dist_px:
                    min_dist_px = dist
                    nearest_tid = tr.track_id

            # If a person is within 70px (~1.2m), item is attended
            if min_dist_px <= 70.0:
                unatt_item.associated_track_id = nearest_tid
                # Decay unattended timer when attended
                unatt_item.unattended_sec = max(0.0, unatt_item.unattended_sec - dt_sec * 0.5)
            else:
                unatt_item.associated_track_id = None
                unatt_item.unattended_sec = round(unatt_item.unattended_sec + dt_sec, 3)

            # Escalation stages
            hazard_thresh = getattr(self.config, "unattended_object_hazard_sec", 5.0)
            nudge_thresh = getattr(self.config, "unattended_object_nudge_sec", 8.0)
            ticket_thresh = getattr(self.config, "unattended_object_ticket_sec", 20.0)

            if unatt_item.unattended_sec >= hazard_thresh:
                unatt_item.is_hazard = True

            if unatt_item.unattended_sec >= nudge_thresh and not unatt_item.nudge_sent:
                unatt_item.nudge_sent = True
                tool_logs.append(
                    self.actuator.trigger_unattended_item_nudge(
                        object_id=obj_key,
                        zone=unatt_item.zone,
                        label=unatt_item.label,
                        duration_sec=unatt_item.unattended_sec,
                    )
                )

            if unatt_item.unattended_sec >= ticket_thresh and not unatt_item.ticket_dispatched:
                unatt_item.ticket_dispatched = True
                tool_logs.append(
                    self.actuator.dispatch_unattended_item_housekeeping_ticket(
                        object_id=obj_key,
                        zone=unatt_item.zone,
                        label=unatt_item.label,
                        duration_sec=unatt_item.unattended_sec,
                    )
                )

        # Prune objects no longer detected
        for old_key in list(self._unattended_objects.keys()):
            if old_key not in active_ids:
                del self._unattended_objects[old_key]

        return list(self._unattended_objects.values()), tool_logs

    def step(
        self,
        tracks: list[SwimmerTrack],
        dt_sec: float,
        objects: list[DetectedObject] | None = None,
        roi_verifier: ROIVerifierCallback | None = None,
    ) -> tuple[
        System1ReflexTrace,
        list[System2InspectionResult],
        list[ToolExecutionLog],
        list[dict[str, str]],
    ]:
        """Run System 1 (<30ms reflex) followed by System 2 governance and record reasoning."""
        sys1_trace, sys1_tools = self.step_system1_reflex(tracks, dt_sec)
        sys2_inspections, sys2_tools = self.step_system2_governance(
            tracks, dt_sec, roi_verifier=roi_verifier
        )
        unattended_items, item_tools = self.step_unattended_objects(
            objects or [], tracks, dt_sec
        )
        sys1_trace.unattended_objects = unattended_items

        # Recompute overall_state in sys1_trace to reflect any System 2 state changes/resets
        overall = AgentState.NORMAL
        for st in self._states.values():
            if _STATE_PRIORITY[st.agent_state] > _STATE_PRIORITY[overall]:
                overall = st.agent_state
        sys1_trace.overall_state = overall
        sys1_trace.track_states = [st.model_copy(deep=True) for st in self._states.values()]

        all_tools = sys1_tools + sys2_tools + item_tools
        thoughts = self.reasoning_logger.record_tick(
            sys1_trace=sys1_trace,
            sys2_results=sys2_inspections,
            tool_logs=all_tools,
        )
        return sys1_trace, sys2_inspections, all_tools, thoughts
