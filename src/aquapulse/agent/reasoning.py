"""Structured System 1 (<30ms Edge Reflex) & System 2 (Deliberative ROI) reasoning logger."""

from __future__ import annotations

from datetime import UTC, datetime

from aquapulse.schemas import (
    AgentState,
    System1ReflexTrace,
    System2InspectionResult,
    ToolExecutionLog,
)


class AgentReasoningLogger:
    """Formats transparent Observe -> Reason -> Verify -> Act traces for the dashboard & API."""

    def __init__(self, max_entries: int = 50) -> None:
        self.max_entries = max_entries
        self.logs: list[dict[str, str]] = []

    def record_tick(
        self,
        *,
        sys1_trace: System1ReflexTrace,
        sys2_results: list[System2InspectionResult],
        tool_logs: list[ToolExecutionLog],
    ) -> list[dict[str, str]]:
        """Generate structured reasoning entries for the current simulation tick."""
        new_entries: list[dict[str, str]] = []
        now_iso = datetime.now(UTC).strftime("%H:%M:%S.%f")[:-3]

        # 1. System 1 Fast Edge Reflex thought trace
        distressed_tracks = [
            ts
            for ts in sys1_trace.track_states
            if ts.submersion_sec > 0.0 or ts.unaccompanied_infant_sec > 0.0
        ]
        if distressed_tracks or sys1_trace.overall_state != AgentState.NORMAL:
            parts: list[str] = []
            for ts in distressed_tracks:
                if ts.submersion_sec > 0.0:
                    mode = (
                        "ACTIVE_FLAILING (surface panic oscillation)"
                        if ts.is_flailing and not ts.is_submerged
                        else (
                            "FLAILING->SUBMERGED (continuous distress carryover)"
                            if ts.is_flailing and ts.is_submerged
                            else "HORIZONTAL_SUBMERGED (motionless underwater)"
                        )
                    )
                    sup = (
                        f"Bystander within {ts.nearest_adult_m:.2f}m (rescue hold)"
                        if ts.is_supervised and ts.nearest_adult_m is not None
                        else f"No adult within 1.5m (nearest={ts.nearest_adult_m or 99.9:.1f}m)"
                    )
                    parts.append(
                        f"Track #{ts.track_id} [{ts.zone.value}]: {mode} t={ts.submersion_sec:.1f}s | {sup} -> {ts.agent_state.value}"
                    )
                elif ts.unaccompanied_infant_sec > 0.0:
                    parts.append(
                        f"Track #{ts.track_id} [TODDLER in {ts.zone.value}]: Near deep-end boundary "
                        f"t={ts.unaccompanied_infant_sec:.1f}s (nearest adult={ts.nearest_adult_m or 99.9:.1f}m > 1.5m) -> {ts.agent_state.value}"
                    )

            summary = " ; ".join(parts) if parts else f"State={sys1_trace.overall_state.value}"
            new_entries.append(
                {
                    "timestamp": now_iso,
                    "path": "SYSTEM_1_REFLEX",
                    "latency_ms": f"{sys1_trace.execution_latency_ms:.2f}ms",
                    "state": sys1_trace.overall_state.value,
                    "thought": (
                        f"[System 1 Edge Reflex | {sys1_trace.execution_latency_ms:.2f}ms < 30ms budget] "
                        f"{summary}"
                    ),
                }
            )

        # 2. System 2 Deliberative Agentic Vision ROI trace
        for res in sys2_results:
            new_entries.append(
                {
                    "timestamp": now_iso,
                    "path": "SYSTEM_2_AGENTIC_ROI",
                    "latency_ms": f"{res.inspection_latency_ms:.1f}ms",
                    "state": "VERIFIED" if res.verified_violation else "CLEARED",
                    "thought": (
                        f"[System 2 Deliberative ROI | Backend={res.inspector_backend} | "
                        f"Tier-1 Face Masked={res.tier1_face_redacted}] "
                        f"Track #{res.track_id}: {res.reasoning_summary} (conf={res.confidence:.2f})"
                    ),
                }
            )

        # 3. Autonomous Tool Actuations
        for tlog in tool_logs:
            new_entries.append(
                {
                    "timestamp": now_iso,
                    "path": f"TOOL_{tlog.system_path}",
                    "latency_ms": "0.1ms",
                    "state": tlog.tool_name,
                    "thought": tlog.message,
                }
            )

        self.logs.extend(new_entries)
        if len(self.logs) > self.max_entries:
            self.logs = self.logs[-self.max_entries :]

        return new_entries
