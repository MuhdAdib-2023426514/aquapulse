---
name: aquapulse-verify
description: >-
  End-to-end verification, latency benchmarking, and smoke-testing runbook for the AquaPulse
  swimming pool monitoring system. Use this skill before marking any milestone complete, after
  modifying src/aquapulse/ or app/streamlit_app.py, or when asked to verify that linting, unit
  tests, System 1 (<30ms) safety latency, Two-Tier PDPA silhouette masking, FastAPI endpoints,
  and the Streamlit dashboard work properly.
---

# AquaPulse Milestone Verification & Smoke-Test Runbook

Run this verification checklist inside WSL Ubuntu before completing any milestone or feature slice.

## 1. Quick One-Command Verification Script

Run the bundled verification script inside WSL bash:

```powershell
wsl bash -lc "cd /home/muhammad_adib/swimming_pool_monitoring_system && bash .agents/skills/aquapulse-verify/scripts/verify_milestone.sh"
```

See [verify_milestone.sh](./scripts/verify_milestone.sh) for the automated gate checks.

---

## 2. Step-by-Step Verification Gates

### Gate 1: Environment & Dependency Sync
Ensure the Python `3.12` virtual environment in `.venv` is synced (using CPU-prioritized PyTorch & `opencv-python-headless`):
```powershell
wsl bash -lc "cd /home/muhammad_adib/swimming_pool_monitoring_system && uv sync"
```

### Gate 2: Static Analysis & Formatting (`ruff`)
Must exit with code `0` and zero warnings:
```powershell
wsl bash -lc "cd /home/muhammad_adib/swimming_pool_monitoring_system && uv run ruff check . && uv run ruff format --check ."
```
If formatting fails, auto-fix with:
```powershell
wsl bash -lc "cd /home/muhammad_adib/swimming_pool_monitoring_system && uv run ruff check --fix . && uv run ruff format ."
```

### Gate 3: Automated Pytest Suite & Domain Invariants
Run the full `pytest` suite (must complete in `<5s` offline even without downloaded YOLO weights):
```powershell
wsl bash -lc "cd /home/muhammad_adib/swimming_pool_monitoring_system && uv run pytest -v"
```
Verify that the test suite covers and passes these hackathon-critical invariants:
1. **System 1 Fast Edge Reflex (`<30ms` Latency Budget & Persistent `track_id`)**:
   - Per-`track_id` state machine transition (`NORMAL` $\to$ `VERIFY` at $t = 5.0\text{s}$ $\to$ `CRITICAL_EMERGENCY` at $t = 8.0\text{s}$) and $1.5\text{m}$ pairwise adult-to-infant proximity check execute synchronously in `< 30ms` locally with zero network/LLM calls.
2. **System 2 Deliberative Agentic Vision (`>15s` Governance & Water QA)**:
   - Non-blocking ROI crop/zoom (`crop_and_zoom_roi`) applies **Tier 1 Face Redaction (`kp[0..4]`)** before verifying cotton streetwear, poolside food/drinks, or smoking (with strict `2.0s` timeout and deterministic OpenCV fallback), and only escalates to a guard ticket after 2 ignored polite speaker nudges.
3. **Two-Tier PDPA 2010 & PDPA (Amendment) Act 2024 Privacy Shield**:
   - **Tier 1**: Head/face keypoints (`kp[0..4]`) are blacked out before any ROI crop is inspected by System 2.
   - **Tier 2**: In `silhouette` mode, all UI evidence frames and guard alerts render strictly as neon skeletal silhouettes on a dark pool blueprint with zero raw skin/swimwear pixels.
4. **Planet Track ESG Math (Pump Affinity Law $P \propto N^3$ & Turnover Floor $\ge 3.5\text{ turnovers/day}$)**:
   - Throttling VFD pump speed to $40\%$ reduces instantaneous pump power to $(0.40)^3 = 6.4\%$ of full-speed draw while strictly enforcing `min_daily_turnovers >= 3.5`, accurately computing RM savings (`RM 0.51/kWh`) and carbon reduction (`0.758 kg CO2/kWh`).

### Gate 4: FastAPI & Streamlit Headless Smoke Check (Milestone 5+)
Once `src/aquapulse/api/main.py` and `app/streamlit_app.py` exist, verify that:
1. FastAPI `TestClient` returns `200 OK` on `/health` and scenario simulation endpoints.
2. `app/streamlit_app.py` uses `@st.fragment` for live canvas updates, compiles cleanly (`python -m py_compile app/streamlit_app.py`), and imports without runtime errors.
