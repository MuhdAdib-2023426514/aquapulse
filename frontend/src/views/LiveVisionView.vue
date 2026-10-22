<script setup lang="ts">
import { computed, ref } from 'vue'
import { useAquaStore } from '../store'
import { useAlertAudio } from '../composables/useAlertAudio'

import AgentStateBanner from '../components/AgentStateBanner.vue'
import PrivacyViewer from '../components/PrivacyViewer.vue'
import EventTimeline from '../components/EventTimeline.vue'
import PoolMap from '../components/PoolMap.vue'
import ReflexTimers from '../components/ReflexTimers.vue'
import System2Inspector from '../components/System2Inspector.vue'
import TrackTable from '../components/TrackTable.vue'
import ReasoningLog from '../components/ReasoningLog.vue'
import GuardPhoneCard from '../components/GuardPhoneCard.vue'
import VideoLibrary from '../components/VideoLibrary.vue'
import CalibrationEditor from '../components/CalibrationEditor.vue'
import ScenarioFallback from '../components/ScenarioFallback.vue'

const store = useAquaStore()

const eventsRef = computed(() => store.events)
const playheadRef = computed(() => store.playheadSec)
const isMutedRef = computed(() => store.isMuted)

// Wire up autonomous audio alerts & TTS voice synthesis
const { isAudioUnlocked, unlockAudio } = useAlertAudio(
  eventsRef,
  playheadRef,
  isMutedRef
)

const calibratingJobId = ref<string | null>(null)

function onOpenCalibration(jobId: string) {
  calibratingJobId.value = jobId
}

function onCloseCalibration() {
  calibratingJobId.value = null
}
</script>

<template>
  <div class="live-vision-view">
    <!-- Top Audio Unlock Banner if needed by browser autoplay policy -->
    <div v-if="!isAudioUnlocked" class="audio-unlock-banner">
      <span>🔊 Enable directional emergency audio alerts and voice broadcasts for this session:</span>
      <button class="unlock-btn" @click="unlockAudio">Enable Poolside Audio</button>
    </div>

    <!-- Agent State & System 1 Latency Banner -->
    <AgentStateBanner />

    <!-- Video Mode vs Scripted Scenario Mode Switcher -->
    <div class="mode-switch-strip">
      <div class="strip-left">
        <button
          class="mode-btn"
          :class="{ active: store.mode === 'video' }"
          @click="store.mode = 'video'"
        >
          📹 Real Video Ingestion Mode
        </button>
        <button
          class="mode-btn"
          :class="{ active: store.mode === 'scenario' }"
          @click="store.mode = 'scenario'; if (!store.scenarioData) store.stepScenario('NORMAL_LAP_AND_FAMILY', 0)"
        >
          🧪 Scripted Scenario Engine (Zero-Config)
        </button>
      </div>

      <div class="strip-right">
        <span class="active-source-badge">
          Source: {{ store.mode === 'video' ? (store.activeJob?.filename || 'No Clip Selected') : store.scenarioName }}
        </span>
      </div>
    </div>

    <!-- Scripted Scenario Fallback Panel (if active) -->
    <ScenarioFallback v-if="store.mode === 'scenario'" />

    <!-- Main Live Command Grid -->
    <div class="command-grid">
      <!-- Left Column: Video/Silhouette Stage & Event Scrubber -->
      <div class="grid-left">
        <PrivacyViewer />
        <EventTimeline v-if="store.mode === 'video'" />
        <PoolMap />
        <TrackTable />
      </div>

      <!-- Right Column: Reflex Timers, System 2 ROI Zoom & Guard Smartphone Alert -->
      <div class="grid-right">
        <ReflexTimers />
        <System2Inspector />
        <GuardPhoneCard />
        <ReasoningLog />
        <VideoLibrary @calibrate="onOpenCalibration" />
      </div>
    </div>

    <!-- Calibration Modal Popup -->
    <CalibrationEditor
      v-if="calibratingJobId"
      :job-id="calibratingJobId"
      @close="onCloseCalibration"
      @processed="onCloseCalibration"
    />
  </div>
</template>

<style scoped>
.live-vision-view {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.audio-unlock-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(255, 145, 0, 0.15);
  border: 1px solid rgba(255, 145, 0, 0.4);
  color: #FFEA00;
  padding: 0.65rem 1.25rem;
  border-radius: 8px;
  font-size: 0.85rem;
}

.unlock-btn {
  background: #FF9100;
  color: #081018;
  border: none;
  font-weight: 700;
  padding: 0.4rem 0.9rem;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.unlock-btn:hover {
  background: #FFEA00;
}

.mode-switch-strip {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(15, 26, 36, 0.8);
  border: 1px solid rgba(51, 78, 104, 0.4);
  border-radius: 10px;
  padding: 0.6rem 1rem;
}

.strip-left {
  display: flex;
  gap: 0.6rem;
}

.mode-btn {
  background: transparent;
  border: 1px solid rgba(51, 78, 104, 0.5);
  color: #9FB3C8;
  padding: 0.45rem 0.9rem;
  border-radius: 6px;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.mode-btn:hover {
  color: #E0F2FE;
  border-color: rgba(0, 229, 255, 0.4);
}

.mode-btn.active {
  background: rgba(0, 229, 255, 0.15);
  color: #00E5FF;
  border-color: #00E5FF;
  box-shadow: 0 0 10px rgba(0, 229, 255, 0.2);
}

.active-source-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: #829AB1;
}

.command-grid {
  display: grid;
  grid-template-columns: 1.25fr 1fr;
  gap: 1.25rem;
  align-items: start;
}

.grid-left,
.grid-right {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

@media (max-width: 1200px) {
  .command-grid {
    grid-template-columns: 1fr;
  }
}
</style>
