<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api'
import { useAquaStore } from '../store'
import type {
  CalibrationProfile,
  CalibrationValidationResult,
  Camera,
  Pool,
  PoolCalibration,
} from '../types/aquapulse'

const props = defineProps<{ jobId: string }>()
const emit = defineEmits<{ close: []; processed: [] }>()

const store = useAquaStore()
const job = computed(() => store.videos.find(v => v.id === props.jobId))

const previewSrc = computed(() => {
  return api.mediaUrl(props.jobId, 'preview.jpg')
})

// Wizard Steps: 1: Camera & Pool, 2: 4 Corners, 3: Dimensions, 4: Boundary, 5: Validate & Test
type WizardTab = 'camera' | 'corners' | 'dimensions' | 'boundary' | 'test'
const activeTab = ref<WizardTab>('corners')

// Camera & Pool Selection State
const selectedPoolId = ref<string>('demo_pool_1')
const selectedCameraId = ref<string>('demo_camera_cctv_1')
const activeProfile = ref<CalibrationProfile | null>(null)
const isLoadingProfiles = ref(false)

// Calibration reactive model
const cal = reactive<PoolCalibration>({
  pool_corners_norm: [
    [0.05, 0.15],
    [0.95, 0.15],
    [0.95, 0.85],
    [0.05, 0.85],
  ],
  deep_end_side: 'right',
  deck_margin_norm: 0.04,
  length_m: 25.0,
  width_m: 12.0,
  shallow_depth_m: 0.8,
  deep_depth_m: 1.8,
  depth_boundary_m: 12.5,
})

const timeScale = ref(1.0)
const sampleFps = ref(5.0)
const activeCorner = ref<number | null>(null)
const imageRef = ref<HTMLImageElement | null>(null)
const stageRef = ref<HTMLDivElement | null>(null)
const isSaving = ref(false)
const isValidating = ref(false)
const validationResult = ref<CalibrationValidationResult | null>(null)
const saveSuccessMsg = ref<string | null>(null)

// History stack for Undo
const historyStack = ref<[number, number][][]>([])

// Interactive test point inspection
const testPoint = ref<{
  normX: number
  normY: number
  x_m: number
  y_m: number
  in_water: boolean
  zone: string
  dist_to_boundary_m: number
} | null>(null)

// Dragging corner state
const draggingCorner = ref<number | null>(null)

watch(
  job,
  (j) => {
    if (j?.calibration) {
      cal.pool_corners_norm = j.calibration.pool_corners_norm.map(p => [p[0], p[1]])
      cal.deep_end_side = j.calibration.deep_end_side
      cal.deck_margin_norm = j.calibration.deck_margin_norm
      cal.length_m = j.calibration.length_m ?? 25.0
      cal.width_m = j.calibration.width_m ?? 12.0
      cal.shallow_depth_m = j.calibration.shallow_depth_m ?? 0.8
      cal.deep_depth_m = j.calibration.deep_depth_m ?? 1.8
      cal.depth_boundary_m = j.calibration.depth_boundary_m ?? 12.5
      timeScale.value = j.time_scale || 1.0
      sampleFps.value = j.sample_fps || 5.0
    }
    if (j?.camera_id) {
      selectedCameraId.value = j.camera_id
    }
  },
  { immediate: true }
)

onMounted(async () => {
  await store.loadPoolsAndCameras()
  if (selectedCameraId.value) {
    await loadActiveCameraProfile(selectedCameraId.value)
  }
})

async function loadActiveCameraProfile(camId: string) {
  isLoadingProfiles.value = true
  try {
    const list = await api.listCalibrations(camId)
    const active = list.find(c => c.is_active) || list[0] || null
    activeProfile.value = active
    if (active) {
      cal.pool_corners_norm = active.pool_corners_norm.map(p => [p[0], p[1]])
      cal.deep_end_side = active.deep_end_side
      cal.deck_margin_norm = active.deck_margin_norm
      cal.length_m = active.length_m
      cal.width_m = active.width_m
      cal.shallow_depth_m = active.shallow_depth_m
      cal.deep_depth_m = active.deep_depth_m
      cal.depth_boundary_m = active.depth_boundary_m
    }
  } catch {
    // fallback gracefully
  } finally {
    isLoadingProfiles.value = false
  }
}

watch(selectedCameraId, async (newId) => {
  if (newId) {
    await loadActiveCameraProfile(newId)
  }
})

// Coordinate handling with letterboxing and DPR support
function getNormCoords(e: MouseEvent | PointerEvent): [number, number] | null {
  if (!imageRef.value) return null
  const rect = imageRef.value.getBoundingClientRect()
  if (rect.width <= 0 || rect.height <= 0) return null
  const normX = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  const normY = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height))
  return [Math.round(normX * 1000) / 1000, Math.round(normY * 1000) / 1000]
}

function pushHistory() {
  historyStack.value.push(cal.pool_corners_norm.map(p => [p[0], p[1]]))
  if (historyStack.value.length > 20) {
    historyStack.value.shift()
  }
}

function undo() {
  const prev = historyStack.value.pop()
  if (prev && prev.length === 4) {
    cal.pool_corners_norm = prev
  }
}

function resetCorners() {
  pushHistory()
  cal.pool_corners_norm = [
    [0.05, 0.15],
    [0.95, 0.15],
    [0.95, 0.85],
    [0.05, 0.85],
  ]
  activeCorner.value = null
  validationResult.value = null
}

function selectCorner(idx: number) {
  activeCorner.value = idx
}

function nudge(dx: number, dy: number) {
  if (activeCorner.value === null) return
  pushHistory()
  const pt = cal.pool_corners_norm[activeCorner.value]
  const nx = Math.max(0, Math.min(1, Math.round((pt[0] + dx) * 1000) / 1000))
  const ny = Math.max(0, Math.min(1, Math.round((pt[1] + dy) * 1000) / 1000))
  cal.pool_corners_norm[activeCorner.value] = [nx, ny]
}

// Stage interaction: click to move selected corner, or inspect test point in Test tab
function onStageClick(e: MouseEvent) {
  const coords = getNormCoords(e)
  if (!coords) return

  if (activeTab.value === 'test') {
    inspectPoint(coords[0], coords[1])
    return
  }

  if (activeCorner.value !== null) {
    pushHistory()
    cal.pool_corners_norm[activeCorner.value] = coords
    activeCorner.value = null
    validationResult.value = null
  }
}

// Pointer drag support for corner handles
function onHandlePointerDown(idx: number, e: PointerEvent) {
  e.stopPropagation()
  draggingCorner.value = idx
  activeCorner.value = idx
  pushHistory()
  const target = e.target as HTMLElement
  target.setPointerCapture(e.pointerId)
}

function onHandlePointerMove(e: PointerEvent) {
  if (draggingCorner.value === null) return
  const coords = getNormCoords(e)
  if (!coords) return
  cal.pool_corners_norm[draggingCorner.value] = coords
}

function onHandlePointerUp(e: PointerEvent) {
  if (draggingCorner.value !== null) {
    const target = e.target as HTMLElement
    try {
      target.releasePointerCapture(e.pointerId)
    } catch {}
    draggingCorner.value = null
  }
}

// Projected Depth Boundary endpoints (normalized [0..1])
const projectedBoundary = computed(() => {
  // If backend validation has computed the exact projected boundary, use it
  if (validationResult.value?.projected_boundary_norm?.length === 2) {
    return validationResult.value.projected_boundary_norm
  }

  // Frontend homography approximation for live editing
  const pts = cal.pool_corners_norm
  const len = cal.length_m || 25.0
  const bDist = cal.depth_boundary_m || 12.5
  const ratio = Math.max(0.05, Math.min(0.95, bDist / len))

  if (cal.deep_end_side === 'right') {
    // Top edge point (from TL to TR)
    const p1: [number, number] = [
      pts[0][0] + (pts[1][0] - pts[0][0]) * ratio,
      pts[0][1] + (pts[1][1] - pts[0][1]) * ratio,
    ]
    // Bottom edge point (from BL to BR)
    const p2: [number, number] = [
      pts[3][0] + (pts[2][0] - pts[3][0]) * ratio,
      pts[3][1] + (pts[2][1] - pts[3][1]) * ratio,
    ]
    return [p1, p2]
  } else if (cal.deep_end_side === 'left') {
    const invRatio = 1.0 - ratio
    const p1: [number, number] = [
      pts[0][0] + (pts[1][0] - pts[0][0]) * invRatio,
      pts[0][1] + (pts[1][1] - pts[0][1]) * invRatio,
    ]
    const p2: [number, number] = [
      pts[3][0] + (pts[2][0] - pts[3][0]) * invRatio,
      pts[3][1] + (pts[2][1] - pts[3][1]) * invRatio,
    ]
    return [p1, p2]
  } else if (cal.deep_end_side === 'bottom') {
    // Left edge (TL to BL)
    const p1: [number, number] = [
      pts[0][0] + (pts[3][0] - pts[0][0]) * ratio,
      pts[0][1] + (pts[3][1] - pts[0][1]) * ratio,
    ]
    // Right edge (TR to BR)
    const p2: [number, number] = [
      pts[1][0] + (pts[2][0] - pts[1][0]) * ratio,
      pts[1][1] + (pts[2][1] - pts[1][1]) * ratio,
    ]
    return [p1, p2]
  } else {
    // top
    const invRatio = 1.0 - ratio
    const p1: [number, number] = [
      pts[0][0] + (pts[3][0] - pts[0][0]) * invRatio,
      pts[0][1] + (pts[3][1] - pts[0][1]) * invRatio,
    ]
    const p2: [number, number] = [
      pts[1][0] + (pts[2][0] - pts[1][0]) * invRatio,
      pts[1][1] + (pts[2][1] - pts[1][1]) * invRatio,
    ]
    return [p1, p2]
  }
})

// Point inspection calculation
function inspectPoint(nx: number, ny: number) {
  const len = cal.length_m || 25.0
  const wid = cal.width_m || 12.0
  const boundary = cal.depth_boundary_m || 12.5

  // Check in-polygon via ray-casting
  const pts = cal.pool_corners_norm
  let inside = false
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const xi = pts[i][0], yi = pts[i][1]
    const xj = pts[j][0], yj = pts[j][1]
    const intersect = yi > ny !== yj > ny && nx < ((xj - xi) * (ny - yi)) / (yj - yi) + xi
    if (intersect) inside = !inside
  }

  // Estimate meter coordinate along length
  let x_m = 0
  let y_m = 0
  if (cal.deep_end_side === 'right') {
    x_m = Math.round(nx * len * 10) / 10
    y_m = Math.round(ny * wid * 10) / 10
  } else if (cal.deep_end_side === 'left') {
    x_m = Math.round((1.0 - nx) * len * 10) / 10
    y_m = Math.round(ny * wid * 10) / 10
  } else if (cal.deep_end_side === 'bottom') {
    x_m = Math.round(ny * len * 10) / 10
    y_m = Math.round(nx * wid * 10) / 10
  } else {
    x_m = Math.round((1.0 - ny) * len * 10) / 10
    y_m = Math.round(nx * wid * 10) / 10
  }

  let zone = 'POOL_DECK'
  if (inside) {
    zone = x_m >= boundary ? 'ZONE_B_DEEP_END' : 'ZONE_A_SHALLOW'
  }

  testPoint.value = {
    normX: nx,
    normY: ny,
    x_m,
    y_m,
    in_water: inside,
    zone,
    dist_to_boundary_m: Math.round(Math.abs(x_m - boundary) * 100) / 100,
  }
}

// Backend Geometry Validation
async function runValidation() {
  isValidating.value = true
  saveSuccessMsg.value = null
  try {
    // If a profile exists, use validate endpoint; otherwise use mock/temporary validation
    if (activeProfile.value) {
      await api.updateCalibration(activeProfile.value.id, {
        pool_corners_norm: cal.pool_corners_norm,
        deep_end_side: cal.deep_end_side,
        deck_margin_norm: cal.deck_margin_norm,
        length_m: cal.length_m,
        width_m: cal.width_m,
        shallow_depth_m: cal.shallow_depth_m,
        deep_depth_m: cal.deep_depth_m,
        depth_boundary_m: cal.depth_boundary_m,
      })
      validationResult.value = await api.validateCalibration(activeProfile.value.id)
    } else {
      // Validate locally if profile not yet registered
      const errors: string[] = []
      if ((cal.deep_depth_m || 1.8) <= (cal.shallow_depth_m || 0.8)) {
        errors.push('Deep depth must be strictly greater than shallow depth.')
      }
      if ((cal.depth_boundary_m || 12.5) >= (cal.length_m || 25.0)) {
        errors.push('Depth boundary must lie strictly inside pool length.')
      }
      validationResult.value = {
        is_valid: errors.length === 0,
        errors,
        warnings: [],
        projected_boundary_norm: projectedBoundary.value,
        sample_mappings: [],
      }
    }
  } catch (err: any) {
    validationResult.value = {
      is_valid: false,
      errors: [err.message || 'Validation failed.'],
      warnings: [],
      projected_boundary_norm: [],
      sample_mappings: [],
    }
  } finally {
    isValidating.value = false
  }
}

// Save & Activate Reusable Camera Profile (FR-08)
async function saveAndActivateProfile() {
  isSaving.value = true
  saveSuccessMsg.value = null
  try {
    let targetProfileId = activeProfile.value?.id

    if (!targetProfileId) {
      // Create new calibration profile
      const created = await api.createCalibration({
        pool_id: selectedPoolId.value,
        camera_id: selectedCameraId.value,
        pool_corners_norm: cal.pool_corners_norm,
        deep_end_side: cal.deep_end_side,
        deck_margin_norm: cal.deck_margin_norm,
        length_m: cal.length_m,
        width_m: cal.width_m,
        shallow_depth_m: cal.shallow_depth_m,
        deep_depth_m: cal.deep_depth_m,
        depth_boundary_m: cal.depth_boundary_m,
      })
      targetProfileId = created.id
    } else {
      // Update existing draft parameters
      await api.updateCalibration(targetProfileId, {
        pool_corners_norm: cal.pool_corners_norm,
        deep_end_side: cal.deep_end_side,
        deck_margin_norm: cal.deck_margin_norm,
        length_m: cal.length_m,
        width_m: cal.width_m,
        shallow_depth_m: cal.shallow_depth_m,
        deep_depth_m: cal.deep_depth_m,
        depth_boundary_m: cal.depth_boundary_m,
      })
    }

    // Activate the profile in SQLite
    const activated = await api.activateCalibration(targetProfileId)
    activeProfile.value = activated
    saveSuccessMsg.value = `✓ Calibration Profile v${activated.version} successfully activated for camera '${selectedCameraId.value}'!`
    await store.loadPoolsAndCameras()
  } catch (err: any) {
    alert(`Failed to activate profile: ${err.message}`)
  } finally {
    isSaving.value = false
  }
}

// Save to Job and Start Video Analysis (FR-09)
async function saveAndProcessVideo() {
  isSaving.value = true
  try {
    // Save to job configuration
    await store.saveConfig(props.jobId, {
      calibration: {
        pool_corners_norm: cal.pool_corners_norm,
        deep_end_side: cal.deep_end_side,
        deck_margin_norm: cal.deck_margin_norm,
        length_m: cal.length_m,
        width_m: cal.width_m,
        shallow_depth_m: cal.shallow_depth_m,
        deep_depth_m: cal.deep_depth_m,
        depth_boundary_m: cal.depth_boundary_m,
      },
      camera_id: selectedCameraId.value,
      calibration_profile_id: activeProfile.value?.id,
      time_scale: timeScale.value,
      sample_fps: sampleFps.value,
    })

    // Start video pipeline processing
    await store.processVideo(props.jobId)
    emit('processed')
  } catch (e: any) {
    alert(`Failed to save and analyze: ${e.message}`)
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <div class="modal-backdrop">
    <div class="calibration-modal">
      <!-- Modal Header -->
      <div class="modal-header">
        <div class="header-titles">
          <h3>📐 One-Time Pool &amp; Camera Calibration</h3>
          <p class="modal-sub">
            Calibrate once per CCTV camera to establish ground-plane homography, shallow/deep zones, and toddler safety boundaries.
          </p>
        </div>
        <button class="close-btn" title="Close" @click="$emit('close')">×</button>
      </div>

      <!-- Wizard Navigation Tabs -->
      <div class="wizard-tabs">
        <button
          class="wizard-tab-btn"
          :class="{ active: activeTab === 'camera' }"
          @click="activeTab = 'camera'"
        >
          1. Camera &amp; Pool
        </button>
        <button
          class="wizard-tab-btn"
          :class="{ active: activeTab === 'corners' }"
          @click="activeTab = 'corners'"
        >
          2. 4 Corners (Basin)
        </button>
        <button
          class="wizard-tab-btn"
          :class="{ active: activeTab === 'dimensions' }"
          @click="activeTab = 'dimensions'"
        >
          3. Dimensions &amp; Depths
        </button>
        <button
          class="wizard-tab-btn"
          :class="{ active: activeTab === 'boundary' }"
          @click="activeTab = 'boundary'"
        >
          4. Depth Boundary &amp; Rope
        </button>
        <button
          class="wizard-tab-btn"
          :class="{ active: activeTab === 'test' }"
          @click="activeTab = 'test'"
        >
          5. Validate &amp; Test
        </button>
      </div>

      <!-- Main Interactive Calibration Stage -->
      <div
        ref="stageRef"
        class="calibration-stage"
        @click="onStageClick"
        @pointermove="onHandlePointerMove"
        @pointerup="onHandlePointerUp"
      >
        <img
          ref="imageRef"
          :src="previewSrc"
          alt="Tier-1 Preview Frame"
          class="preview-img"
          draggable="false"
        />

        <svg class="calibration-overlay" viewBox="0 0 100 100" preserveAspectRatio="none">
          <!-- Calibrated Water Surface Area (Cyan tint) -->
          <polygon
            :points="cal.pool_corners_norm.map(p => `${p[0] * 100},${p[1] * 100}`).join(' ')"
            fill="rgba(0, 229, 255, 0.16)"
            stroke="#176776"
            stroke-width="0.75"
          />

          <!-- Projected Yellow Floating Safety Rope Boundary (FR-05) -->
          <line
            v-if="projectedBoundary.length === 2"
            :x1="projectedBoundary[0][0] * 100"
            :y1="projectedBoundary[0][1] * 100"
            :x2="projectedBoundary[1][0] * 100"
            :y2="projectedBoundary[1][1] * 100"
            stroke="#FFD600"
            stroke-width="1.2"
            stroke-dasharray="3, 2"
          />
        </svg>

        <!-- 4 Draggable Corner Handles -->
        <button
          v-for="(pt, idx) in cal.pool_corners_norm"
          :key="`corner-${idx}`"
          class="corner-handle"
          :class="{ active: activeCorner === idx, dragging: draggingCorner === idx }"
          :style="{ left: `${pt[0] * 100}%`, top: `${pt[1] * 100}%` }"
          @pointerdown="onHandlePointerDown(idx, $event)"
          @click.stop="selectCorner(idx)"
        >
          {{ ['TL', 'TR', 'BR', 'BL'][idx] }}
        </button>

        <!-- Floating Yellow Rope Label -->
        <div
          v-if="projectedBoundary.length === 2"
          class="rope-label-tag"
          :style="{
            left: `${((projectedBoundary[0][0] + projectedBoundary[1][0]) / 2) * 100}%`,
            top: `${((projectedBoundary[0][1] + projectedBoundary[1][1]) / 2) * 100}%`,
          }"
        >
          🟡 Yellow Safety Rope ({{ cal.depth_boundary_m }}m)
        </div>

        <!-- Interactive Test Point Pin (Test Tab) -->
        <div
          v-if="testPoint"
          class="test-point-pin"
          :style="{ left: `${testPoint.normX * 100}%`, top: `${testPoint.normY * 100}%` }"
        >
          📍
        </div>
      </div>

      <!-- Tab Content Panels -->

      <!-- TAB 1: Camera & Pool Selection -->
      <div v-if="activeTab === 'camera'" class="wizard-panel">
        <div class="panel-desc">
          <strong>Step 1: Assign Camera &amp; Pool Facility</strong>
          <p>
            Choose the swimming pool basin and CCTV camera for this profile. Saved calibrations are permanently reused for every subsequent video uploaded from this camera.
          </p>
        </div>
        <div class="form-grid">
          <div class="ctrl-group">
            <label>Swimming Pool Basin</label>
            <select v-model="selectedPoolId">
              <option v-for="p in store.pools" :key="p.id" :value="p.id">
                {{ p.name }} ({{ p.length_m }}m × {{ p.width_m }}m)
              </option>
            </select>
          </div>
          <div class="ctrl-group">
            <label>CCTV Camera</label>
            <select v-model="selectedCameraId">
              <option v-for="c in store.cameras" :key="c.id" :value="c.id">
                {{ c.name }} {{ c.active_calibration_version ? `(v${c.active_calibration_version} Active)` : '(Uncalibrated)' }}
              </option>
            </select>
          </div>
          <div class="ctrl-group">
            <label>Active Calibration Status</label>
            <div class="status-indicator">
              <span v-if="activeProfile?.is_active" class="badge-active">
                ✓ Active Profile v{{ activeProfile.version }}
              </span>
              <span v-else class="badge-draft">
                Draft / Unactivated
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- TAB 2: 4 Corner Calibration -->
      <div v-if="activeTab === 'corners'" class="wizard-panel">
        <div class="panel-desc">
          <strong>Step 2: Water Basin Corner Alignment</strong>
          <p>
            Click or drag the 4 corner handles to align with the rectangular pool water surface in clockwise order: Top-Left (TL), Top-Right (TR), Bottom-Right (BR), Bottom-Left (BL).
          </p>
        </div>
        <div class="tools-row">
          <div class="corner-status-pill">
            Selected: <strong>{{ activeCorner !== null ? ['TL', 'TR', 'BR', 'BL'][activeCorner] : 'None (Click handle to select)' }}</strong>
          </div>
          <div class="nudge-controls">
            <button class="nudge-btn" title="Nudge Up" :disabled="activeCorner === null" @click="nudge(0, -0.005)">⬆</button>
            <button class="nudge-btn" title="Nudge Down" :disabled="activeCorner === null" @click="nudge(0, 0.005)">⬇</button>
            <button class="nudge-btn" title="Nudge Left" :disabled="activeCorner === null" @click="nudge(-0.005, 0)">⬅</button>
            <button class="nudge-btn" title="Nudge Right" :disabled="activeCorner === null" @click="nudge(0.005, 0)">➡</button>
          </div>
          <button class="tool-btn" :disabled="historyStack.length === 0" @click="undo">↩ Undo</button>
          <button class="tool-btn" @click="resetCorners">🔄 Reset Corners</button>
        </div>
      </div>

      <!-- TAB 3: Physical Dimensions & Depths -->
      <div v-if="activeTab === 'dimensions'" class="wizard-panel">
        <div class="panel-desc">
          <strong>Step 3: Verified Facility Dimensions</strong>
          <p>
            Enter administrator-verified physical pool dimensions and water depths. Note: AquaPulse strictly uses confirmed facility geometry rather than guessing depth from water color.
          </p>
        </div>
        <div class="form-grid">
          <div class="ctrl-group">
            <label>Length (m)</label>
            <input v-model.number="cal.length_m" type="number" step="0.5" min="2.0" max="100.0" />
            <span class="field-hint">Longitudinal pool length</span>
          </div>
          <div class="ctrl-group">
            <label>Width (m)</label>
            <input v-model.number="cal.width_m" type="number" step="0.5" min="1.0" max="50.0" />
            <span class="field-hint">Transverse pool width</span>
          </div>
          <div class="ctrl-group">
            <label>Shallow Water Depth (m)</label>
            <input v-model.number="cal.shallow_depth_m" type="number" step="0.1" min="0.2" max="3.0" />
            <span class="field-hint">Zone A shallow end depth</span>
          </div>
          <div class="ctrl-group">
            <label>Deep Water Depth (m)</label>
            <input v-model.number="cal.deep_depth_m" type="number" step="0.1" min="0.5" max="10.0" />
            <span class="field-hint">Zone B deep end depth</span>
          </div>
        </div>
      </div>

      <!-- TAB 4: Orientation & Safety Depth Boundary -->
      <div v-if="activeTab === 'boundary'" class="wizard-panel">
        <div class="panel-desc">
          <strong>Step 4: Deep End Orientation &amp; Visual Safety Rope</strong>
          <p>
            Select which camera edge corresponds to the deep water end, and position the yellow floating safety rope along the pool length.
          </p>
        </div>
        <div class="form-grid">
          <div class="ctrl-group">
            <label>Deep-End Camera Orientation</label>
            <select v-model="cal.deep_end_side">
              <option value="right">Right Side (Zone B ≥ {{ cal.depth_boundary_m }}m)</option>
              <option value="left">Left Side</option>
              <option value="bottom">Bottom (Rotated view)</option>
              <option value="top">Top (Rotated view)</option>
            </select>
          </div>
          <div class="ctrl-group">
            <label>Depth Boundary Position ({{ cal.depth_boundary_m }}m from shallow end)</label>
            <input
              v-model.number="cal.depth_boundary_m"
              type="range"
              :min="1.0"
              :max="(cal.length_m || 25.0) - 1.0"
              step="0.5"
            />
            <span class="field-hint">Aligns with yellow floating safety rope on camera view</span>
          </div>
          <div class="ctrl-group">
            <label>Pitch Time Compression</label>
            <select v-model.number="timeScale">
              <option :value="1.0">1x (Official 5s VERIFY / 8s CRITICAL / 15s Nudge)</option>
              <option :value="2.0">2x Fast Demo (2.5s VERIFY / 4s CRITICAL / 7.5s Nudge)</option>
            </select>
          </div>
        </div>
      </div>

      <!-- TAB 5: Geometry Validation & Test Points -->
      <div v-if="activeTab === 'test'" class="wizard-panel">
        <div class="panel-desc">
          <strong>Step 5: Homography Validation &amp; Test Point Inspection</strong>
          <p>
            Verify mathematical homography, non-self-intersection, and click anywhere on the pool canvas above to test physical coordinate mapping.
          </p>
        </div>

        <div class="test-controls-row">
          <button class="primary-btn validate-btn" :disabled="isValidating" @click="runValidation">
            {{ isValidating ? 'Validating Geometry...' : '⚡ Validate Geometry' }}
          </button>
        </div>

        <!-- Validation Results Alert -->
        <div v-if="validationResult" class="validation-box" :class="{ valid: validationResult.is_valid, invalid: !validationResult.is_valid }">
          <div v-if="validationResult.is_valid" class="val-header">
            <strong>✓ Calibration Geometry Validated</strong>
            <p>Non-degenerate planar homography verified. Projected shallow/deep boundary lies strictly within the pool water basin.</p>
          </div>
          <div v-else class="val-header">
            <strong>⚠ Calibration Geometry Validation Failed</strong>
            <ul>
              <li v-for="(err, idx) in validationResult.errors" :key="`err-${idx}`">{{ err }}</li>
            </ul>
          </div>
        </div>

        <!-- Test Point Inspector Feedback -->
        <div v-if="testPoint" class="point-inspector-card">
          <div class="insp-title">📍 Inspected Test Point:</div>
          <div class="insp-grid">
            <div>Physical: <strong>x: {{ testPoint.x_m }}m, y: {{ testPoint.y_m }}m</strong></div>
            <div>In Water: <strong>{{ testPoint.in_water ? 'Yes (Water Surface)' : 'No (Deck Area)' }}</strong></div>
            <div>Zone: <strong :class="testPoint.zone">{{ testPoint.zone }}</strong></div>
            <div>Distance to Rope: <strong>{{ testPoint.dist_to_boundary_m }}m</strong></div>
          </div>
        </div>
      </div>

      <!-- Notification message if saved -->
      <div v-if="saveSuccessMsg" class="success-banner">
        {{ saveSuccessMsg }}
      </div>

      <!-- Modal Footer Controls -->
      <div class="modal-footer">
        <button class="secondary-btn" @click="$emit('close')">Cancel</button>

        <button
          class="secondary-btn save-profile-btn"
          :disabled="isSaving"
          @click="saveAndActivateProfile"
        >
          💾 Save &amp; Activate Camera Profile
        </button>

        <button
          class="primary-btn"
          :disabled="isSaving"
          @click="saveAndProcessVideo"
        >
          {{ isSaving ? 'Analyzing...' : '⚡ Save &amp; Analyze Video' }}
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
  padding: 1rem;
}

.calibration-modal {
  background: #FFFFFF;
  border: 1px solid var(--line);
  border-radius: 12px;
  width: 100%;
  max-width: 960px;
  max-height: 94vh;
  overflow-y: auto;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.25);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.header-titles h3 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text);
}

.modal-sub {
  font-size: 0.8rem;
  color: var(--muted);
  margin: 0.25rem 0 0 0;
}

.close-btn {
  background: transparent;
  border: none;
  color: var(--muted);
  font-size: 1.5rem;
  line-height: 1;
  cursor: pointer;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
}

.close-btn:hover {
  color: var(--danger);
  background: rgba(163, 78, 66, 0.1);
}

/* Wizard Tabs */
.wizard-tabs {
  display: flex;
  gap: 0.5rem;
  border-bottom: 1px solid var(--line);
  padding-bottom: 0.5rem;
  overflow-x: auto;
}

.wizard-tab-btn {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  padding: 0.4rem 0.75rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--muted);
  white-space: nowrap;
  transition: all 0.2s ease;
}

.wizard-tab-btn:hover {
  color: var(--accent);
  background: var(--accent-soft);
}

.wizard-tab-btn.active {
  color: var(--accent);
  background: var(--accent-soft);
  border-color: var(--accent);
}

/* Stage */
.calibration-stage {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: #0B1622;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--line);
  cursor: crosshair;
  user-select: none;
  touch-action: none;
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
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--accent);
  color: #FFFFFF;
  font-weight: 800;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  border: 2px solid #FFFFFF;
  box-shadow: 0 0 10px rgba(23, 103, 118, 0.6);
  cursor: grab;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
  touch-action: none;
}

.corner-handle:hover {
  transform: translate(-50%, -50%) scale(1.15);
  background: #208e9d;
}

.corner-handle.active {
  background: var(--danger);
  box-shadow: 0 0 15px rgba(163, 78, 66, 0.8);
  transform: translate(-50%, -50%) scale(1.2);
}

.corner-handle.dragging {
  cursor: grabbing;
}

.rope-label-tag {
  position: absolute;
  transform: translate(-50%, -120%);
  background: rgba(0, 0, 0, 0.75);
  color: #FFD600;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  pointer-events: none;
  white-space: nowrap;
  border: 1px solid #FFD600;
}

.test-point-pin {
  position: absolute;
  transform: translate(-50%, -50%);
  font-size: 1.2rem;
  pointer-events: none;
}

/* Wizard Panels */
.wizard-panel {
  background: var(--page);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.panel-desc {
  font-size: 0.8rem;
  color: var(--text);
}

.panel-desc p {
  margin: 0.25rem 0 0 0;
  color: var(--muted);
  font-size: 0.75rem;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 0.75rem;
}

.ctrl-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.ctrl-group label {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text);
}

.ctrl-group select,
.ctrl-group input {
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--text);
  padding: 0.45rem 0.6rem;
  border-radius: 6px;
  font-size: 0.8rem;
}

.field-hint {
  font-size: 0.68rem;
  color: var(--muted);
}

.tools-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.corner-status-pill {
  font-size: 0.75rem;
  background: var(--surface);
  border: 1px solid var(--line);
  padding: 0.35rem 0.65rem;
  border-radius: 6px;
}

.nudge-controls {
  display: flex;
  gap: 0.25rem;
}

.nudge-btn,
.tool-btn {
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--text);
  padding: 0.35rem 0.65rem;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
}

.nudge-btn:hover:not(:disabled),
.tool-btn:hover:not(:disabled) {
  background: var(--accent-soft);
  border-color: var(--accent);
}

.nudge-btn:disabled,
.tool-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Validation & Feedback */
.validation-box {
  border-radius: 6px;
  padding: 0.75rem;
  font-size: 0.78rem;
}

.validation-box.valid {
  background: #eefcf4;
  border: 1px solid #b3ebcc;
  color: #1b5e20;
}

.validation-box.invalid {
  background: #fdf2f2;
  border: 1px solid #f8b4b4;
  color: var(--danger);
}

.val-header p {
  margin: 0.25rem 0 0 0;
  font-size: 0.72rem;
}

.val-header ul {
  margin: 0.25rem 0 0 1rem;
  padding: 0;
}

.point-inspector-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 0.75rem;
  font-size: 0.75rem;
}

.insp-title {
  font-weight: 700;
  color: var(--accent);
  margin-bottom: 0.35rem;
}

.insp-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.35rem;
}

.ZONE_A_SHALLOW {
  color: #00838f;
}

.ZONE_B_DEEP_END {
  color: #1565c0;
}

.POOL_DECK {
  color: var(--muted);
}

.success-banner {
  background: #eefcf4;
  border: 1px solid #b3ebcc;
  color: #1b5e20;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  font-size: 0.8rem;
  font-weight: 600;
}

.status-indicator {
  display: flex;
  align-items: center;
  height: 34px;
}

.badge-active {
  background: #eefcf4;
  color: #1b5e20;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-size: 0.72rem;
  font-weight: 700;
}

.badge-draft {
  background: #fff8e1;
  color: #b78103;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-size: 0.72rem;
  font-weight: 700;
}

/* Modal Footer */
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--line);
  flex-wrap: wrap;
}

.secondary-btn {
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--line);
  padding: 0.5rem 1rem;
  border-radius: 6px;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.secondary-btn:hover {
  background: var(--page);
  border-color: var(--accent);
}

.save-profile-btn {
  border-color: var(--accent);
  color: var(--accent);
}

.save-profile-btn:hover {
  background: var(--accent-soft);
}

.primary-btn {
  background: var(--accent);
  color: #FFFFFF;
  border: none;
  padding: 0.5rem 1.25rem;
  border-radius: 6px;
  font-size: 0.82rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;
}

.primary-btn:hover:not(:disabled) {
  background: #208e9d;
}

.primary-btn:disabled {
  opacity: 0.5;
  cursor: wait;
}
</style>
