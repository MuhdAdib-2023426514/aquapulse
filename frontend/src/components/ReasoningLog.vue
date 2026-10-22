<script setup lang="ts">
import { computed } from 'vue'
import { useAquaStore } from '../store'

const store = useAquaStore()

const thoughts = computed<string[]>(() => {
  if (store.mode === 'scenario') {
    return store.scenarioData?.reasoning_thoughts || []
  }
  return store.currentFrame?.reasoning_thoughts || []
})
</script>

<template>
  <div class="reasoning-card">
    <div class="reasoning-topline">
      <h4>🧠 Analysis notes</h4>
      <span class="subtle">Experimental cues; review manually</span>
    </div>

    <div class="thoughts-terminal">
      <div v-for="(log, idx) in thoughts" :key="`thought-${idx}`" class="log-line">
        <span class="prompt-sym">&gt;</span>
        <span class="log-text" :class="{ alert: log.includes('🚨') || log.includes('⚠️') || log.includes('EMERGENCY') }">
          {{ log }}
        </span>
      </div>
      <div v-if="!thoughts.length" class="empty-log">
        <span>No analysis notes for this clip.</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.reasoning-card {
  background: rgba(15, 26, 36, 0.85);
  border: 1px solid rgba(51, 78, 104, 0.4);
  border-radius: 10px;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  backdrop-filter: blur(8px);
}

.reasoning-topline {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.reasoning-topline h4 {
  margin: 0;
  font-size: 0.95rem;
  color: #FFFFFF;
}

.subtle {
  font-size: 0.7rem;
  color: #617981;
}

.thoughts-terminal {
  background: #F5F8F9;
  border: 1px solid rgba(51, 78, 104, 0.5);
  border-radius: 6px;
  padding: 0.75rem;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  max-height: 150px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.log-line {
  display: flex;
  gap: 0.4rem;
  line-height: 1.35;
}

.prompt-sym {
  color: #176776;
}

.log-text {
  color: #4B6269;
}

.log-text.alert {
  color: #FF80AB;
}

.empty-log {
  color: #72858B;
  font-style: italic;
}
</style>
