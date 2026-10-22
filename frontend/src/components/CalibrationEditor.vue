<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { api } from '../api'
import { useAquaStore } from '../store'
import type { PoolCalibration } from '../types/aquapulse'

const props = defineProps<{ jobId: string }>()
const emit = defineEmits<{ close: []; processed: [] }>()

const store = useAquaStore()
const job = computed(() => store.videos.find(v => v.id === props.jobId))

const previewSrc = computed(() => {
  return api.mediaUrl(props.jobId, 'preview.jpg')
})

const cal = reactive<PoolCalibration>({
  pool_corners_norm: [
    [0.05, 0.15],
    [0.95, 0.15],
    [0.95, 0.85],
    [0.05, 0.85],
  ],
  deep_end_side: 'right',
  deck_margin_norm: 0.04,
})

const timeScale = ref(1.0)
const sampleFps = ref(5.0)
const activeCorner = ref<number | null>(null)
const imageRef = ref<HTMLImageElement | null>(null)
const isSaving = ref(false)

watch(
  job,
  (j) => {
    if (j?.calibration) {
      cal.pool_corners_norm = j.calibration.pool_corners_norm.map(p => [p[0], p[1]])
      cal.deep_end_side = j.calibration.deep_end_side
      cal.deck_margin_norm = j.calibration.deck_margin_norm
      timeScale.value = j.time_scale || 1.0
      sampleFps.value = j.sample_fps || 5.0
    }
  },
  { immediate: true }
)

function onStageClick(e: MouseEvent) {
  if (!imageRef.value) return
  const rect = imageRef.value.getBoundingClientRect()
  const normX = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  const normY = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height))

  if (activeCorner.value !== null) {
    cal.pool_corners_norm[activeCorner.value] = [normX, normY]
    activeCorner.value = null
  }
}

function selectCorner(idx: number) {
  activeCorner.value = idx
}

async function saveAndProcess() {
  isSaving.value = true
  try {
    await store.saveConfig(props.jobId, {
      calibration: {
        pool_corners_norm: cal.pool_corners_norm,
        deep_end_side: cal.deep_end_side,
        deck_margin_norm: cal.deck_margin_norm,
      },
      time_scale: timeScale.value,
      sample_fps: sampleFps.value,
    })
    await store.processVideo(props.jobId)
    emit('processed')
  } catch (e: any) {
    alert(`Failed to save and process: ${e.message}`)
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <div class="modal-backdrop">
    <div class="calibration-modal">
      <div class="modal-header">
        <div>
          <h3>📐 Pool Geometry &amp; Perspective Calibration</h3>
          <p class="modal-sub">
            Click the 4 corners of the pool water surface on the face-masked preview below.
          </p>
        </div>
        <button class="close-btn" @click="$emit('close')">×</button>
      </div>

      <!-- Preview Image with Interactive Corner Handles -->
      <div class="calibration-stage" @click="onStageClick">
        <img ref="imageRef" :src="previewSrc" alt="Tier-1 Preview Frame" class="preview-img" />

        <svg class="calibration-overlay" viewBox="0 0 100 100" preserveAspectRatio="none">
          <!-- Polygon fill -->
          <polygon
            :points="cal.pool_corners_norm.map(p => `${p[0] * 100},${p[1] * 100}`).join(' ')"
            fill="rgba(0, 229, 255, 0.18)"
            stroke="#176776"
            stroke-width="0.8"
          />
        </svg>

        <!-- 4 Draggable Corner Handles -->
        <button
          v-for="(pt, idx) in cal.pool_corners_norm"
          :key="`corner-${idx}`"
          class="corner-handle"
          :class="{ active: activeCorner === idx }"
          :style="{ left: `${pt[0] * 100}%`, top: `${pt[1] * 100}%` }"
          @click.stop="selectCorner(idx)"
        >
          {{ ['TL', 'TR', 'BR', 'BL'][idx] }}
        </button>
      </div>

      <!-- Settings Controls -->
      <div class="calibration-controls">
        <div class="ctrl-group">
          <label>Deep End Side (Zone B >= 12.5m)</label>
          <select v-model="cal.deep_end_side">
            <option value="right">Right Side (Standard)</option>
            <option value="left">Left Side</option>
            <option value="bottom">Bottom</option>
            <option value="top">Top</option>
          </select>
        </div>

        <div class="ctrl-group">
          <label>Pitch Time Compression</label>
          <select v-model.number="timeScale">
            <option :value="1.0">1x (Official AGENTS.md 10s/20s/15s)</option>
            <option :value="2.0">2x Fast Demo (5s VERIFY / 10s CRITICAL / 7.5s Nudge)</option>
          </select>
        </div>

        <div class="ctrl-group">
          <label>Sample Processing FPS</label>
          <select v-model.number="sampleFps">
            <option :value="3.0">3 FPS (Fastest)</option>
            <option :value="5.0">5 FPS (Recommended · High Accuracy)</option>
            <option :value="10.0">10 FPS (Dense)</option>
          </select>
        </div>
      </div>

      <div class="modal-footer">
        <button class="secondary-btn" @click="$emit('close')">Cancel</button>
        <button class="primary-btn" :disabled="isSaving" @click="saveAndProcess">
          {{ isSaving ? 'Saving...' : '💾 Save Calibration & Start Processing' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(4, 10, 16, 0.88);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 1.5rem;
}

.calibration-modal {
  background: #FFFFFF;
  border: 1px solid rgba(0, 229, 255, 0.4);
  border-radius: 12px;
  width: 100%;
  max-width: 900px;
  max-height: 92vh;
  overflow-y: auto;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.8), 0 0 20px rgba(0, 229, 255, 0.15);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 700;
  color: #FFFFFF;
}

.modal-sub {
  font-size: 0.82rem;
  color: #5F737A;
  margin: 0.25rem 0 0 0;
}

.close-btn {
  background: transparent;
  border: none;
  color: #617981;
  font-size: 1.5rem;
  line-height: 1;
  cursor: pointer;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
}

.close-btn:hover {
  color: #FFFFFF;
  background: rgba(255, 23, 68, 0.2);
}

.calibration-stage {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: #F5F8F9;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid rgba(51, 78, 104, 0.6);
  cursor: crosshair;
  user-select: none;
}

.preview-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.calibration-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.corner-handle {
  position: absolute;
  transform: translate(-50%, -50%);
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #176776;
  color: #F5F8F9;
  font-weight: 800;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  border: 2px solid #FFFFFF;
  box-shadow: 0 0 12px #176776;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
  transition: transform 0.15s ease, background 0.15s ease;
}

.corner-handle:hover {
  transform: translate(-50%, -50%) scale(1.15);
  background: #84FFFF;
}

.corner-handle.active {
  background: #A34E42;
  border-color: #FFFFFF;
  color: #FFFFFF;
  box-shadow: 0 0 18px #A34E42;
  transform: translate(-50%, -50%) scale(1.25);
  animation: pulse-corner 1s infinite alternate;
}

@keyframes pulse-corner {
  from { box-shadow: 0 0 10px #A34E42; }
  to { box-shadow: 0 0 25px #A34E42; }
}

.calibration-controls {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
  background: rgba(11, 22, 34, 0.7);
  padding: 1rem;
  border-radius: 8px;
  border: 1px solid rgba(51, 78, 104, 0.4);
}

.ctrl-group {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.ctrl-group label {
  font-size: 0.72rem;
  color: #617981;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.ctrl-group select {
  background: #F5F8F9;
  border: 1px solid rgba(51, 78, 104, 0.6);
  color: #213D46;
  padding: 0.5rem 0.65rem;
  border-radius: 6px;
  font-size: 0.8rem;
  outline: none;
}

.ctrl-group select:focus {
  border-color: #176776;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid rgba(51, 78, 104, 0.3);
}

.secondary-btn {
  background: transparent;
  color: #5F737A;
  border: 1px solid rgba(51, 78, 104, 0.5);
  padding: 0.55rem 1.15rem;
  border-radius: 6px;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.secondary-btn:hover {
  color: #FFFFFF;
  border-color: rgba(0, 229, 255, 0.4);
}

.primary-btn {
  background: #176776;
  color: #F5F8F9;
  border: none;
  padding: 0.55rem 1.35rem;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 0 12px rgba(0, 229, 255, 0.3);
}

.primary-btn:hover:not(:disabled) {
  background: #84FFFF;
  transform: translateY(-1px);
}

.primary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
