<script setup lang="ts">
import { computed } from 'vue'
import { useAquaStore } from '../store'

const store = useAquaStore()

const trackStates = computed(() => {
  if (store.mode === 'scenario') {
    return store.scenarioData?.system1_trace?.track_states || []
  }
  return store.currentFrame?.system1_trace?.track_states || []
})

const activeDistressTracks = computed(() => {
  return trackStates.value.filter(
    (t: any) => t.is_flailing || t.is_submerged || t.submersion_sec > 0
  )
})

const activeViolationTracks = computed(() => {
  return trackStates.value.filter(
    (t: any) => t.violation_type !== 'NONE' || t.violation_sec > 0
  )
})
</script>

<template>
  <div class="timers-card">
    <h4>⏱️ Stateful Escalation Timers</h4>

    <div v-if="!activeDistressTracks.length && !activeViolationTracks.length" class="empty-timers">
      <span>No active distress or rule violations in progress.</span>
      <small>Timers advance automatically when flailing, submersion or clothing violations occur.</small>
    </div>

    <!-- Distress / Submersion Timers -->
    <div v-for="t in activeDistressTracks" :key="`distress-${t.track_id}`" class="timer-row distress-timer">
      <div class="timer-top">
        <strong>Track #{{ t.track_id }} ({{ t.role }})</strong>
        <span class="timer-badge" :class="t.agent_state.toLowerCase()">
          {{ t.agent_state }} · {{ t.submersion_sec.toFixed(1) }}s
        </span>
      </div>

      <div class="progress-track">
        <div
          class="progress-fill"
          :style="{
            width: `${Math.min(100, (t.submersion_sec / 20.0) * 100)}%`,
            backgroundColor: t.submersion_sec >= 20.0 ? '#FF1744' : t.submersion_sec >= 10.0 ? '#FFEA00' : '#00E5FF'
          }"
        ></div>
        <!-- 10s VERIFY marker -->
        <span class="marker marker-verify" style="left: 50%;">10s</span>
        <!-- 20s CRITICAL marker -->
        <span class="marker marker-critical" style="left: 100%;">20s</span>
      </div>

      <div class="timer-sub">
        <small v-if="t.is_supervised" class="text-green">
          Adult within {{ t.nearest_adult_m?.toFixed(1) }}m assisting (Siren Held in VERIFY)
        </small>
        <small v-else-if="t.submersion_sec >= 20.0" class="text-red">
          Confirmed distress: Directional siren active!
        </small>
        <small v-else>
          Submersion / flailing in {{ t.zone }}
        </small>
      </div>
    </div>

    <!-- Rule Violation Timers -->
    <div v-for="t in activeViolationTracks" :key="`violation-${t.track_id}`" class="timer-row violation-timer">
      <div class="timer-top">
        <strong>Track #{{ t.track_id }} · {{ t.violation_type }}</strong>
        <span class="timer-badge nudge">
          {{ t.violation_sec.toFixed(1) }}s · {{ t.nudge_count }} nudges
        </span>
      </div>

      <div class="progress-track">
        <div
          class="progress-fill"
          :style="{
            width: `${Math.min(100, (t.violation_sec / 30.0) * 100)}%`,
            backgroundColor: t.nudge_count >= 2 ? '#B388FF' : '#448AFF'
          }"
        ></div>
        <span class="marker" style="left: 50%;">15s Nudge</span>
        <span class="marker" style="left: 100%;">30s Ticket</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.timers-card {
  background: rgba(15, 26, 36, 0.85);
  border: 1px solid rgba(51, 78, 104, 0.4);
  border-radius: 10px;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  backdrop-filter: blur(8px);
}

.timers-card h4 {
  margin: 0;
  font-size: 0.95rem;
  color: #FFFFFF;
}

.empty-timers {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 1rem;
  background: rgba(11, 22, 34, 0.5);
  border: 1px dashed rgba(51, 78, 104, 0.4);
  border-radius: 6px;
  font-size: 0.8rem;
  color: #829AB1;
}

.empty-timers small {
  font-size: 0.7rem;
  color: #627D98;
}

.timer-row {
  background: rgba(11, 22, 34, 0.7);
  border: 1px solid rgba(51, 78, 104, 0.4);
  border-radius: 8px;
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.distress-timer {
  border-left: 3px solid #FF1744;
}

.violation-timer {
  border-left: 3px solid #FF9100;
}

.timer-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.82rem;
  color: #FFFFFF;
}

.timer-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  font-weight: 700;
}

.timer-badge.critical_emergency {
  background: rgba(255, 23, 68, 0.2);
  color: #FF1744;
}

.timer-badge.verify {
  background: rgba(255, 234, 0, 0.2);
  color: #FFEA00;
}

.timer-badge.normal {
  background: rgba(0, 255, 102, 0.2);
  color: #00FF66;
}

.timer-badge.nudge {
  background: rgba(255, 145, 0, 0.2);
  color: #FF9100;
}

.progress-track {
  position: relative;
  width: 100%;
  height: 8px;
  background: rgba(30, 41, 59, 0.8);
  border-radius: 4px;
  overflow: visible;
  margin: 0.35rem 0;
}

.progress-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}

.marker {
  position: absolute;
  top: -14px;
  transform: translateX(-50%);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.62rem;
  color: #829AB1;
}

.marker-verify { color: #FFEA00; }
.marker-critical { color: #FF1744; }

.timer-sub {
  font-size: 0.75rem;
  color: #9FB3C8;
}

.text-green { color: #00FF66; }
.text-red { color: #FF1744; font-weight: 600; }
</style>
