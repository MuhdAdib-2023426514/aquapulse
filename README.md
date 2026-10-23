---
title: AquaPulse — AI Pool Monitoring & ESG System
emoji: 🏊
colorFrom: blue
colorTo: cyan
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# 🌊 AquaPulse — Privacy-First Agentic Vision Monitoring & ESG Optimization System for Residential Swimming Pools

> **Competition**: **Sime Darby Property University Hackathon (*"Township of Tomorrow"*)**  
> **Tracks Targeted**: **People** (Life Safety, Community Harmony, Inclusivity) & **Planet** (Energy & Water Conservation, Low-Carbon Operations)

---

## 1. Executive Summary

Malaysian high-rise strata condominiums and township clubhouses face three structural challenges at residential swimming pools:
1. **The "Lifeguardless" 3–5 Minute Guardhouse Gap**: Most strata condo pools have no full-time lifeguards on deck, while guardhouse auxiliary police take 3–5 minutes to reach the pool deck during a silent drowning or toddler emergency.
2. **24/7 Fixed-Speed Filtration Pump Energy Waste**: Traditional `5.5 kW` commercial pool pumps run at 100% speed even during 0-swimmer overnight and midday UV lulls—wasting tens of thousands of Ringgit in TNB commercial strata electricity tariffs (`RM 0.51/kWh`) and grid carbon emissions (`0.758 kg CO2/kWh`).
3. **PDPA Privacy & Strata Rule Friction**: Residents strongly oppose raw CCTV facial surveillance at pools, and security guards dislike confronting residents over cotton streetwear in the water or poolside food/drinks.

**AquaPulse** solves all three challenges through a **Dual-Path Agentic Vision & VFD Eco-Drive Architecture** with **Two-Tier Malaysia PDPA 2010 & PDPA (Amendment) Act 2024 Compliance**:
- **⚡ Path 1 — System 1 Fast Edge Reflex (`<30ms` Synchronous Local Loop)**: Tracks persistent `track_id`s and 17 COCO skeletal keypoints to detect **Active Surface Distress / Flailing (`ACTIVE_FLAILING`)** transitioning continuously into **Silent Submersion (`HORIZONTAL_SUBMERGED`)**, plus **Unaccompanied Toddlers within `1.5m` of the Deep-End Boundary**. Mobilizes poolside bystanders within 5 seconds via a directional siren + bilingual English/Bahasa Malaysia TTS broadcast (`t = 20.0s`) while dispatching the fastest entry route map to the Guardhouse smartphone.
- **🔍 Path 2 — System 2 Deliberative Agentic Vision (`1–3s` Non-Blocking 3-Step Visual Tool Chain & Water QA)**: Executes a verifiable **3-Step Agentic Vision Pipeline** (`crop_and_zoom_roi` $\to$ `probe_sub_rois_and_context` $\to$ `verify_attire_or_item`):
  1. **Step 1 (`crop_and_zoom_roi`)**: Applies **Tier-1 Face Redaction (`kp[0..4]` blacked out)** and crops a `2x` zoomed ROI around the swimmer.
  2. **Step 2 (`probe_sub_rois_and_context`)**: Extracts the torso polygon (`kp[5,6,11,12]`) to compute HSV saturation/value and Laplacian texture (opaque cotton streetwear vs. dark Lycra swimwear), measures wrist (`kp[9,10]`) proximity to `bottle`/`cup`/`bowl`/`wine glass`/`food_container` or stray/pet animals (`dog`/`cat`/`bird`), and probes wrist/upper-torso aerosol plumes.
  3. **Step 3 (`verify_attire_or_item`)**: Queries `gemini-3.8-flash` (when `GEMINI_API_KEY` is configured, within a strict `2.0s` timeout) with deterministic offline OpenCV sub-ROI fallback, playing a polite directional speaker reminder after `15.0s` and only opening a Guardhouse ticket if `2` consecutive nudges (`30.0s`) are ignored.
- **🌱 Planet Track Bather-Load VFD Pump Eco-Drive**: Computes a real-time **Biological & Contamination Load Score** factoring in bather load, cotton streetwear ($w_1$), poolside food/drink ($w_2$), and pet/stray animal bio-hazards ($w_3$). Throttles Variable Frequency Drive (VFD) filtration pumps down to `40%` eco-mode (`0.352 kW` vs `5.5 kW` fixed via the cubic **Pump Affinity Law** $P_2 / P_1 = (N_2 / N_1)^3$) during verified zero-occupancy windows while strictly enforcing a **Minimum Daily Turnover Floor (`>= 3.5 turnovers/day`)**—achieving **~32–35% energy, RM, and $\text{CO}_2$ savings**.
- **📐 One-Time Camera Perspective Calibration & Persistent Profiles**: Supports registering swimming pools and cameras once. An administrator interactively aligns the 4 pool corners, confirms physical dimensions/depths, selects deep-end orientation, and sets the shallow/deep boundary (aligning with the floating yellow safety rope). Validated calibrations persist in SQLite with immutable versions ($v1, v2, \dots$) and are **automatically reused for all future video uploads from the same camera**, eliminating redundant calibration effort while guaranteeing accurate zone assignment and toddler deep-end proximity tracking.

---

## 2. One-Time Pool & Camera Calibration Workflow

```
[Register Pool & Camera] ──> [Interactive 4-Corner Polygon] ──> [Enter Dimensions & Depths]
                                                                        │
[Auto-Reuse on Video Upload] <── [Activate Profile (v1)] <── [Validate Geometry & Safety Boundary]
```

### Calibration Workflow Steps
1. **Pool & Camera Registration (`/api/v1/pools`, `/api/v1/cameras`)**:
   - Register the physical pool basin (e.g. *AquaPulse Demo Pool*, 25m × 12m) and attach one or more CCTV camera mountings (e.g. *Main Pool CCTV*).
   - Pre-seeded out of the box with the **AquaPulse Demo Pool Profile** (`demo_pool_1`, `demo_camera_cctv_1`, `demo_calibration_v1`).
2. **Interactive 4-Corner Basin Alignment**:
   - Drag or click the 4 corner handles `[TL, TR, BR, BL]` in clockwise order on the Tier-1 preview frame.
   - Includes reset, undo history stack, and fine $\pm 0.5\%$ nudge controls.
3. **Verified Physical Dimensions & Depths**:
   - Explicitly confirm length ($25.0\text{m}$), width ($12.0\text{m}$), shallow depth ($0.8\text{m}$), and deep depth ($1.8\text{m}$).
   - The system strictly uses administrator-confirmed facility geometry rather than unreliable visual color heuristics.
4. **Deep-End Orientation & Safety Boundary**:
   - Supports 4 camera viewpoints: `right` (default), `left`, `bottom`, `top`.
   - Longitudinal boundary position (e.g. $12.5\text{m}$) renders a live projected yellow dashed boundary line matching the physical yellow floating safety rope.
5. **Geometry Validation & Interactive Point Inspector**:
   - Validates non-degeneracy, Shoelace area $>0.005$, strict convexity/clockwise order (detects self-intersecting hourglass/bowtie polygons), and homography invertibility.
   - Click anywhere on the pool canvas to test-inspect physical coordinates $(x_m, y_m)$, in-water containment, and zone classification (`ZONE_A_SHALLOW`, `ZONE_B_DEEP_END`, `POOL_DECK`).
6. **Automatic Video Reuse**:
   - Uploading video clips associated with a camera automatically binds its active calibration profile without re-clicking corners.
   - Revising geometry creates a new version ($v2, v3$) in draft status, protecting historical incident analyses from retroactive mutation.

---

## 2. Quickstart Commands (WSL Ubuntu + `uv`)

### Install / Sync Dependencies
```powershell
wsl bash -lc 'cd /home/muhammad_adib/swimming_pool_monitoring_system && /home/muhammad_adib/.local/bin/uv sync'
```

### Run Full Verification Suite (`ruff` + `pytest` + Syntax Gate)
```powershell
wsl bash -lc 'cd /home/muhammad_adib/swimming_pool_monitoring_system && bash .agents/skills/aquapulse-verify/scripts/verify_milestone.sh'
```

### Launch 4-Tab Streamlit Pitch Dashboard (Port 8501)
```powershell
wsl bash -lc 'cd /home/muhammad_adib/swimming_pool_monitoring_system && /home/muhammad_adib/.local/bin/uv run streamlit run app/streamlit_app.py --server.port 8501'
```
*(Optional: export `GEMINI_API_KEY="your-key"` inside WSL to enable live `gemini-3.8-flash` multimodal VLM verification in System 2 Step 3; otherwise it runs 100% offline via deterministic OpenCV sub-ROI heuristics.)*

### Launch FastAPI Backend Server (Port 8000)
```powershell
wsl bash -lc 'cd /home/muhammad_adib/swimming_pool_monitoring_system && /home/muhammad_adib/.local/bin/uv run uvicorn aquapulse.api.main:app --host 0.0.0.0 --port 8000 --reload'
```

---

## 3. 3-Minute Live Hackathon Pitch Script

1. **Minute 0:00–1:00 — Tab 1: System 1 (`<30ms`) Active Flailing $\to$ Silent Drowning Rescue & Two-Tier PDPA Shield**
   - Show the **Tier-2 Skeletal Silhouette Canvas** (`0%` raw biometric pixels stored or displayed).
   - Select **Scenario #1 (`Silent Drowning Rescue`)**: at `0s–4s`, point out Swimmer `#201` in `ACTIVE_FLAILING` (surface panic oscillation). Click **`🟡 5s (VERIFY)`** to show the seamless transition into underwater submersion (`VERIFY` state + yellow poolside strobe). Click **`🚨 8s (CRITICAL)`** to fire the offline WAV siren, bilingual English/BM TTS broadcast, and Guardhouse Smartphone Route Card—all in `<1ms` (`<30ms` budget).
2. **Minute 1:00–1:45 — Tab 1: System 2 (`>=5s`) 3-Step Agentic Vision Tool Chain & Polite Audio Nudge**
   - Select **Scenario #3 (`Cotton T-Shirt & Food Nudge`)** and click **`🔊 5s (Sys2 Nudge #1)`**.
   - Show the **Tier-1 Face-Masked 2× ROI Zoom** and the **`🛠️ Track #ID Agentic Tool Trace (3 Steps)`** checklist on the right panel: Step 1 blacks out head keypoints `kp[0..4] = [0,0,0]` and crops `2x`, Step 2 probes torso polygon (`kp[5,6,11,12]`) HSV/Laplacian fabric texture and wrist (`kp[9,10]`) proximity to food/drinks, and Step 3 issues the VLM/OpenCV consensus verdict. Click **`👮 8s (Guard Ticket)`** to demonstrate 2-strike escalation.
3. **Minute 1:45–2:30 — Tab 2: Planet Track VFD Pump Eco-Drive & Township Scale Multiplier**
   - Open **Tab 2** to show the cubic **Pump Affinity Law Curve ($P \propto N^3$)** (`0.352 kW` at `40%` speed vs. `5.5 kW` fixed), the **Minimum Daily Turnover Compliance Badge (`>= 3.5 turnovers/day`)**, and slide the **Sime Darby Township Scale Multiplier** to `10–25` strata developments.
4. **Minute 2:30–3:00 — Tab 3 & Tab 4: Monsoon Debris Inspector & Resident Township App Widget**
   - Open **Tab 3** to show OpenCV detecting post-monsoon floating leaves/twigs and early green-algae drift before a costly pool drain is needed.
   - Finish on **Tab 4** with the **Elmina Township Resident App Mobile Card**, switching days of the week (`Monday..Sunday`) to show `scikit-learn` Quiet Swim Windows and inclusive Senior/Toddler safe hours.
