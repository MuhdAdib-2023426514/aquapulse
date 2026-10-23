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

const unattendedObjects = computed(() => {
  if (store.mode === 'scenario') {
    return store.scenarioData?.system1_trace?.unattended_objects || []
  }
  return store.currentFrame?.system1_trace?.unattended_objects || []
})

const activeUnattendedObjects = computed(() => {
  return unattendedObjects.value.filter((o: any) => o.unattended_sec > 0 || o.is_hazard)
})
</script>

<template>
  <div class="timers-card">
    <div class="timers-header">
      <h4>⏱️ Stateful Escalation Timers</h4>
      <span class="header-sub">System 1 Temporal State Engine (&lt;30ms edge reflex)</span>
    </div>

    <div v-if="!activeDistressTracks.length && !activeViolationTracks.length && !activeUnattendedObjects.length" class="empty-timers">
      <span class="empty-title">🛡️ All Zones Normal — Baseline Monitoring</span>
      <small class="empty-desc">Timers engage automatically upon surface flailing, motionless submersion, or strata rule violations.</small>
    </div>

    <!-- Distress / Submersion Timers -->
    <div
      v-for="t in activeDistressTracks"
      :key="`distress-${t.track_id}`"
      class="timer-row distress-timer"
      :class="{
        'is-verify': t.agent_state === 'VERIFY',
        'is-critical': t.agent_state === 'CRITICAL_EMERGENCY'
      }"
    >
      <div class="timer-top">
        <strong class="track-title">Track #{{ t.track_id }} ({{ t.role }})</strong>
        <span class="timer-badge" :class="t.agent_state.toLowerCase()">
          {{ t.agent_state.replace('_', ' ') }} · {{ t.submersion_sec.toFixed(1) }}s
        </span>
      </div>

      <div class="progress-track">
        <div
          class="progress-fill"
          :style="{
            width: `${Math.min(100, (t.submersion_sec / 8.0) * 100)}%`,
            backgroundColor: t.submersion_sec >= 8.0 ? '#EF4444' : t.submersion_sec >= 5.0 ? '#F59E0B' : '#0284C7'
          }"
        ></div>
        <!-- 5s VERIFY marker -->
        <span class="marker marker-verify" style="left: 62.5%;">5s (Verify)</span>
        <!-- 8s CRITICAL marker -->
        <span class="marker marker-critical" style="left: 100%;">8s (Critical)</span>
      </div>

      <div class="timer-sub">
        <span v-if="t.is_supervised" class="text-green">
          ✓ Adult bystander within {{ t.nearest_adult_m?.toFixed(1) }}m assisting (Siren held in VERIFY)
        </span>
        <span v-else-if="t.submersion_sec >= 8.0" class="text-red">
          🚨 Confirmed unassisted submersion &gt;8s: 120dB directional siren &amp; guard dispatch active!
        </span>
        <span v-else-if="t.submersion_sec >= 5.0" class="text-amber">
          ⚠️ Stage 1 Caution: Motionless submerged in {{ t.zone.replace('ZONE_', '').replace('_', ' ') }}
        </span>
        <span v-else class="text-subtle">
          Submersion / flailing in {{ t.zone.replace('ZONE_', '').replace('_', ' ') }}
        </span>
      </div>
    </div>

    <!-- Rule Violation Timers -->
    <div v-for="t in activeViolationTracks" :key="`violation-${t.track_id}`" class="timer-row violation-timer">
      <div class="timer-top">
        <strong class="track-title">Track #{{ t.track_id }} · {{ t.violation_type.replace(/_/g, ' ') }}</strong>
        <span class="timer-badge nudge" :class="{ 'is-critical': t.nudge_count >= 2 }">
          {{ t.violation_sec.toFixed(1) }}s · {{ t.nudge_count }} nudges
        </span>
      </div>

      <div class="progress-track">
        <div
          class="progress-fill"
          :style="{
            width: `${Math.min(100, (t.violation_sec / 8.0) * 100)}%`,
            backgroundColor: t.nudge_count >= 2 ? '#A855F7' : t.violation_sec >= 5.0 ? '#F59E0B' : '#38BDF8'
          }"
        ></div>
        <span class="marker marker-nudge" style="left: 62.5%;">5s Nudge</span>
        <span class="marker marker-ticket" style="left: 100%;">8s Ticket</span>
      </div>

      <div class="timer-sub">
        <span class="text-subtle">
          {{ t.nudge_count >= 2 ? '🚨 Escalated to Guardhouse ticket (ignored 2 polite nudges)' : t.violation_sec >= 5.0 ? '📢 Directional audio voice nudge #1 fired' : 'Leaky bucket monitoring poolside activity' }}
        </span>
      </div>
    </div>

    <!-- Unattended Hazard Item Timers -->
    <div v-for="o in activeUnattendedObjects" :key="`unattended-${o.object_id}`" class="timer-row violation-timer">
      <div class="timer-top">
        <strong class="track-title">Unattended {{ o.label.toUpperCase() }} · {{ o.zone.replace(/_/g, ' ') }}</strong>
        <span class="timer-badge nudge" :class="{ 'is-critical': o.ticket_dispatched, 'is-warning': o.is_hazard }">
          {{ o.unattended_sec.toFixed(1) }}s · {{ o.ticket_dispatched ? 'Ticket Sent' : o.is_hazard ? 'Hazard' : 'Monitoring' }}
        </span>
      </div>

      <div class="progress-track">
        <div
          class="progress-fill"
          :style="{
            width: `${Math.min(100, (o.unattended_sec / 8.0) * 100)}%`,
            backgroundColor: o.ticket_dispatched ? '#A855F7' : o.is_hazard ? '#F59E0B' : '#0284C7'
          }"
        ></div>
        <span class="marker marker-nudge" style="left: 62.5%;">5s Hazard</span>
        <span class="marker marker-ticket" style="left: 100%;">8s Audio</span>
      </div>

      <div class="timer-sub">
        <span class="text-subtle">
          {{ o.ticket_dispatched ? '🎫 Housekeeping ticket opened' : o.is_hazard ? '⚠️ Slip/Fall hazard at pool perimeter' : 'Object tracking active' }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.timers-card {
  background: rgba(13, 23, 33, 0.95);
  border: 1px solid rgba(0, 229, 255, 0.3);
  border-radius: 10px;
  padding: 1.1rem;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  backdrop-filter: blur(8px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
}

.timers-header {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  border-bottom: 1px solid rgba(51, 78, 104, 0.3);
  padding-bottom: 0.5rem;
}

.timers-header h4 {
  margin: 0;
  font-size: 0.98rem;
  font-weight: 700;
  color: #FFFFFF;
}

.header-sub {
  font-size: 0.72rem;
  color: #94A3B8;
  font-family: 'JetBrains Mono', monospace;
}

.empty-timers {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 1rem;
  background: rgba(16, 28, 40, 0.7);
  border: 1px dashed rgba(56, 189, 248, 0.35);
  border-radius: 8px;
}

.empty-title {
  font-size: 0.82rem;
  font-weight: 600;
  color: #38BDF8;
}

.empty-desc {
  font-size: 0.72rem;
  color: #94A3B8;
}

.timer-row {
  background: rgba(18, 32, 46, 0.9);
  border: 1px solid rgba(51, 78, 104, 0.5);
  border-radius: 8px;
  padding: 0.85rem;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  transition: all 0.2s ease;
}

.distress-timer {
  border-left: 4px solid #0284C7;
}

.distress-timer.is-verify {
  border-left-color: #F59E0B;
  background: rgba(28, 34, 44, 0.95);
  box-shadow: 0 0 12px rgba(245, 158, 11, 0.15);
}

.distress-timer.is-critical {
  border-left-color: #EF4444;
  background: rgba(35, 20, 24, 0.95);
  box-shadow: 0 0 16px rgba(239, 68, 68, 0.25);
}

.violation-timer {
  border-left: 4px solid #A855F7;
}

.timer-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.track-title {
  font-size: 0.85rem;
  color: #FFFFFF;
  font-weight: 700;
}

.timer-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  padding: 0.2rem 0.55rem;
  border-radius: 4px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.timer-badge.critical_emergency {
  background: rgba(239, 68, 68, 0.25);
  color: #EF4444;
  border: 1px solid #EF4444;
  box-shadow: 0 0 8px rgba(239, 68, 68, 0.4);
}

.timer-badge.verify {
  background: rgba(245, 158, 11, 0.22);
  color: #F59E0B;
  border: 1px solid #F59E0B;
  box-shadow: 0 0 8px rgba(245, 158, 11, 0.3);
}

.timer-badge.normal {
  background: rgba(16, 185, 129, 0.18);
  color: #10B981;
  border: 1px solid #10B981;
}

.timer-badge.nudge {
  background: rgba(56, 189, 248, 0.18);
  color: #38BDF8;
  border: 1px solid #38BDF8;
}

.progress-track {
  position: relative;
  width: 100%;
  height: 9px;
  background: rgba(11, 20, 30, 0.9);
  border: 1px solid rgba(51, 78, 104, 0.6);
  border-radius: 5px;
  overflow: visible;
  margin: 0.65rem 0 0.35rem 0;
}

.progress-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 0 8px currentColor;
}

.marker {
  position: absolute;
  top: -16px;
  transform: translateX(-50%);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.marker-verify {
  color: #F59E0B;
}

.marker-critical {
  color: #EF4444;
  transform: translateX(-100%);
}

.marker-nudge {
  color: #38BDF8;
}

.marker-ticket {
  color: #A855F7;
  transform: translateX(-100%);
}

.timer-sub {
  font-size: 0.76rem;
  font-weight: 500;
  line-height: 1.35;
}

.text-subtle {
  color: #CBD5E1;
}

.text-amber {
  color: #F59E0B;
  font-weight: 600;
}

.text-green {
  color: #10B981;
  font-weight: 600;
}

.text-red {
  color: #EF4444;
  font-weight: 700;
}
</style>
