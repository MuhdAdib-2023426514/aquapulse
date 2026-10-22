<script setup lang="ts">
import { computed } from 'vue'
import { useAquaStore } from '../store'

const store = useAquaStore()

const state = computed(() => store.overallState)
const latencyMs = computed(() => {
  if (store.mode === 'scenario') {
    return store.scenarioData?.system1_trace?.execution_latency_ms || 1.2
  }
  return store.currentFrame?.system1_trace?.execution_latency_ms || 1.15
})

const stateInfo = computed(() => {
  switch (state.value) {
    case 'CRITICAL_EMERGENCY':
      return {
        badge: '🚨 CRITICAL EMERGENCY',
        desc: 'Directional Siren & On-Site TTS Voice Broadcast Active — Swimmer Submerged Without Bystander',
        class: 'emergency-state',
      }
    case 'VERIFY':
      return {
        badge: '⚠️ VERIFY (t >= 10s)',
        desc: 'Yellow Poolside Caution Beacon Triggered — Verifying Adult Bystander Assistance within 1.5m',
        class: 'verify-state',
      }
    case 'NUDGE_REQUIRED':
      return {
        badge: '📢 NUDGE REQUIRED (t >= 15s)',
        desc: 'Polite Directional Speaker Voice Nudge Playing — Continuous Cotton Attire / Poolside Item',
        class: 'nudge-state',
      }
    case 'ESCALATED_GUARD_TICKET':
      return {
        badge: '🎫 ESCALATED GUARD TICKET',
        desc: 'Security Guard Ticket Opened — Resident Ignored 2 Consecutive Poolside Nudges',
        class: 'ticket-state',
      }
    default:
      return {
        badge: '✅ NORMAL MONITORING',
        desc: 'Synchronous System 1 Reflex Loop (<30ms) Active — Tracking 17 Skeletal Keypoints & Zones',
        class: 'normal-state',
      }
  }
})
</script>

<template>
  <div class="agent-banner" :class="stateInfo.class">
    <div class="banner-left">
      <span class="state-chip">{{ stateInfo.badge }}</span>
      <p class="state-desc">{{ stateInfo.desc }}</p>
    </div>

    <div class="banner-right">
      <div class="kpi-mini">
        <span class="kpi-label">SYS 1 REFLEX</span>
        <strong class="kpi-val">{{ latencyMs.toFixed(2) }} ms</strong>
        <small class="kpi-sub">&lt; 30ms budget</small>
      </div>

      <div class="kpi-mini">
        <span class="kpi-label">PLAYHEAD CLOCK</span>
        <strong class="kpi-val">{{ store.playheadSec.toFixed(1) }} s</strong>
        <small class="kpi-sub">{{ (store.activeJob?.duration_sec || 0).toFixed(1) }}s total</small>
      </div>
    </div>
  </div>
</template>

<style scoped>
.agent-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(15, 26, 36, 0.9);
  border: 1px solid rgba(51, 78, 104, 0.4);
  border-radius: 10px;
  padding: 0.85rem 1.25rem;
  transition: all 0.3s ease;
  backdrop-filter: blur(8px);
}

.agent-banner.normal-state {
  border-color: rgba(0, 255, 102, 0.4);
  box-shadow: 0 0 15px rgba(0, 255, 102, 0.08);
}

.agent-banner.verify-state {
  border-color: rgba(255, 234, 0, 0.6);
  background: rgba(25, 30, 20, 0.95);
  box-shadow: 0 0 20px rgba(255, 234, 0, 0.15);
}

.agent-banner.emergency-state {
  border-color: #FF1744;
  background: rgba(35, 15, 20, 0.95);
  box-shadow: 0 0 25px rgba(255, 23, 68, 0.25);
  animation: pulse-border 1.5s infinite alternate;
}

.agent-banner.nudge-state {
  border-color: #FF9100;
  box-shadow: 0 0 18px rgba(255, 145, 0, 0.15);
}

.agent-banner.ticket-state {
  border-color: #FF5252;
}

@keyframes pulse-border {
  from { border-color: #FF1744; }
  to { border-color: #FF8A80; }
}

.banner-left {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.state-chip {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.82rem;
  font-weight: 800;
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
  background: rgba(11, 22, 34, 0.8);
  border: 1px solid currentColor;
  white-space: nowrap;
}

.normal-state .state-chip { color: #00FF66; }
.verify-state .state-chip { color: #FFEA00; }
.emergency-state .state-chip { color: #FF1744; }
.nudge-state .state-chip { color: #FF9100; }
.ticket-state .state-chip { color: #FF5252; }

.state-desc {
  font-size: 0.85rem;
  color: #CBD2D9;
  margin: 0;
  line-height: 1.35;
}

.banner-right {
  display: flex;
  align-items: center;
  gap: 1.25rem;
}

.kpi-mini {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  border-left: 1px solid rgba(51, 78, 104, 0.4);
  padding-left: 1rem;
}

.kpi-label {
  font-size: 0.65rem;
  color: #829AB1;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.kpi-val {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1.05rem;
  color: #FFFFFF;
  font-weight: 700;
}

.kpi-sub {
  font-size: 0.65rem;
  color: #627D98;
}
</style>
