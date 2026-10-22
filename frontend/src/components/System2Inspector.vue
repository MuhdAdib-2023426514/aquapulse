<script setup lang="ts">
import { computed } from 'vue'
import { api } from '../api'
import { useAquaStore } from '../store'

const store = useAquaStore()

const inspections = computed(() => {
  if (store.mode === 'scenario') {
    return store.scenarioData?.system2_inspections || []
  }
  return store.currentFrame?.system2_inspections || []
})

const roiImages = computed(() => {
  if (store.mode === 'scenario') return {}
  return store.currentFrame?.roi_images || {}
})

function getCropUrl(relPath: string): string {
  if (!store.activeJob) return ''
  return api.mediaUrl(store.activeJob.id, relPath)
}
</script>

<template>
  <div class="system2-card">
    <div class="sys2-header">
      <h4>🔍 System 2 Tier-1 Face-Masked ROI Inspector</h4>
      <span class="sys2-sub">3-Step Deliberative Visual Tool Chain (0% Biometric Leakage)</span>
    </div>

    <div v-if="!inspections.length && !Object.keys(roiImages).length" class="empty-sys2">
      <p>No active System 2 ROI inspections at this timestamp.</p>
      <small>When cotton attire, poolside drinks, or animals are suspected, System 2 executes face-masked ROI crop &amp; zoom inspection.</small>
    </div>

    <!-- Active ROI Images & Visual Tool Steps -->
    <div v-for="(insp, idx) in inspections" :key="`insp-${idx}`" class="inspection-item">
      <div class="inspection-top">
        <div class="crop-thumb-wrap">
          <img
            v-if="insp.track_id && roiImages[String(insp.track_id)]"
            :src="getCropUrl(roiImages[String(insp.track_id)])"
            alt="Tier-1 Face-Masked 2x Zoom ROI"
            class="roi-thumbnail"
          />
          <div v-else class="crop-placeholder">
            <span>ROI</span>
          </div>
          <span class="redaction-chip">Face Masked</span>
        </div>

        <div class="inspection-meta">
          <div class="meta-line">
            <strong>Target: Track #{{ insp.track_id }} ({{ insp.target_type }})</strong>
            <span class="backend-badge">{{ insp.inspector_backend }}</span>
          </div>
          <span class="verdict-chip" :class="{ verified: insp.verified_violation }">
            {{ insp.verified_violation ? `Verified: ${insp.violation_type}` : 'Unverified' }}
            ({{ (insp.confidence * 100).toFixed(0) }}% conf)
          </span>
          <p class="reasoning-p">{{ insp.reasoning_summary }}</p>
        </div>
      </div>

      <!-- 3-Step Visual Tool Chain Trace -->
      <div v-if="insp.visual_tool_steps?.length" class="tool-chain">
        <span class="chain-title">Visual Tool Execution Chain:</span>
        <ol class="steps-list">
          <li v-for="(step, sIdx) in insp.visual_tool_steps" :key="`step-${sIdx}`">
            <code>{{ step }}</code>
          </li>
        </ol>
      </div>
    </div>
  </div>
</template>

<style scoped>
.system2-card {
  background: rgba(15, 26, 36, 0.85);
  border: 1px solid rgba(51, 78, 104, 0.4);
  border-radius: 10px;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  backdrop-filter: blur(8px);
}

.sys2-header {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.sys2-header h4 {
  margin: 0;
  font-size: 0.95rem;
  color: #FFFFFF;
}

.sys2-sub {
  font-size: 0.7rem;
  color: #176776;
  font-family: 'JetBrains Mono', monospace;
}

.empty-sys2 {
  background: rgba(11, 22, 34, 0.5);
  border: 1px dashed rgba(51, 78, 104, 0.4);
  border-radius: 6px;
  padding: 1rem;
  font-size: 0.8rem;
  color: #617981;
}

.empty-sys2 small {
  font-size: 0.7rem;
  color: #72858B;
}

.inspection-item {
  background: rgba(11, 22, 34, 0.7);
  border: 1px solid rgba(51, 78, 104, 0.4);
  border-radius: 8px;
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.inspection-top {
  display: flex;
  gap: 0.85rem;
  align-items: flex-start;
}

.crop-thumb-wrap {
  position: relative;
  width: 72px;
  height: 72px;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid rgba(0, 229, 255, 0.4);
  background: #F5F8F9;
  flex-shrink: 0;
}

.roi-thumbnail {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.crop-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  color: #72858B;
}

.redaction-chip {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(255, 23, 68, 0.85);
  color: #FFFFFF;
  font-size: 0.55rem;
  text-align: center;
  font-weight: 700;
  text-transform: uppercase;
}

.inspection-meta {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 0;
}

.meta-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.8rem;
  color: #FFFFFF;
}

.backend-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.62rem;
  color: #397A68;
  background: rgba(0, 255, 102, 0.15);
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
}

.verdict-chip {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.68rem;
  color: #A56535;
  background: rgba(255, 145, 0, 0.15);
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
  width: fit-content;
  font-weight: 600;
}

.verdict-chip.verified {
  color: #A34E42;
  background: rgba(255, 82, 82, 0.15);
}

.reasoning-p {
  font-size: 0.75rem;
  color: #4B6269;
  line-height: 1.35;
  margin: 0;
}

.tool-chain {
  background: rgba(8, 16, 24, 0.8);
  border: 1px solid rgba(51, 78, 104, 0.3);
  border-radius: 6px;
  padding: 0.5rem 0.65rem;
}

.chain-title {
  font-size: 0.68rem;
  color: #617981;
  text-transform: uppercase;
  font-weight: 600;
}

.steps-list {
  margin: 0.25rem 0 0 1rem;
  font-size: 0.72rem;
  color: #176776;
}

.steps-list code {
  font-family: 'JetBrains Mono', monospace;
}
</style>
