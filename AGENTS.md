# AGENTS.md — AquaPulse (`swimming_pool_monitoring_system`)

> **Project**: **AquaPulse** — Privacy-First Agentic Vision Monitoring & ESG Optimization System for Residential Swimming Pools  
> **Competition**: **Sime Darby Property University Hackathon ("Township of Tomorrow")**  
> **Tracks Targeted**: **People** (Life Safety, Community Harmony, Inclusivity) & **Planet** (Energy & Water Conservation, Low-Carbon Operations)

---

## 1. Mission & Hackathon Rubric Alignment

Every module, endpoint, and UI component in this repository must directly reinforce the **6-part Sime Darby Property Hackathon Judging Rubric**:

1. **Impact & Sustainability Value (25%) — Dynamic "Bather-Load" Pump & Chemical Eco-Drive**
   - Uses vision-derived occupancy and rule-violation telemetry to calculate a real-time **Biological & Contamination Load Score**:
     $$\text{Contamination Score} = (\text{Swimmer Count} \times \text{Duration}) + w_1(\text{Cotton Clothing Violations}) + w_2(\text{Food/Drink Events}) + w_3(\text{Pet/Stray Animal Events})$$
   - Dynamically throttles Variable Frequency Drive (VFD) filtration pumps down to 40% eco-mode during verified zero-occupancy windows and triggers targeted high-filtration purge cycles after peak loads, while strictly maintaining a **Minimum Daily Turnover Floor ($\ge 3.5\text{ turnovers/day}$)** to guarantee baseline sanitation compliance.
   - Applies the **Pump Affinity Law** ($P_2 / P_1 = (N_2 / N_1)^3$) and Malaysian **TNB commercial/strata electricity tariffs (RM/kWh)** + grid carbon intensity ($\text{kg CO}_2\text{/kWh}$) to quantify daily/annual savings (~25–35% energy reduction).

2. **Innovation & Differentiation (20%) — Two-Stage "Lifeguardless" Poolside Intervention**
   - Solves the Malaysian strata condo reality where no lifeguards are on deck and guardhouse security takes 3–5 minutes to arrive.
   - **Stateful Agentic Escalation Loop**:
     - `NORMAL`: Active monitoring of swimmer poses, persistent `track_id`s, zones, and submersion timers.
     - `VERIFY` ($t = 5\text{s}$ motionless/submerged OR unaccompanied infant/toddler within 1.5m of deep-end boundary): Checks whether an adult swimmer is within 1.5m interacting with the subject; activates yellow poolside caution beacon and pre-alerts security.
     - `CRITICAL_EMERGENCY` ($t = 8\text{s}$ confirmed distress with no bystander response): Triggers an **on-site directional siren + TTS voice broadcast** (*"Emergency in Zone B Deep End! Swimmer submerged—nearby residents please assist immediately!"*) to mobilize bystanders within 5 seconds, while dispatching a live zone map and fastest entry route to the guard's smartphone.

3. **Feasibility & Deliverability (20%) — Privacy-Preserving "Skeletal Silhouette Mode" + Polite Audio Nudges**
   - **100% Malaysia PDPA 2010 & PDPA (Amendment) Act 2024 Compliance**: Enforces a **Two-Tier Redaction Architecture** so biometric facial identity is never exposed to cloud APIs or stored on disk, rendering swimmers as **anonymized colored skeletal silhouettes** on a pool zone canvas for all saved logs and UI views.
   - **Frictionless Rule Governance**: When cotton streetwear in water, poolside food/drinks, or smoking persists for $>15\text{s}$, the agent transitions to `NUDGE_REQUIRED` and plays a polite, localized voice nudge via directional speakers. A human security guard ticket is only opened if the resident ignores **2 consecutive nudges** (or $>3$ minutes).

4. **Commercial & Value Multiplication (10%) — Visual Water Clarity & Monsoon Debris Inspector**
   - During calm off-peak hours, OpenCV analyzes pool floor-tile/lane-line contrast (turbidity estimation), color-histogram drift (green algae tint warning before costly pool drainage), and surface object contours (post-storm floating leaves/branches) to auto-create morning cleaning tickets for JMB/MC facility teams.

5. **Strategic Fit & People Track (15%) + Prototype Quality (10%) — Resident App "Crowd & Comfort" Widget**
   - Publishes anonymous live headcount, swimmer profile breakdown (lap swimmers vs. families/infants/seniors), water clarity status, and diurnal **Quiet-Hour Forecasts** so residents can plan visits and JMBs can designate inclusive Senior/Toddler safe hours.

---

## 2. Tech Stack & Architecture

- **Language & Package Manager**: Python `>=3.12` managed strictly via **`uv`**.
- **Backend API & Agent Brain**: **FastAPI** (`uvicorn`, `pydantic`) serving REST endpoints for vision frame processing, scenario simulation, agent state inspection, tool execution logs, and ESG/time-series analytics.
- **AI / Computer Vision Pipeline (Pre-Trained Zero-Shot + Hybrid Mode — No Custom Training Required)**:
  - **Pre-Trained & Heuristic CV Mode (Ultralytics YOLO26 NMS-Free Edge Architecture)**:
    - **`yolo26n-pose.pt` (COCO Pose + ByteTrack — NMS-Free End-to-End)**: Extracts 17 skeletal keypoints with persistent `track_id`s (`model.track(frame, persist=True)`) for swimmer headcount, zone tracking, submersion/horizontal posture geometry, pairwise supervision distance pairing ($1.5\text{m}$), and PDPA facial redaction / skeletal silhouette rendering.
    - **`yolo26n.pt` (COCO Object Detection — NMS-Free End-to-End) + OpenCV HSV/Contour Heuristics**: Detects poolside food/drinks (`bottle`, `cup`, `bowl`, `wine glass`, food items) and stray/pet animals (`cat` #15, `dog` #16, `bird` #14), analyzes torso keypoint polygons (`kp[5,6,11,12]`) for opaque cotton streetwear vs. swimwear, and inspects water clarity (Laplacian tile contrast, HSV green-algae drift, and floating storm debris contours).
  - **Multi-Target Tracking & Two-Tier PDPA Redaction**:
    - **Persistent Swimmer IDs (`track_id: int`)**: Every detected or synthesized person must maintain a consistent `track_id` across frames so `state_machine.py` accurately tracks individual timers (`submersion_sec`, `unaccompanied_infant_sec`, `violation_sec`) and computes pairwise Euclidean distances (`adult_to_infant_m <= 1.5`).
    - **Tier 1 Masking (For System 2 ROI Verification)**: Redact ONLY the head/face bounding box derived from nose/eye/ear keypoints (`kp[0..4]`) before passing the cropped torso/hand ROI to `agentic_inspector.py` (so cotton fabric texture, food containers, or smoke remain visually verifiable while facial biometric identity is never exposed to any VLM/API).
    - **Tier 2 Masking (For UI Display & Evidence Storage)**: Render full **Skeletal Silhouette Mode** (neon keypoints + limb vectors on a dark blueprint pool zone grid, zero raw skin/swimwear pixels) for all saved JMB logs and Guardhouse alerts.
  - **Deterministic Pitch Scenario Injector**: Interactive triggers controllable from Streamlit/FastAPI so live hackathon pitches can deterministically demonstrate:
    1. *Silent Drowning Rescue Loop ($0\text{s} \to 5\text{s} \to 8\text{s}$)*
    2. *Unaccompanied Toddler Near Deep End*
    3. *Cotton T-Shirt / Poolside Food & Smoking Polite Nudge*
    4. *Post-Monsoon Storm Debris & Algae Tint Drift*
    5. *24-Hour Peak Crowd Surge $\to$ VFD Eco-Throttle & Post-Peak Purge*
- **Dual-Path Agentic Architecture: "System 1" (Fast Edge Reflex) vs. "System 2" (Deliberative Agentic Vision)**:
  - **⚡ Path 1 — "System 1" Fast Edge Reflex (`<30ms` Latency — Life Safety Critical Path)**:
    - **Used strictly for**: Silent Drowning / Submersion Tracking & Unaccompanied Toddler Near Deep End.
    - **Zero Cloud / Zero VLM Latency in the Critical Loop**: Runs 100% locally and synchronously using NMS-free `yolo26n-pose.pt` keypoints + `<2ms` NumPy/OpenCV geometry + deterministic Python Temporal State Machine ($5.0\text{s}$ `VERIFY` bystander check $\to$ $8.0\text{s}$ `CRITICAL_EMERGENCY`).
    - Fires local poolside strobe and **pre-cached directional emergency voice broadcast** in milliseconds—guaranteed to work even if condo Wi-Fi/internet is completely offline. Only *after* the emergency alarm is already triggered does an asynchronous task enrich the guardhouse incident log.
  - **🔍 Path 2 — "System 2" Deliberative Agentic Vision (`1–3s` Latency — Governance & Maintenance)**:
    - **Used strictly for**: Non-life-safety tasks where **high precision / zero false resident accusations** matter more than millisecond latency:
      1. *Strata Rule Governance ($>15\text{s}$ `NUDGE_REQUIRED` window)*: Executes a verifiable **3-Step Agentic Vision Tool Chain** (`crop_and_zoom_roi` $\to$ `probe_sub_rois_and_context` $\to$ `verify_attire_or_item`, recorded in `System2InspectionResult.visual_tool_steps`) using OpenCV sub-ROI inspection (torso polygon `kp[5,6,11,12]` HSV/Laplacian fabric analysis, wrist `kp[9,10]` object proximity, and smoke aerosol probe) + optional Gemini Vision (`gemini-3.8-flash`) with a strict `2.0s` timeout and deterministic offline fallback to confirm cotton streetwear (vs. proper Lycra rashguard), food/drinks, pets/stray animals, or smoking before playing a polite directional speaker nudge.
      2. *Off-Peak Visual Water Clarity & Monsoon Debris Inspection*: Periodically crops pool floor-tile lane lines and water surface ROIs during calm windows to verify turbidity, algae green-shift, and floating storm debris before opening a JMB cleaner ticket.
- **Time-Series Storage & Forecasting**:
  - **Embedded SQLite** (`sqlite3` / `SQLAlchemy`) pre-seeded automatically on startup with **30 days of realistic Malaysian high-rise condo pool telemetry** (hourly headcounts, age-group mix, rule violations, water clarity scores, and Fixed vs. VFD pump kWh).
  - **Diurnal Crowd & Contamination Forecaster** (`scikit-learn` / statistical hourly-day-of-week profile) predicting quiet swim windows and optimal VFD pump schedules.
- **Frontend & Testing Workbench**:
  - **4-Tab Streamlit App** (`streamlit`, `plotly`) communicating with the FastAPI backend (with direct in-process service fallback for single-command convenience):
    1. **Tab 1 — Live Vision & Agentic Command Center** (Video/Canvas with PDPA Skeletal Silhouette toggle, Scenario Injector, **System 1 Fast Reflex Timer vs. System 2 Agentic ROI Zoom Inspector**, Live State Machine & Reasoning Log, TTS Directional Speaker Player, Guard Smartphone Alert Card)
    2. **Tab 2 — ESG & VFD Pump Energy Simulator** (Biological Contamination Score gauge, Pump Affinity Law $P \propto N^3$ curve, Minimum Daily Turnover compliance badge, 24h/30d kWh, RM TNB tariff & $\text{kg CO}_2$ savings charts)
    3. **Tab 3 — Visual Water Clarity & Monsoon Debris Inspector** (Turbidity/contrast score, green-index drift chart, surface debris detection overlay, automated JMB cleaner work-order log)
    4. **Tab 4 — Resident Township App "Crowd & Comfort" Widget** (Mobile-styled preview card with live crowd level, lap vs. family activity ratio, quiet-hour forecast, and senior/toddler safe-hour recommendations)

---

## 3. WSL & Shell Execution Rules (CRITICAL FOR AGENTS)

The project lives inside WSL Ubuntu at `/home/muhammad_adib/swimming_pool_monitoring_system` (accessed from Windows via `\\wsl$\ubuntu\home\muhammad_adib\swimming_pool_monitoring_system`).

- **Always run Python, `uv`, pytest, ruff, and server commands inside WSL bash** so the Linux virtual environment (`.venv`) and `/home/muhammad_adib/.local/bin/uv` are used:
  ```powershell
  wsl bash -lc "cd /home/muhammad_adib/swimming_pool_monitoring_system && uv run <command>"
  ```
- **Never install packages globally with `pip`**. Always use `uv add <package>` or `uv add --dev <package>` inside WSL:
  ```powershell
  wsl bash -lc "cd /home/muhammad_adib/swimming_pool_monitoring_system && uv add fastapi uvicorn streamlit"
  ```
- **Fast, Lightweight CPU/WSL Dependency Resolution**:
  - Pin CPU-only PyTorch indices in `pyproject.toml` (unless a dedicated WSL CUDA GPU is required) so `uv sync` completes in seconds rather than downloading ~2.5GB of NVIDIA CUDA wheels.
  - Ensure `opencv-python-headless` is prioritized and prevent `ultralytics` from overriding headless OpenCV in WSL (avoiding missing `libGL.so.1` crashes).
  - Store `yolo26n-pose.pt` and `yolo26n.pt` inside `assets/models/` or auto-fallback gracefully to the **Deterministic Scenario Synthesizer** if model weights are not yet downloaded so `pytest` runs in `<5 seconds` offline.
- If `.venv` is still bound to Python 3.14 when adding ML wheels, recreate it with Python 3.12:
  ```powershell
  wsl bash -lc "cd /home/muhammad_adib/swimming_pool_monitoring_system && uv venv --python 3.12 --allow-existing && uv sync"
  ```

---

## 4. Target Directory Structure

```text
swimming_pool_monitoring_system/
├── AGENTS.md                        # This master architectural & workflow guide
├── README.md                        # Setup, architecture overview, and hackathon pitch guide
├── pyproject.toml                   # uv project metadata, CPU torch index, dependencies, ruff & pytest config
├── .python-version                  # Pinned to 3.12 for ML wheel compatibility
├── src/
│   └── aquapulse/
│       ├── __init__.py
│       ├── config.py                # Thresholds (5s/8s/15s), TNB tariffs (RM/kWh), turnover floor, zone polygons
│       ├── schemas.py               # Pydantic models for detections, track_id, System 1/2 traces, tool calls, ESG metrics
│       ├── db/
│       │   ├── __init__.py
│       │   ├── database.py          # SQLite connection & table initialization
│       │   └── seed.py              # 30-day Malaysian strata condo pool time-series generator
│       ├── vision/
│       │   ├── __init__.py
│       │   ├── detector.py          # Pre-trained YOLO26 Pose/Object tracker + deterministic scenario synthesizer
│       │   ├── agentic_inspector.py # System 2 Agentic Vision (Tier-1 face-masked ROI crop/zoom, attire/item verifier)
│       │   ├── privacy.py           # Two-tier PDPA Face Redactor & full Skeletal Silhouette frame renderer
│       │   └── water_inspector.py   # OpenCV water turbidity, green-algae drift & storm debris analyzer
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── state_machine.py     # System 1 (<30ms) & System 2 stateful temporal reasoning engine (per track_id)
│       │   ├── tools.py             # Autonomous tool actuators (Strobe, Speaker TTS, Guard Dispatch, Cleaner Ticket)
│       │   └── reasoning.py         # Structured System 1/System 2 thought logger (LLM optional + offline fallback)
│       ├── esg/
│       │   ├── __init__.py
│       │   ├── pump_optimizer.py    # Biological Contamination Score, Turnover Floor & Pump Affinity Law VFD calculator
│       │   └── forecaster.py        # Diurnal crowd & quiet-hour forecaster for Resident Widget & Eco-Drive
│       └── api/
│           ├── __init__.py
│           └── main.py              # FastAPI application & REST endpoints (/health, /vision, /agent, /esg, /resident)
├── app/
│   └── streamlit_app.py             # 4-Tab Streamlit interactive prototype & pitch dashboard (using @st.fragment)
├── assets/                          # Generated demo frames, models/, synthetic pool videos, pre-cached TTS audio alerts
└── tests/
    ├── test_state_machine.py        # Verifies System 1 (<30ms 5s/8s rescue) & System 2 (15s ROI-verified nudge)
    ├── test_esg_optimizer.py        # Verifies Contamination Score, Turnover Floor & Pump Affinity Law (P ~ N^3) math
    ├── test_vision_privacy.py       # Verifies Tier-1 face masking, Tier-2 silhouette anonymization & water inspector
    └── test_api.py                  # FastAPI TestClient integration tests for all endpoints
```

---

## 5. Standard Commands & Verification Gates

Before marking any milestone or task complete, the agent **MUST** run and pass the verification commands below:

### Install / Sync Dependencies
```powershell
wsl bash -lc "cd /home/muhammad_adib/swimming_pool_monitoring_system && uv sync"
```

### Run Automated Tests (Pytest)
```powershell
wsl bash -lc "cd /home/muhammad_adib/swimming_pool_monitoring_system && uv run pytest -v"
```

### Run Linter & Formatter (Ruff)
```powershell
wsl bash -lc "cd /home/muhammad_adib/swimming_pool_monitoring_system && uv run ruff check ."
```

### Start FastAPI Backend Server (Port 8000)
```powershell
wsl bash -lc "cd /home/muhammad_adib/swimming_pool_monitoring_system && uv run uvicorn aquapulse.api.main:app --host 0.0.0.0 --port 8000 --reload"
```

### Start Streamlit Prototype Dashboard (Port 8501)
```powershell
wsl bash -lc "cd /home/muhammad_adib/swimming_pool_monitoring_system && uv run streamlit run app/streamlit_app.py --server.port 8501"
```

---

## 6. Engineering & Coding Conventions

1. **Zero-Config Reliability for Live Pitches**:
   - The app must boot and seed its SQLite database automatically on first launch with zero manual setup.
   - If no webcam or external video file is uploaded, the Vision tab must automatically render a rich, animated synthetic pool deck canvas (or sample video loop) with movable/injectable swimmers, skeletal poses, persistent `track_id`s, deep-end zone boundaries, and storm debris so every feature works out-of-the-box.
2. **Two-Tier PDPA Privacy Enforcement (Crucial for System 2 Accuracy)**:
   - *Tier 1 (System 2 ROI Inspector Input)*: Mask only the head/face (`keypoints 0–4`) when cropping the torso/hand ROI for `agentic_inspector.py` so cotton clothing texture, food containers, and smoke remain visually verifiable without exposing facial biometric data.
   - *Tier 2 (UI & Evidence Storage)*: When `privacy_mode="silhouette"` (default), all saved frames, evidence thumbnails, and guard alerts must render swimmers strictly as neon skeletal keypoints/silhouettes on a dark/blueprint pool grid (complying with Malaysia PDPA 2010 & PDPA Amendment Act 2024).
3. **Persistent Multi-Swimmer Tracking (`track_id`)**:
   - Every detected or synthesized swimmer must carry a persistent `track_id: int` across frames so `state_machine.py` accurately tracks individual timers (`submersion_sec`, `unaccompanied_infant_sec`, `violation_sec`) and computes pairwise Euclidean distances (`adult_to_infant_m <= 1.5`).
4. **Non-Blocking System 1 vs. System 2 Concurrency & Offline Fallback**:
   - System 1 (`state_machine.py` life-safety check) MUST execute synchronously in `<30ms` per tick and never block on System 2 I/O or VLM API calls.
   - System 2 (`agentic_inspector.py`) must run asynchronously or via non-blocking cached state transitions with a strict `2.0s` timeout. If `GEMINI_API_KEY` is missing or network fails, `agentic_inspector.py` must seamlessly fall back to deterministic OpenCV HSV/contour heuristics with zero crashes.
5. **Compliant VFD Pump Turnover Floor**:
   - `pump_optimizer.py` must enforce a minimum daily water turnover floor (`min_daily_turnovers: float = 3.5`) alongside the Pump Affinity Law ($P_2 / P_1 = (N_2 / N_1)^3$) so energy savings (~25–35%) never compromise baseline pool sanitation standards.
6. **Smooth Streamlit Live Rendering**:
   - Use `@st.fragment` in `app/streamlit_app.py` for the live Vision Canvas & Agentic State Log panel so ticking the simulation timer ($0\text{s} \to 5\text{s} \to 8\text{s}$) updates smoothly without triggering slow full-page reloads of the Plotly ESG and SQLite analytics tabs.
7. **Malaysian Localization & Domain Realism**:
   - Use **RM (Malaysian Ringgit)** and realistic **TNB commercial/strata tariff rates** (e.g., `RM 0.51 / kWh`), Malaysian grid carbon factor (`0.758 kg CO2 / kWh`), and local township terminology (*JMB/MC, Guardhouse Auxiliary Police, Monsoon Storm Debris, PDPA 2010 & PDPA Amendment Act 2024*).
8. **Clean, Typed, Modular Python**:
   - Use Pydantic v2 models in `schemas.py` for all data contracts between Vision, Agent, ESG, FastAPI, and Streamlit.
   - Keep business logic inside `src/aquapulse/` so both FastAPI endpoints and pytest unit tests exercise the exact same code paths.

---

## 7. Implementation Milestones (Vertical Slices)

- **Milestone 1: Environment, Package Layout & Core Domain Schemas**
  - Configure `pyproject.toml` with `src/` layout (`aquapulse`), CPU-prioritized wheel resolution, and Python 3.12 `.venv`; install core dependencies (`fastapi`, `uvicorn`, `streamlit`, `pydantic`, `opencv-python-headless`, `numpy`, `plotly`, `scikit-learn`, `httpx`, `pytest`, `ruff`, `ultralytics`).
  - Implement `config.py`, `schemas.py` (with `track_id` and System 1/2 trace schemas), and the auto-seeding 30-day Malaysian condo pool SQLite database (`db/`).
- **Milestone 2: Layer 2 & 3 — Dual-Path Stateful Agentic Brain & Autonomous Tools**
  - Build `agent/state_machine.py` (System 1 `<30ms` per-`track_id` life-safety reflex vs. System 2 non-blocking deliberative governance loop), `agent/tools.py`, and `agent/reasoning.py` (with pre-cached/synthesized TTS audio generation + guard/cleaner ticket logs).
  - Verify with `tests/test_state_machine.py` ($10\text{s}$ `VERIFY`, bystander interaction cancel, $20\text{s}$ `CRITICAL_EMERGENCY`, $15\text{s}$ `NUDGE_REQUIRED`).
- **Milestone 3: Layer 1 — Zero-Shot Computer Vision, System 2 Agentic ROI Inspector, Two-Tier PDPA Shield & Water Inspector**
  - Build `vision/detector.py` (pre-trained YOLO26 Pose/Object tracker + deterministic scenario synthesizer), `vision/agentic_inspector.py` (Tier-1 face-masked ROI crop/zoom + attire/item verification), `vision/privacy.py` (Tier-1 face redactor & Tier-2 PDPA skeletal silhouette renderer), and `vision/water_inspector.py` (turbidity, algae tint drift, floating debris).
  - Verify with `tests/test_vision_privacy.py`.
- **Milestone 4: Layer 4 — Bather-Load ESG VFD Pump Optimizer & Crowd Forecaster**
  - Build `esg/pump_optimizer.py` (Biological Contamination Score + Minimum Daily Turnover floor + Pump Affinity Law $P \propto N^3$ RM/$\text{CO}_2$ calculator) and `esg/forecaster.py`.
  - Verify with `tests/test_esg_optimizer.py`.
- **Milestone 5: FastAPI Backend & 4-Tab Streamlit Pitch Dashboard**
  - Expose all layers via `api/main.py` and build the complete 4-tab `app/streamlit_app.py` (using `@st.fragment` for smooth live canvas updates) with live scenario injectors, audio alerts, Plotly ESG charts, and the Resident Mobile Widget preview.
  - Run full `pytest` and `ruff` verification suites.
