<script setup lang="ts">
import { computed } from 'vue'
import { useAquaStore } from '../store'
import type { ToolExecutionLog } from '../types/aquapulse'

const store = useAquaStore()

const latestGuardAlert = computed<ToolExecutionLog | { tool_name: string; zone: any; guard_route_hint?: string; audio_tts_text?: string } | null>(() => {
  if (store.mode === 'scenario') {
    const logs = store.scenarioData?.tool_logs || []
    for (let i = logs.length - 1; i >= 0; i--) {
      const l = logs[i]
      if (
        l.tool_name.includes('emergency') ||
        l.tool_name.includes('guard') ||
        l.tool_name.includes('caution') ||
        l.tool_name.includes('beacon')
      ) {
        return l
      }
    }
    return null
  }

  // In video mode: check events that fired at or before playheadSec
  const events = store.events.filter(e => e.t <= store.playheadSec)
  for (let i = events.length - 1; i >= 0; i--) {
    const ev = events[i]
    if (
      ev.kind.includes('emergency') ||
      ev.kind.includes('guard') ||
      ev.kind.includes('caution') ||
      ev.kind.includes('beacon')
    ) {
      return {
        tool_name: ev.kind,
        zone: ev.zone,
        guard_route_hint: ev.guard_route_hint || undefined,
        audio_tts_text: ev.audio_tts_text || ev.message,
      }
    }
  }

  // Fallback to currentFrame tool_logs
  const logs = store.currentFrame?.tool_logs || []
  for (let i = logs.length - 1; i >= 0; i--) {
    const l = logs[i]
    if (
      l.tool_name.includes('emergency') ||
      l.tool_name.includes('guard') ||
      l.tool_name.includes('caution') ||
      l.tool_name.includes('beacon')
    ) {
      return l
    }
  }
  return null
})

const isCritical = computed(() => {
  return (
    latestGuardAlert.value?.tool_name.includes('emergency') ||
    store.overallState === 'CRITICAL_EMERGENCY'
  )
})

const isCautionVerify = computed(() => {
  if (isCritical.value) return false
  return (
    latestGuardAlert.value?.tool_name.includes('caution') ||
    latestGuardAlert.value?.tool_name.includes('beacon') ||
    store.overallState === 'VERIFY'
  )
})

const isGuardTicket = computed(() => {
  if (isCritical.value || isCautionVerify.value) return false
  return (
    latestGuardAlert.value?.tool_name.includes('guard') ||
    store.overallState === 'ESCALATED_GUARD_TICKET'
  )
})

const alertTitle = computed(() => {
  if (isCritical.value) return 'EMERGENCY DISPATCH'
  if (isCautionVerify.value) return 'CAUTION PRE-ALERT'
  if (isGuardTicket.value) return 'GUARD INCIDENT TICKET'
  return 'GUARD STANDBY'
})

const alertZone = computed(() => {
  if (latestGuardAlert.value?.zone) {
    return latestGuardAlert.value.zone.replace('ZONE_', '').replace('_', ' ')
  }
  if (isCautionVerify.value || isCritical.value) {
    return 'B DEEP END'
  }
  return 'All Zones Monitored'
})

const routeHint = computed(() => {
  if (latestGuardAlert.value?.guard_route_hint) {
    return latestGuardAlert.value.guard_route_hint
  }
  if (isCautionVerify.value || isCritical.value) {
    return 'Gate 2 (Deep End Access) via Block B Service Lift'
  }
  return 'Standard pool patrol route active'
})

const alertMessage = computed(() => {
  if (latestGuardAlert.value?.audio_tts_text) {
    return latestGuardAlert.value.audio_tts_text
  }
  if (isCritical.value) {
    return 'CRITICAL EMERGENCY: Submersion >8s in Zone B Deep End! Mobilize rescue immediately!'
  }
  if (isCautionVerify.value) {
    return 'Caution: Swimmer submerged >5s in Zone B Deep End. Security standby activated.'
  }
  return null
})
</script>

<template>
  <div class="guard-phone-card">
    <div class="phone-frame">
      <div class="phone-screen" :class="{ 'screen-critical': isCritical, 'screen-verify': isCautionVerify, 'screen-ticket': isGuardTicket }">
        <div class="phone-topbar">
          <span class="phone-time">16:40</span>
          <span class="phone-cam-notch"></span>
          <span class="phone-signal">5G 📶</span>
        </div>

        <div class="phone-alert-body">
          <div
            class="alert-icon-circle"
            :class="{
              'icon-critical': isCritical,
              'icon-verify': isCautionVerify,
              'icon-ticket': isGuardTicket,
              'icon-standby': !isCritical && !isCautionVerify && !isGuardTicket,
            }"
          >
            {{ isCritical ? '🚨' : isCautionVerify ? '⚠️' : isGuardTicket ? '🎫' : '🛡️' }}
          </div>

          <h5
            class="alert-title"
            :class="{
              'title-critical': isCritical,
              'title-verify': isCautionVerify,
              'title-ticket': isGuardTicket,
              'title-standby': !isCritical && !isCautionVerify && !isGuardTicket,
            }"
          >
            {{ alertTitle }}
          </h5>

          <p class="alert-zone">
            {{ alertZone }}
          </p>

          <div class="route-hint-box" :class="{ 'route-verify': isCautionVerify, 'route-critical': isCritical, 'route-ticket': isGuardTicket }">
            <span class="route-label">
              {{ isCritical ? 'Fastest Emergency Entry:' : isCautionVerify ? 'Pre-Alert Standby Gate:' : isGuardTicket ? 'Guardhouse Incident Dispatched:' : 'Patrol Route:' }}
            </span>
            <p class="route-text">{{ routeHint }}</p>
          </div>

          <p v-if="alertMessage" class="tts-quote">
            "{{ alertMessage }}"
          </p>

          <div class="phone-actions">
            <button class="phone-ack-btn" :class="{ 'ack-critical': isCritical, 'ack-verify': isCautionVerify, 'ack-ticket': isGuardTicket }">
              {{ isCritical ? 'DISPATCHED' : isCautionVerify ? 'ACKNOWLEDGE' : isGuardTicket ? 'TICKET OPEN' : 'CHECK' }}
            </button>
            <button class="phone-call-btn">Call JMB</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.guard-phone-card {
  display: flex;
  justify-content: center;
}

.phone-frame {
  width: 100%;
  max-width: 320px;
  background: #0B131E;
  border: 5px solid #1E293B;
  border-radius: 28px;
  padding: 0.45rem;
  box-shadow: 0 12px 36px rgba(0, 0, 0, 0.5);
}

.phone-screen {
  background: #0F172A;
  border-radius: 20px;
  padding: 0.85rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  border: 1px solid rgba(51, 78, 104, 0.4);
  transition: all 0.3s ease;
}

.phone-screen.screen-verify {
  border-color: rgba(245, 158, 11, 0.7);
  box-shadow: inset 0 0 16px rgba(245, 158, 11, 0.15);
}

.phone-screen.screen-ticket {
  border-color: rgba(179, 136, 255, 0.8);
  box-shadow: inset 0 0 18px rgba(179, 136, 255, 0.2);
}

.phone-screen.screen-critical {
  border-color: rgba(239, 68, 68, 0.85);
  box-shadow: inset 0 0 20px rgba(239, 68, 68, 0.25);
  animation: pulse-screen 1.2s infinite alternate;
}

@keyframes pulse-screen {
  from { border-color: rgba(239, 68, 68, 0.6); }
  to { border-color: rgba(239, 68, 68, 1); }
}

.phone-topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.7rem;
  color: #94A3B8;
  font-family: 'JetBrains Mono', monospace;
  padding-bottom: 0.4rem;
  border-bottom: 1px solid rgba(51, 78, 104, 0.3);
}

.phone-cam-notch {
  width: 34px;
  height: 4px;
  background: #334155;
  border-radius: 2px;
}

.phone-alert-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 0.45rem;
}

.alert-icon-circle {
  font-size: 1.6rem;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
}

.icon-standby {
  background: rgba(56, 189, 248, 0.12);
  border: 1px solid rgba(56, 189, 248, 0.35);
}

.icon-verify {
  background: rgba(245, 158, 11, 0.2);
  border: 1px solid #F59E0B;
  box-shadow: 0 0 14px rgba(245, 158, 11, 0.4);
}

.icon-ticket {
  background: rgba(179, 136, 255, 0.2);
  border: 1px solid #B388FF;
  box-shadow: 0 0 14px rgba(179, 136, 255, 0.4);
}

.icon-critical {
  background: rgba(239, 68, 68, 0.25);
  border: 1px solid #EF4444;
  box-shadow: 0 0 18px rgba(239, 68, 68, 0.6);
  animation: pulse-alert 0.9s infinite alternate;
}

@keyframes pulse-alert {
  from { transform: scale(0.95); }
  to { transform: scale(1.08); }
}

.alert-title {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 800;
  letter-spacing: 0.03em;
}

.title-standby {
  color: #38BDF8;
}

.title-verify {
  color: #F59E0B;
  text-shadow: 0 0 8px rgba(245, 158, 11, 0.5);
}

.title-ticket {
  color: #B388FF;
  text-shadow: 0 0 8px rgba(179, 136, 255, 0.5);
}

.title-critical {
  color: #EF4444;
  text-shadow: 0 0 10px rgba(239, 68, 68, 0.6);
}

.alert-zone {
  font-size: 0.78rem;
  color: #E2E8F0;
  font-weight: 700;
  margin: -0.15rem 0 0.15rem 0;
  letter-spacing: 0.02em;
}

.route-hint-box {
  background: rgba(15, 23, 42, 0.85);
  border: 1px solid rgba(51, 78, 104, 0.5);
  border-radius: 8px;
  padding: 0.5rem 0.65rem;
  width: 100%;
  text-align: left;
}

.route-hint-box.route-verify {
  border-color: rgba(245, 158, 11, 0.5);
  background: rgba(30, 24, 15, 0.8);
}

.route-hint-box.route-ticket {
  border-color: rgba(179, 136, 255, 0.6);
  background: rgba(25, 18, 38, 0.85);
}

.route-hint-box.route-critical {
  border-color: rgba(239, 68, 68, 0.6);
  background: rgba(35, 15, 18, 0.85);
}

.route-label {
  font-size: 0.65rem;
  color: #94A3B8;
  text-transform: uppercase;
  font-weight: 600;
  letter-spacing: 0.04em;
  display: block;
}

.route-text {
  font-size: 0.75rem;
  color: #F8FAFC;
  margin: 0.2rem 0 0 0;
  font-weight: 600;
  line-height: 1.3;
}

.tts-quote {
  font-size: 0.72rem;
  color: #CBD5E1;
  font-style: italic;
  line-height: 1.35;
  margin: 0.25rem 0;
  background: rgba(0, 0, 0, 0.25);
  padding: 0.35rem 0.5rem;
  border-radius: 6px;
  width: 100%;
  text-align: left;
}

.phone-actions {
  display: flex;
  gap: 0.5rem;
  width: 100%;
  margin-top: 0.25rem;
}

.phone-ack-btn {
  flex: 1;
  background: #0284C7;
  color: #FFFFFF;
  border: none;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 0.45rem;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.phone-ack-btn.ack-verify {
  background: #D97706;
}

.phone-ack-btn.ack-ticket {
  background: #7C3AED;
}

.phone-ack-btn.ack-critical {
  background: #DC2626;
}

.phone-call-btn {
  flex: 1;
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid #DC2626;
  color: #EF4444;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 0.45rem;
  border-radius: 6px;
  cursor: pointer;
}
</style>
