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

    <!-- Empty / Standby State -->
    <div v-if="!inspections.length && !Object.keys(roiImages).length" class="empty-sys2">
      <div class="standby-header">
        <span class="standby-dot"></span>
        <strong class="standby-title">System 2 Deliberative Inspector in Standby</strong>
      </div>
      <p class="standby-desc">
        Life-safety reflexes (System 1) take priority. When non-emergency rule violations (cotton streetwear, poolside drinks, or stray pets) persist &gt;15s, System 2 engages automated face-masked ROI crop &amp; zoom inspection.
      </p>
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
            <strong class="target-title">Target: Track #{{ insp.track_id }} ({{ insp.target_type }})</strong>
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

.sys2-header {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  border-bottom: 1px solid rgba(51, 78, 104, 0.3);
  padding-bottom: 0.5rem;
}

.sys2-header h4 {
  margin: 0;
  font-size: 0.98rem;
  font-weight: 700;
  color: #FFFFFF;
}

.sys2-sub {
  font-size: 0.72rem;
  color: #38BDF8;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 500;
}

.empty-sys2 {
  background: rgba(16, 28, 40, 0.75);
  border: 1px dashed rgba(56, 189, 248, 0.35);
  border-radius: 8px;
  padding: 0.9rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.standby-header {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.standby-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #38BDF8;
  box-shadow: 0 0 8px #38BDF8;
}

.standby-title {
  font-size: 0.82rem;
  color: #F1F5F9;
  font-weight: 600;
}

.standby-desc {
  font-size: 0.75rem;
  color: #94A3B8;
  margin: 0;
  line-height: 1.45;
}

.inspection-item {
  background: rgba(18, 32, 46, 0.9);
  border: 1px solid rgba(51, 78, 104, 0.5);
  border-radius: 8px;
  padding: 0.85rem;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
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
  flex-shrink: 0;
  background: #0B141D;
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
  font-size: 0.7rem;
  color: #64748B;
  font-weight: 700;
}

.redaction-chip {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(0, 0, 0, 0.85);
  color: #38BDF8;
  font-size: 0.58rem;
  text-align: center;
  padding: 1px 0;
  font-weight: 700;
}

.inspection-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.meta-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.target-title {
  font-size: 0.82rem;
  color: #FFFFFF;
  font-weight: 700;
}

.backend-badge {
  font-size: 0.65rem;
  background: rgba(56, 189, 248, 0.15);
  border: 1px solid rgba(56, 189, 248, 0.3);
  color: #38BDF8;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
}

.verdict-chip {
  align-self: flex-start;
  font-size: 0.72rem;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-weight: 700;
  background: rgba(148, 163, 184, 0.15);
  color: #94A3B8;
  border: 1px solid rgba(148, 163, 184, 0.3);
}

.verdict-chip.verified {
  background: rgba(239, 68, 68, 0.2);
  color: #EF4444;
  border-color: #EF4444;
}

.reasoning-p {
  font-size: 0.74rem;
  color: #CBD5E1;
  margin: 0;
  line-height: 1.4;
}

.tool-chain {
  background: rgba(11, 20, 29, 0.85);
  border: 1px solid rgba(51, 78, 104, 0.4);
  border-radius: 6px;
  padding: 0.5rem 0.65rem;
}

.chain-title {
  font-size: 0.68rem;
  font-weight: 600;
  color: #64748B;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.steps-list {
  margin: 0.25rem 0 0 1rem;
  padding: 0;
  font-size: 0.7rem;
  color: #38BDF8;
}

.steps-list code {
  color: #E2E8F0;
  background: rgba(0, 0, 0, 0.3);
  padding: 0.1rem 0.3rem;
  border-radius: 3px;
  font-family: 'JetBrains Mono', monospace;
}
</style>
