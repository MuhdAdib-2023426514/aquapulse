"""Unit tests for the AquaPulse Domain Inspector & Simulator MCP Server (`mcp_server.py`)."""

from __future__ import annotations

from aquapulse.mcp_server import (
    audit_esg_and_sqlite_telemetry,
    audit_hackathon_rubric_and_contracts,
    handle_jsonrpc_message,
    render_and_verify_pdpa_frames,
    simulate_scenario_timeline,
)


def test_mcp_jsonrpc_initialize_and_tools_list() -> None:
    """Verify MCP JSON-RPC 2.0 initialize, ping, and tools/list responses."""
    init_resp = handle_jsonrpc_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        }
    )
    assert init_resp is not None
    assert init_resp["result"]["serverInfo"]["name"] == "aquapulse_inspector"

    # Notification (no id) must return None
    notif_resp = handle_jsonrpc_message({"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert notif_resp is None

    list_resp = handle_jsonrpc_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert list_resp is not None
    tool_names = [t["name"] for t in list_resp["result"]["tools"]]
    assert "simulate_scenario_timeline" in tool_names
    assert "render_and_verify_pdpa_frames" in tool_names
    assert "audit_esg_and_sqlite_telemetry" in tool_names
    assert "audit_hackathon_rubric_and_contracts" in tool_names


def test_mcp_tools_execution() -> None:
    """Verify all 4 AquaPulse MCP tools execute cleanly and validate domain invariants."""
    sim_out = simulate_scenario_timeline("SILENT_DROWNING_RESCUE", "0,5,8")
    assert "VERIFY" in sim_out
    assert "CRITICAL_EMERGENCY" in sim_out

    pdpa_out = render_and_verify_pdpa_frames("COTTON_TSHIRT_AND_FOOD_NUDGE", 16.0)
    assert "Tier-2 Blueprint Check  : PASSED" in pdpa_out
    assert "Max Pixel = 0 (Redacted=True)" in pdpa_out

    esg_out = audit_esg_and_sqlite_telemetry()
    assert "720 Hourly Rows Seeded: True" in esg_out
    assert "30-Day Turnover Floor >= 3.5x: True" in esg_out
    assert "Pump Affinity Law @ 40% == 0.352 kW" in esg_out

    sql_out = audit_esg_and_sqlite_telemetry(
        "SELECT COUNT(*) AS cnt FROM hourly_telemetry WHERE vfd_speed_pct >= 40.0"
    )
    assert '"cnt": 720' in sql_out

    rubric_out = audit_hackathon_rubric_and_contracts()
    assert "ALL RUBRIC GATES PASSED" in rubric_out
