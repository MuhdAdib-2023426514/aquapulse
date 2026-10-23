<script setup lang="ts">
import { computed } from 'vue'
import { useAquaStore } from '../store'

const store = useAquaStore()

const thoughts = computed<any[]>(() => {
  if (store.mode === 'scenario') {
    return store.scenarioData?.reasoning_thoughts || []
  }
  return store.currentFrame?.reasoning_thoughts || []
})

function getThoughtText(t: any): string {
  if (typeof t === 'string') return t
  if (t && typeof t === 'object') {
    return t.thought || t.message || JSON.stringify(t)
  }
  return String(t)
}

function isAlert(text: string): boolean {
  return (
    text.includes('🚨') ||
    text.includes('⚠️') ||
    text.includes('EMERGENCY') ||
    text.includes('CRITICAL') ||
    text.includes('VERIFY')
  )
}
</script>

<template>
  <div class="reasoning-card">
    <div class="reasoning-topline">
      <h4>🧠 AI Reasoning &amp; Reflex Telemetry</h4>
      <span class="subtle">Autonomous System 1 reflex traces &amp; tool dispatch logs</span>
    </div>

    <div class="thoughts-terminal">
      <div v-for="(logItem, idx) in thoughts" :key="`thought-${idx}`" class="log-line">
        <span class="prompt-sym">&gt;</span>
        <span class="log-text" :class="{ alert: isAlert(getThoughtText(logItem)) }">
          {{ getThoughtText(logItem) }}
        </span>
      </div>
      <div v-if="!thoughts.length" class="empty-log">
        <span class="prompt-sym">&gt;</span>
        <span>Awaiting active perception events... Monitoring pool telemetry.</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.reasoning-card {
  background: rgba(13, 23, 33, 0.95);
  border: 1px solid rgba(0, 229, 255, 0.3);
  border-radius: 10px;
  padding: 1.1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  backdrop-filter: blur(8px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
}

.reasoning-topline {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  border-bottom: 1px solid rgba(51, 78, 104, 0.3);
  padding-bottom: 0.5rem;
}

.reasoning-topline h4 {
  margin: 0;
  font-size: 0.98rem;
  font-weight: 700;
  color: #FFFFFF;
}

.subtle {
  font-size: 0.72rem;
  color: #94A3B8;
  font-family: 'JetBrains Mono', monospace;
}

.thoughts-terminal {
  background: #080D15;
  border: 1px solid rgba(0, 229, 255, 0.25);
  border-radius: 8px;
  padding: 0.85rem;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.76rem;
  max-height: 180px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.6);
}

.log-line {
  display: flex;
  gap: 0.5rem;
  line-height: 1.4;
  word-break: break-word;
}

.prompt-sym {
  color: #00E5FF;
  font-weight: 700;
  user-select: none;
}

.log-text {
  color: #E2E8F0;
}

.log-text.alert {
  color: #FBBF24;
  font-weight: 600;
  text-shadow: 0 0 6px rgba(245, 158, 11, 0.3);
}

.empty-log {
  display: flex;
  gap: 0.5rem;
  color: #64748B;
  font-style: italic;
}
</style>
