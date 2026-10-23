<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useAquaStore } from '../store'
import type { ScenarioName } from '../types/aquapulse'

const store = useAquaStore()

const scenarios: { id: ScenarioName; label: string }[] = [
  { id: 'SILENT_DROWNING_RESCUE', label: '1. 🚨 Silent Drowning Rescue (0s -> 5s -> 8s)' },
  { id: 'UNACCOMPANIED_TODDLER_DEEP_END', label: '2. 👶 Toddler Near Deep End (1.5m Boundary)' },
  { id: 'COTTON_TSHIRT_AND_FOOD_NUDGE', label: '3. 👕 Cotton T-Shirt & Food Nudge' },
  { id: 'PET_AND_STRAY_ANIMAL_POOL', label: '4. 🐕‍🦺 Pet Dog in Pool & 100% VFD Purge' },
  { id: 'MONSOON_DEBRIS_AND_ALGAE', label: '5. 🍂 Monsoon Storm Debris & Algae Drift' },
  { id: 'PEAK_CROWD_SURGE_ECO_DRIVE', label: '6. ⚡ Peak Crowd Surge & VFD Eco-Throttle' },
  { id: 'NORMAL_LAP_AND_FAMILY', label: '7. 🏊 Normal Lap & Supervised Family' },
]

const sliderSec = ref(store.scenarioElapsedSec || 0)

watch(
  () => store.scenarioElapsedSec,
  (val) => {
    sliderSec.value = val
  }
)

interface Milestone {
  sec: number
  label: string
  hint: string
}

const scenarioMilestones = computed<Milestone[]>(() => {
  switch (store.scenarioName) {
    case 'SILENT_DROWNING_RESCUE':
      return [
        { sec: 0, label: '0s: Flailing', hint: 'Surface struggle in Zone B Deep End' },
        { sec: 5, label: '5s: Verify', hint: 'Motionless underwater + Yellow beacon' },
        { sec: 8, label: '8s: Critical Alarm', hint: 'Directional siren + TTS + Guard alert' },
      ]
    case 'UNACCOMPANIED_TODDLER_DEEP_END':
      return [
        { sec: 0, label: '0s: Near Boundary', hint: 'Within 1.5m of deep-end line' },
        { sec: 5, label: '5s: Verify Strobe', hint: 'Unaccompanied caution beacon' },
        { sec: 8, label: '8s: Emergency Dispatch', hint: 'Immediate security intervention' },
      ]
    case 'COTTON_TSHIRT_AND_FOOD_NUDGE':
      return [
        { sec: 0, label: '0s: Detected', hint: 'Streetwear / poolside drink' },
        { sec: 5, label: '5s: Voice Nudge', hint: 'Polite directional speaker nudge' },
        { sec: 8, label: '8s: Guard Ticket', hint: 'Escalation after ignored nudge' },
      ]
    case 'PET_AND_STRAY_ANIMAL_POOL':
      return [
        { sec: 0, label: '0s: Perimeter', hint: 'Stray animal detected poolside' },
        { sec: 10, label: '10s: Water Contamination', hint: 'Bio-hazard alert & 100% VFD Purge' },
        { sec: 25, label: '25s: Sanitation Cycle', hint: 'High turnover purge cycle active' },
      ]
    case 'MONSOON_DEBRIS_AND_ALGAE':
      return [
        { sec: 0, label: '0s: Baseline', hint: 'Calm water surface check' },
        { sec: 12, label: '12s: Inspection', hint: 'Algae green-shift & debris contours' },
        { sec: 25, label: '25s: Cleaner Ticket', hint: 'Automated work-order dispatched' },
      ]
    case 'PEAK_CROWD_SURGE_ECO_DRIVE':
      return [
        { sec: 0, label: '0s: Baseline', hint: 'Low bather load (40% Eco-mode)' },
        { sec: 12, label: '12s: Crowd Surge', hint: '14 swimmers bather-load spike' },
        { sec: 25, label: '25s: Eco-Throttle', hint: 'Dynamic pump affinity optimization' },
      ]
    default:
      return [
        { sec: 0, label: '0s: Start', hint: 'Baseline monitoring' },
        { sec: 10, label: '10s: Midpoint', hint: 'Continuous tracking' },
        { sec: 20, label: '20s: Target', hint: 'Compliance verification' },
      ]
  }
})

const stateClass = computed(() => {
  const st = store.overallState
  if (st === 'CRITICAL_EMERGENCY') return 'badge-critical'
  if (st === 'VERIFY') return 'badge-verify'
  if (st === 'NUDGE_REQUIRED' || st === 'ESCALATED_GUARD_TICKET') return 'badge-nudge'
  return 'badge-normal'
})

const overallStateText = computed(() => {
  return String(store.overallState || 'NORMAL').replace(/_/g, ' ')
})

async function pickScenario(name: ScenarioName) {
  sliderSec.value = 0
  await store.stepScenario(name, 0)
}

async function onSliderChange(e: Event) {
  const val = parseFloat((e.target as HTMLInputElement).value)
  sliderSec.value = val
  await store.stepScenario(store.scenarioName, val)
}

async function jumpToMilestone(sec: number) {
  sliderSec.value = sec
  await store.stepScenario(store.scenarioName, sec)
}
</script>

<template>
  <div class="scenario-fallback-card">
    <div class="fallback-header">
      <div class="header-titles">
        <h4>🧪 Scripted Scenario Engine (Zero-Config Mode)</h4>
        <p class="subtle">Test all 7 hackathon pitch scenarios deterministically without needing video upload.</p>
      </div>
      <div class="header-badge">
        <span class="engine-badge">Deterministic Simulator Active</span>
      </div>
    </div>

    <!-- 7 Scenario Buttons (Crisp & High Contrast) -->
    <div class="scenario-buttons-grid">
      <button
        v-for="s in scenarios"
        :key="s.id"
        class="scen-btn"
        :class="{ active: store.scenarioName === s.id }"
        @click="pickScenario(s.id)"
      >
        <span class="btn-text">{{ s.label }}</span>
      </button>
    </div>

    <!-- Time Slider Scrubber & Pitch Milestone Jumps -->
    <div class="scenario-time-bar">
      <div class="time-bar-top">
        <div class="time-readout">
          <span class="readout-label">Timeline:</span>
          <strong class="readout-sec">{{ sliderSec.toFixed(1) }}s</strong>
          <span class="state-pill" :class="stateClass">
            <span class="pulse-indicator"></span>
            {{ overallStateText }}
          </span>
        </div>

        <!-- Quick 1-Click Milestone Jumps -->
        <div class="milestones-wrap">
          <span class="milestones-caption">Pitch Milestones:</span>
          <div class="milestone-btns">
            <button
              v-for="m in scenarioMilestones"
              :key="m.sec"
              class="milestone-btn"
              :class="{ active: Math.abs(sliderSec - m.sec) < 1.0 }"
              :title="m.hint"
              @click="jumpToMilestone(m.sec)"
            >
              {{ m.label }}
            </button>
          </div>
        </div>
      </div>

      <div class="slider-container">
        <input
          type="range"
          class="scenario-slider"
          min="0"
          max="30"
          step="1"
          :value="sliderSec"
          @input="onSliderChange"
        />
        <div class="slider-ticks">
          <span class="tick" :class="{ 'tick-highlight': Math.abs(sliderSec - 0) < 0.6 }">0s</span>
          <span class="tick keypoint-tick" :class="{ 'tick-highlight': Math.abs(sliderSec - 5) < 0.6 }">5s (Verify)</span>
          <span class="tick keypoint-tick-critical" :class="{ 'tick-highlight': Math.abs(sliderSec - 8) < 0.6 }">8s (Critical)</span>
          <span class="tick" :class="{ 'tick-highlight': Math.abs(sliderSec - 15) < 0.6 }">15s</span>
          <span class="tick" :class="{ 'tick-highlight': Math.abs(sliderSec - 20) < 0.6 }">20s</span>
          <span class="tick" :class="{ 'tick-highlight': Math.abs(sliderSec - 25) < 0.6 }">25s</span>
          <span class="tick" :class="{ 'tick-highlight': Math.abs(sliderSec - 30) < 0.6 }">30s</span>
        </div>
      </div>
    </div>

    <!-- Rendered Frames from API -->
    <div v-if="store.scenarioData?.rendered_frames" class="scenario-frame-preview">
      <div class="frame-col">
        <div class="col-header">
          <span class="col-badge badge-tier2">🛡️ Tier-2 PDPA Skeletal Silhouette (0% Biometrics)</span>
          <span class="col-sub">Neon keypoints on dark blueprint zone grid for cloud & guardhouse</span>
        </div>
        <div class="frame-wrapper">
          <img
            :src="store.scenarioData.rendered_frames.silhouette_bgr"
            alt="Tier-2 Silhouette"
            class="frame-img"
          />
        </div>
      </div>

      <div class="frame-col">
        <div class="col-header">
          <span class="col-badge badge-tier1">🔍 Tier-1 Synthetic Pool Perception</span>
          <span class="col-sub">Face-masked Torso/Limb Perception for System 2 inspection</span>
        </div>
        <div class="frame-wrapper">
          <img
            :src="store.scenarioData.rendered_frames.raw_bgr"
            alt="Tier-1 Face Masked"
            class="frame-img"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scenario-fallback-card {
  background: rgba(13, 23, 33, 0.95);
  border: 1px solid rgba(0, 229, 255, 0.35);
  border-radius: 12px;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
  backdrop-filter: blur(10px);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

.fallback-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(51, 78, 104, 0.35);
  padding-bottom: 0.75rem;
}

.fallback-header h4 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 700;
  color: #FFFFFF;
  letter-spacing: -0.01em;
}

.subtle {
  font-size: 0.8rem;
  color: #8CA0AA;
  margin: 0.25rem 0 0 0;
}

.engine-badge {
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  background: rgba(0, 229, 255, 0.12);
  border: 1px solid rgba(0, 229, 255, 0.3);
  color: #38BDF8;
}

/* 7 Scenario Buttons Grid */
.scenario-buttons-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(270px, 1fr));
  gap: 0.55rem;
}

.scen-btn {
  background: rgba(18, 33, 49, 0.85);
  border: 1px solid rgba(0, 229, 255, 0.22);
  color: #E6F1F6;
  font-size: 0.82rem;
  font-weight: 600;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
}

.scen-btn:hover {
  background: rgba(0, 229, 255, 0.16);
  color: #FFFFFF;
  border-color: rgba(0, 229, 255, 0.6);
  transform: translateY(-1px);
}

.scen-btn.active {
  background: rgba(0, 229, 255, 0.26);
  color: #FFFFFF;
  border-color: #00F0FF;
  box-shadow: 0 0 14px rgba(0, 229, 255, 0.35);
  font-weight: 700;
}

/* Time Scrubber & Quick Milestones Bar */
.scenario-time-bar {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  background: rgba(11, 20, 29, 0.9);
  border: 1px solid rgba(0, 229, 255, 0.25);
  padding: 0.85rem 1.1rem;
  border-radius: 8px;
}

.time-bar-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.time-readout {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  font-size: 0.85rem;
  color: #94A3B8;
}

.readout-label {
  font-weight: 500;
}

.readout-sec {
  color: #FFFFFF;
  font-family: 'JetBrains Mono', monospace;
  font-size: 1.05rem;
  font-weight: 700;
  min-width: 50px;
}

/* State Badge */
.state-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.pulse-indicator {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.badge-normal {
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.4);
  color: #10B981;
}

.badge-verify {
  background: rgba(245, 158, 11, 0.18);
  border: 1px solid rgba(245, 158, 11, 0.5);
  color: #F59E0B;
  box-shadow: 0 0 10px rgba(245, 158, 11, 0.3);
}

.badge-critical {
  background: rgba(239, 68, 68, 0.25);
  border: 1px solid rgba(239, 68, 68, 0.7);
  color: #EF4444;
  box-shadow: 0 0 14px rgba(239, 68, 68, 0.45);
  animation: critical-pulse 1.2s infinite ease-in-out;
}

.badge-nudge {
  background: rgba(56, 189, 248, 0.18);
  border: 1px solid rgba(56, 189, 248, 0.5);
  color: #38BDF8;
}

@keyframes critical-pulse {
  0%, 100% {
    box-shadow: 0 0 10px rgba(239, 68, 68, 0.4);
  }
  50% {
    box-shadow: 0 0 20px rgba(239, 68, 68, 0.8);
  }
}

/* Quick Pitch Milestone Jumps */
.milestones-wrap {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.milestones-caption {
  font-size: 0.75rem;
  font-weight: 600;
  color: #64748B;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.milestone-btns {
  display: flex;
  gap: 0.35rem;
}

.milestone-btn {
  background: rgba(20, 36, 52, 0.9);
  border: 1px solid rgba(51, 78, 104, 0.6);
  color: #E2E8F0;
  font-size: 0.76rem;
  font-weight: 600;
  padding: 0.3rem 0.65rem;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.milestone-btn:hover {
  background: rgba(0, 229, 255, 0.2);
  color: #FFFFFF;
  border-color: rgba(0, 229, 255, 0.6);
}

.milestone-btn.active {
  background: #0284C7;
  color: #FFFFFF;
  border-color: #38BDF8;
  box-shadow: 0 0 10px rgba(56, 189, 248, 0.4);
}

/* Slider Track & Ticks */
.slider-container {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.scenario-slider {
  width: 100%;
  accent-color: #00E5FF;
  cursor: pointer;
  height: 6px;
  border-radius: 3px;
}

.slider-ticks {
  display: flex;
  justify-content: space-between;
  font-size: 0.7rem;
  color: #64748B;
  font-family: 'JetBrains Mono', monospace;
  padding: 0 2px;
}

.tick-highlight {
  color: #00E5FF;
  font-weight: 700;
}

.keypoint-tick {
  color: #F59E0B;
}

.keypoint-tick-critical {
  color: #EF4444;
}

/* Rendered Frames Preview */
.scenario-frame-preview {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.1rem;
}

@media (max-width: 900px) {
  .scenario-frame-preview {
    grid-template-columns: 1fr;
  }
}

.frame-col {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.col-header {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.col-badge {
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.badge-tier2 {
  color: #38BDF8;
}

.badge-tier1 {
  color: #94A3B8;
}

.col-sub {
  font-size: 0.7rem;
  color: #64748B;
}

.frame-wrapper {
  background: #0B141D;
  border: 1px solid rgba(0, 229, 255, 0.3);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
}

.frame-img {
  width: 100%;
  display: block;
}
</style>
