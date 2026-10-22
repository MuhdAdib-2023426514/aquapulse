<script setup lang="ts">
import { ref } from 'vue'
import { useAquaStore } from '../store'
import type { ScenarioName } from '../types/aquapulse'

const store = useAquaStore()

const scenarios: { id: ScenarioName; label: string }[] = [
  { id: 'SILENT_DROWNING_RESCUE', label: '1. 🚨 Silent Drowning Rescue (0s -> 10s -> 20s)' },
  { id: 'UNACCOMPANIED_TODDLER_DEEP_END', label: '2. 👶 Toddler Near Deep End (1.5m Boundary)' },
  { id: 'COTTON_TSHIRT_AND_FOOD_NUDGE', label: '3. 👕 Cotton T-Shirt & Food Nudge' },
  { id: 'PET_AND_STRAY_ANIMAL_POOL', label: '4. 🐕‍🦺 Pet Dog in Pool & 100% VFD Purge' },
  { id: 'MONSOON_DEBRIS_AND_ALGAE', label: '5. 🍂 Monsoon Storm Debris & Algae Drift' },
  { id: 'PEAK_CROWD_SURGE_ECO_DRIVE', label: '6. ⚡ Peak Crowd Surge & VFD Eco-Throttle' },
  { id: 'NORMAL_LAP_AND_FAMILY', label: '7. 🏊 Normal Lap & Supervised Family' },
]

const sliderSec = ref(0)

async function pickScenario(name: ScenarioName) {
  sliderSec.value = 0
  await store.stepScenario(name, 0)
}

async function onSliderChange(e: Event) {
  const val = parseFloat((e.target as HTMLInputElement).value)
  sliderSec.value = val
  await store.stepScenario(store.scenarioName, val)
}
</script>

<template>
  <div class="scenario-fallback-card">
    <div class="fallback-header">
      <h4>🧪 Scripted Scenario Engine (Zero-Config Mode)</h4>
      <p class="subtle">Test all 7 hackathon pitch scenarios deterministically without needing video upload.</p>
    </div>

    <!-- 7 Scenario Buttons -->
    <div class="scenario-buttons-grid">
      <button
        v-for="s in scenarios"
        :key="s.id"
        class="scen-btn"
        :class="{ active: store.scenarioName === s.id }"
        @click="pickScenario(s.id)"
      >
        {{ s.label }}
      </button>
    </div>

    <!-- Time Slider Scrubber -->
    <div class="scenario-time-bar">
      <div class="time-readout">
        <span>Timeline Scrubber:</span>
        <strong>{{ sliderSec.toFixed(1) }}s</strong>
      </div>
      <input
        type="range"
        class="scenario-slider"
        min="0"
        max="30"
        step="2.5"
        :value="sliderSec"
        @input="onSliderChange"
      />
    </div>

    <!-- Rendered Frames from API -->
    <div v-if="store.scenarioData?.rendered_frames" class="scenario-frame-preview">
      <div class="frame-col">
        <span class="col-title">Tier-2 PDPA Skeletal Silhouette (0% Biometrics)</span>
        <img
          :src="store.scenarioData.rendered_frames.silhouette_bgr"
          alt="Tier-2 Silhouette"
          class="frame-img"
        />
      </div>
      <div class="frame-col">
        <span class="col-title">Tier-1 Face-Masked Synthetic Pool</span>
        <img
          :src="store.scenarioData.rendered_frames.raw_bgr"
          alt="Tier-1 Face Masked"
          class="frame-img"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.scenario-fallback-card {
  background: rgba(15, 26, 36, 0.9);
  border: 1px solid rgba(0, 229, 255, 0.3);
  border-radius: 10px;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  backdrop-filter: blur(8px);
}

.fallback-header h4 {
  margin: 0;
  font-size: 1.05rem;
  color: #FFFFFF;
}

.subtle {
  font-size: 0.78rem;
  color: #617981;
  margin: 0.2rem 0 0 0;
}

.scenario-buttons-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 0.5rem;
}

.scen-btn {
  background: rgba(11, 22, 34, 0.7);
  border: 1px solid rgba(51, 78, 104, 0.4);
  color: #4B6269;
  font-size: 0.78rem;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s ease;
}

.scen-btn:hover {
  background: rgba(0, 229, 255, 0.1);
  color: #FFFFFF;
  border-color: rgba(0, 229, 255, 0.4);
}

.scen-btn.active {
  background: rgba(0, 229, 255, 0.2);
  color: #176776;
  border-color: #176776;
  box-shadow: 0 0 10px rgba(0, 229, 255, 0.25);
  font-weight: 700;
}

.scenario-time-bar {
  display: flex;
  align-items: center;
  gap: 1rem;
  background: rgba(11, 22, 34, 0.8);
  border: 1px solid rgba(51, 78, 104, 0.4);
  padding: 0.6rem 1rem;
  border-radius: 6px;
}

.time-readout {
  display: flex;
  gap: 0.4rem;
  font-size: 0.8rem;
  color: #617981;
}

.time-readout strong {
  color: #176776;
  font-family: 'JetBrains Mono', monospace;
}

.scenario-slider {
  flex: 1;
  accent-color: #176776;
  cursor: pointer;
}

.scenario-frame-preview {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.frame-col {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.col-title {
  font-size: 0.72rem;
  color: #617981;
  font-weight: 600;
}

.frame-img {
  width: 100%;
  border-radius: 6px;
  border: 1px solid rgba(51, 78, 104, 0.5);
  background: #F5F8F9;
}
</style>
