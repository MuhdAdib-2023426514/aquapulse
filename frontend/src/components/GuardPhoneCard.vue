<script setup lang="ts">
import { computed } from 'vue'
import { useAquaStore } from '../store'
import type { ToolExecutionLog } from '../types/aquapulse'

const store = useAquaStore()

const latestGuardAlert = computed<ToolExecutionLog | null>(() => {
  const logs = (store.mode === 'scenario'
    ? store.scenarioData?.tool_logs
    : store.currentFrame?.tool_logs) || []

  // Find latest emergency or guard ticket
  for (let i = logs.length - 1; i >= 0; i--) {
    const l = logs[i]
    if (l.tool_name.includes('emergency') || l.tool_name.includes('guard')) {
      return l
    }
  }
  return null
})
</script>

<template>
  <div class="guard-phone-card">
    <div class="phone-frame">
      <div class="phone-screen">
        <div class="phone-topbar">
          <span class="phone-time">16:40</span>
          <span class="phone-cam-notch"></span>
          <span class="phone-signal">5G 📶</span>
        </div>

        <div class="phone-alert-body">
          <div class="alert-icon-circle" :class="{ critical: latestGuardAlert?.system_path === 'SYSTEM_1' }">
            {{ latestGuardAlert?.system_path === 'SYSTEM_1' ? '🚨' : '🎫' }}
          </div>

          <h5 class="alert-title">
            {{ latestGuardAlert ? (latestGuardAlert.system_path === 'SYSTEM_1' ? 'EMERGENCY DISPATCH' : 'GUARD INCIDENT TICKET') : 'GUARD STANDBY' }}
          </h5>

          <p class="alert-zone">
            {{ latestGuardAlert ? latestGuardAlert.zone.replace('ZONE_', '').replace('_', ' ') : 'All Zones Monitored' }}
          </p>

          <div v-if="latestGuardAlert" class="route-hint-box">
            <span class="route-label">Fastest Entry Route:</span>
            <p class="route-text">{{ latestGuardAlert.guard_route_hint || 'Enter via Deck B access gate' }}</p>
          </div>

          <p v-if="latestGuardAlert?.audio_tts_text" class="tts-quote">
            "{{ latestGuardAlert.audio_tts_text }}"
          </p>

          <div class="phone-actions">
            <button class="phone-ack-btn">Acknowledge</button>
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
  background: #F5F8F9;
  border: 6px solid #1E293B;
  border-radius: 28px;
  padding: 0.5rem;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
}

.phone-screen {
  background: #FFFFFF;
  border-radius: 20px;
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.phone-topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.7rem;
  color: #617981;
  font-family: 'JetBrains Mono', monospace;
  padding-bottom: 0.35rem;
  border-bottom: 1px solid rgba(51, 78, 104, 0.3);
}

.phone-cam-notch {
  width: 32px;
  height: 4px;
  background: #DCE6E9;
  border-radius: 2px;
}

.phone-alert-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 0.4rem;
}

.alert-icon-circle {
  font-size: 1.75rem;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: rgba(0, 229, 255, 0.1);
  border: 1px solid rgba(0, 229, 255, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
}

.alert-icon-circle.critical {
  background: rgba(255, 23, 68, 0.2);
  border-color: #A34E42;
  box-shadow: 0 0 15px rgba(255, 23, 68, 0.4);
  animation: pulse-alert 1s infinite alternate;
}

@keyframes pulse-alert {
  from { transform: scale(0.95); }
  to { transform: scale(1.05); }
}

.alert-title {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 700;
  color: #FFFFFF;
}

.alert-zone {
  font-size: 0.75rem;
  color: #176776;
  font-weight: 600;
}

.route-hint-box {
  background: rgba(11, 22, 34, 0.8);
  border: 1px solid rgba(0, 229, 255, 0.25);
  border-radius: 6px;
  padding: 0.5rem;
  width: 100%;
  text-align: left;
}

.route-label {
  font-size: 0.65rem;
  color: #617981;
  text-transform: uppercase;
}

.route-text {
  font-size: 0.75rem;
  color: #FFFFFF;
  margin: 0.15rem 0 0 0;
  font-weight: 500;
}

.tts-quote {
  font-size: 0.72rem;
  color: #B1782A;
  font-style: italic;
  line-height: 1.35;
  margin: 0.25rem 0;
}

.phone-actions {
  display: flex;
  gap: 0.5rem;
  width: 100%;
  margin-top: 0.25rem;
}

.phone-ack-btn {
  flex: 1;
  background: #176776;
  color: #F5F8F9;
  border: none;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 0.4rem;
  border-radius: 4px;
  cursor: pointer;
}

.phone-call-btn {
  flex: 1;
  background: rgba(255, 23, 68, 0.15);
  border: 1px solid #A34E42;
  color: #A34E42;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 0.4rem;
  border-radius: 4px;
  cursor: pointer;
}
</style>
