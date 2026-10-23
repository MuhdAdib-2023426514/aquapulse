---
name: aquapulse-rubric-qa
description: >-
  Audits the 6 Sime Darby Property Hackathon Rubric pillars, benchmarks System 1 p95/p99
  latency (<30ms), exports Tier-1/Tier-2 PDPA visual debug frames for inspection, verifies
  Streamlit 4-tab UI & FastAPI schema parity, and smoke-tests the aquapulse_inspector MCP
  server. Use this skill when adding new scenarios/features, debugging Vision/ESG/Streamlit
  issues, or preparing for a live hackathon pitch.
---

# AquaPulse Rubric, Visual QA & Contract Audit Skill

Use this skill alongside `aquapulse-verify` to deeply inspect visual frames, benchmark tail latency, verify Python/FastAPI/Streamlit contract alignment, and audit the 6 Sime Darby Property Hackathon Rubric pillars.

## 1. Run Full Rubric, Latency & Headless UI Audit

Run the bundled Python audit script inside the project virtual environment:

```bash
uv run python .agents/skills/aquapulse-rubric-qa/scripts/audit_rubric_and_ui.py
```

See [audit_rubric_and_ui.py](./scripts/audit_rubric_and_ui.py) for the implementation.

---

## 2. Using the `aquapulse_inspector` MCP Tools

When the `aquapulse_inspector` MCP server ([mcp_server.py](../../../src/aquapulse/mcp_server.py)) is active, invoke its 4 tools directly or via CLI one-liners:

1. **`simulate_scenario_timeline(scenario, timestamps_csv)`**:
   - Steps any `ScenarioName` through `0s, 5s, 8s, 15s, 30s` and prints `System1ReflexTrace`, `TrackTemporalState`s, `System2InspectionResult.visual_tool_steps`, and `ToolExecutionLog`s.
2. **`render_and_verify_pdpa_frames(scenario, elapsed_sec)`**:
   - Exports PNGs into `assets/debug_frames/`:
     - `tier2_silhouette_<scenario>.png` (0% raw biometric pixels)
     - `tier1_roi_<scenario>_track_<id>.png` (head `kp[0..4] == [0, 0, 0]` blacked out + $2\times$ zoom)
     - `water_qa_<scenario>.png` (Laplacian contrast + HSV green-algae drift + monsoon debris contours)
   - After running this tool, use `read_file` on the generated `.png` paths in `assets/debug_frames/` to visually inspect the rendered frames!
3. **`audit_esg_and_sqlite_telemetry(sql_query)`**:
   - Validates all 720 hours in `assets/aquapulse.db`, checks `min_daily_turnovers >= 3.5`, verifies Pump Affinity Law ($0.352\text{ kW}$ at $40\%$), or runs a custom read-only `SELECT` query.
4. **`audit_hackathon_rubric_and_contracts()`**:
   - Runs a 50-tick System 1 latency benchmark (`p50`/`max < 30ms`) and verifies all 7 `ScenarioName` scenarios.

---

## 3. Checklist When Adding or Modifying Features

1. **Schema & UI Parity**:
   - Any new `ScenarioName` added in `src/aquapulse/schemas.py` **must** also be added to `SCENARIO_LABELS` in `app/streamlit_app.py` and handled in `synthesize_scenario_frame` in `src/aquapulse/vision/detector.py`.
2. **Two-Tier PDPA Invariant**:
   - Tier 1 (`apply_tier1_face_mask`): `masked[hy1:hy2, hx1:hx2]` must have `np.max(...) == 0` before any System 2 crop or VLM call.
   - Tier 2 (`render_tier2_silhouette_frame`): Top-left background pixel `(5, 5)` must equal the dark blueprint BGR `(34, 22, 11)`.
3. **System 1 vs. System 2 Separation**:
   - Never call `verify_attire_or_item` or network I/O inside `step_system1_reflex`.
4. **ESG Turnover Floor**:
   - Every 24-hour VFD schedule in `optimize_24h_vfd_schedule` and `seed_30_days_if_empty` must maintain `daily_turnovers >= 3.5`.
