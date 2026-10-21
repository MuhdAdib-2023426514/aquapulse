#!/usr/bin/env python3
"""Comprehensive 6-Pillar Hackathon Rubric, System 1 p99 Latency, PDPA Frame & UI Contract Auditor."""

from __future__ import annotations

import ast
import statistics
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aquapulse.api.main import AquaPulseRuntimeService  # noqa: E402
from aquapulse.config import SYS1_MAX_LATENCY_MS  # noqa: E402
from aquapulse.mcp_server import (  # noqa: E402
    audit_esg_and_sqlite_telemetry,
    audit_hackathon_rubric_and_contracts,
    handle_jsonrpc_message,
    render_and_verify_pdpa_frames,
    simulate_scenario_timeline,
)
from aquapulse.schemas import ScenarioName  # noqa: E402
from aquapulse.vision.detector import synthesize_scenario_frame  # noqa: E402


def check_streamlit_scenario_parity() -> tuple[bool, str]:
    """Verify every ScenarioName in schemas.py is mapped in app/streamlit_app.py SCENARIO_LABELS."""
    app_path = PROJECT_ROOT / "app" / "streamlit_app.py"
    source = app_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    found_scenarios: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "ScenarioName":
                found_scenarios.add(node.attr)

    expected = {s.name for s in ScenarioName}
    missing = expected - found_scenarios
    if missing:
        return False, f"Missing ScenarioName mappings in streamlit_app.py: {sorted(missing)}"
    return True, f"All {len(expected)} ScenarioName enum values are mapped in streamlit_app.py"


def benchmark_system1_p99_latency(iterations: int = 100) -> tuple[bool, str]:
    """Benchmark System 1 synchronous reflex over 100 ticks and verify p99 & max < 30.0ms."""
    svc = AquaPulseRuntimeService(db_path=":memory:")
    _, tracks, _ = synthesize_scenario_frame(
        ScenarioName.PEAK_CROWD_SURGE_ECO_DRIVE, elapsed_sec=12.0
    )
    latencies: list[float] = []
    for _ in range(iterations):
        trace, _ = svc.state_machine.step_system1_reflex(tracks, dt_sec=0.5)
        latencies.append(trace.execution_latency_ms)

    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[int(iterations * 0.95) - 1]
    p99 = latencies[int(iterations * 0.99) - 1]
    max_lat = latencies[-1]
    ok = max_lat < SYS1_MAX_LATENCY_MS
    msg = (
        f"14-Swimmer System 1 Benchmark ({iterations} ticks): "
        f"p50={p50:.3f}ms, p95={p95:.3f}ms, p99={p99:.3f}ms, max={max_lat:.3f}ms "
        f"(Budget < {SYS1_MAX_LATENCY_MS}ms)"
    )
    return ok, msg


def verify_mcp_server_jsonrpc() -> tuple[bool, str]:
    """Smoke-test all JSON-RPC 2.0 endpoints of aquapulse.mcp_server."""
    init_resp = handle_jsonrpc_message(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    )
    list_resp = handle_jsonrpc_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    if not init_resp or not list_resp:
        return False, "MCP initialize or tools/list returned None"

    tools = list_resp.get("result", {}).get("tools", [])
    tool_names = [t["name"] for t in tools]
    expected_tools = [
        "simulate_scenario_timeline",
        "render_and_verify_pdpa_frames",
        "audit_esg_and_sqlite_telemetry",
        "audit_hackathon_rubric_and_contracts",
    ]
    if tool_names != expected_tools:
        return False, f"Unexpected MCP tools: {tool_names}"

    for idx, tname in enumerate(expected_tools, start=10):
        call_resp = handle_jsonrpc_message(
            {
                "jsonrpc": "2.0",
                "id": idx,
                "method": "tools/call",
                "params": {"name": tname, "arguments": {}},
            }
        )
        if not call_resp or call_resp.get("result", {}).get("isError"):
            return False, f"MCP tool {tname} failed: {call_resp}"

    return True, f"All {len(expected_tools)} MCP tools verified over JSON-RPC 2.0"


def main() -> int:
    print("=" * 76)
    print("🌊 AQUAPULSE HACKATHON RUBRIC, LATENCY, PDPA & MCP AUDIT")
    print("=" * 76)

    checks: list[tuple[str, bool, str]] = []

    ok_ui, msg_ui = check_streamlit_scenario_parity()
    checks.append(("Streamlit <-> Schema Scenario Parity", ok_ui, msg_ui))

    ok_lat, msg_lat = benchmark_system1_p99_latency(100)
    checks.append(("System 1 (<30ms) 100-Tick Tail Latency", ok_lat, msg_lat))

    ok_mcp, msg_mcp = verify_mcp_server_jsonrpc()
    checks.append(("AquaPulse MCP Server JSON-RPC Suite", ok_mcp, msg_mcp))

    for name, passed, detail in checks:
        mark = "✅ PASS" if passed else "❌ FAIL"
        print(f"{mark} | {name}: {detail}")

    print("\n" + "-" * 76)
    print(simulate_scenario_timeline("SILENT_DROWNING_RESCUE", "0,10,20"))
    print("\n" + "-" * 76)
    print(render_and_verify_pdpa_frames("COTTON_TSHIRT_AND_FOOD_NUDGE", 16.0))
    print("\n" + "-" * 76)
    print(audit_esg_and_sqlite_telemetry())
    print("\n" + "-" * 76)
    print(audit_hackathon_rubric_and_contracts())
    print("=" * 76)

    if not all(ok for _, ok, _ in checks):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
