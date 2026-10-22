<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { api } from '../api'
import { useAquaStore } from '../store'
import { useTimelineSync } from '../composables/useTimelineSync'
import type { Keypoint2D, SwimmerTrack } from '../types/aquapulse'

const store = useAquaStore()
const videoRef = ref<HTMLVideoElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const containerRef = ref<HTMLElement | null>(null)

const framesRef = computed(() => store.frames)
const playheadRef = computed(() => store.playheadSec)
const { currentFrame, interpolatedTracks } = useTimelineSync(framesRef, playheadRef)

const videoSrc = computed(() => {
  if (!store.activeJob || store.activeJob.status !== 'completed') return ''
  return api.mediaUrl(store.activeJob.id, 'masked.mp4')
})

const COCO_EDGES: [number, number][] = [
  [0, 1], [0, 2], [1, 3], [2, 4], // Head
  [5, 6], [5, 7], [7, 9], [6, 8], [8, 10], // Arms
  [5, 11], [6, 12], [11, 12], // Torso
  [11, 13], [13, 15], [12, 14], [14, 16], // Legs
]

let animationFrameId: number | null = null

function renderCanvas() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const width = canvas.width
  const height = canvas.height
  const isSilhouette = store.privacyMode === 'SILHOUETTE'

  ctx.clearRect(0, 0, width, height)

  if (isSilhouette) {
    // 1. Dark blueprint architectural background (#0B1622)
    ctx.fillStyle = '#0B1622'
    ctx.fillRect(0, 0, width, height)

    // 2. Pool basin: Zone A Shallow (#142738) & Zone B Deep End (#0E1D2B)
    const basinX1 = width * 0.06
    const basinX2 = width * 0.94
    const basinY1 = height * 0.16
    const basinY2 = height * 0.84
    const basinMidX = (basinX1 + basinX2) / 2

    // Zone A
    ctx.fillStyle = '#142738'
    ctx.fillRect(basinX1, basinY1, basinMidX - basinX1, basinY2 - basinY1)

    // Zone B
    ctx.fillStyle = '#0E1D2B'
    ctx.fillRect(basinMidX, basinY1, basinX2 - basinMidX, basinY2 - basinY1)

    // Architectural grid lines
    ctx.strokeStyle = '#1B354C'
    ctx.lineWidth = 1
    for (let gx = basinX1; gx <= basinX2; gx += (basinX2 - basinX1) / 12) {
      ctx.beginPath()
      ctx.moveTo(gx, basinY1)
      ctx.lineTo(gx, basinY2)
      ctx.stroke()
    }
    for (let gy = basinY1; gy <= basinY2; gy += (basinY2 - basinY1) / 5) {
      ctx.beginPath()
      ctx.moveTo(basinX1, gy)
      ctx.lineTo(basinX2, gy)
      ctx.stroke()
    }

    // Outer basin border & 12.5m Deep-End boundary line
    ctx.strokeStyle = '#327B91'
    ctx.lineWidth = 2
    ctx.strokeRect(basinX1, basinY1, basinX2 - basinX1, basinY2 - basinY1)

    ctx.strokeStyle = '#00E5FF'
    ctx.lineWidth = 2.5
    ctx.setLineDash([6, 4])
    ctx.beginPath()
    ctx.moveTo(basinMidX, basinY1)
    ctx.lineTo(basinMidX, basinY2)
    ctx.stroke()
    ctx.setLineDash([])

    // Watermark & zone headers
    ctx.fillStyle = '#64FFDA'
    ctx.font = '600 11px Outfit, sans-serif'
    ctx.fillText('PDPA TIER-2 SKELETAL SILHOUETTE SHIELD (0% RAW BIOMETRIC PIXELS)', basinX1 + 4, basinY1 - 8)

    ctx.fillStyle = '#94A3B8'
    ctx.font = '500 10px JetBrains Mono, monospace'
    ctx.fillText('ZONE A: SHALLOW (0.8m)', basinX1 + 8, basinY1 + 18)
    ctx.fillText('ZONE B: DEEP END (1.8m)', basinMidX + 8, basinY1 + 18)
  }

  // 3. Render Swimmer Tracks
  const tracks = interpolatedTracks.value
  const scaleX = width / 640.0
  const scaleY = height / 360.0

  for (const track of tracks) {
    drawSwimmer(ctx, track, scaleX, scaleY, isSilhouette)
  }

  // Loop requestAnimationFrame for smooth 60fps interpolation while playing
  if (store.isPlaying) {
    animationFrameId = requestAnimationFrame(renderCanvas)
  }
}

function drawSwimmer(
  ctx: CanvasRenderingContext2D,
  track: SwimmerTrack,
  scaleX: number,
  scaleY: number,
  isSilhouette: boolean
) {
  // Determine color based on distress and role
  let neonColor = '#00E5FF' // default active swimmer
  if (track.is_flailing || track.is_submerged) {
    neonColor = '#FF1744' // red distress
  } else if (track.near_deep_boundary) {
    neonColor = '#FFEA00' // yellow caution
  } else if (track.suspected_violation !== 'NONE') {
    neonColor = '#FF9100' // orange violation
  } else if (track.role === 'TODDLER') {
    neonColor = '#E040FB' // purple toddler
  } else if (track.role === 'LAP_SWIMMER') {
    neonColor = '#00E676' // green lap swimmer
  }

  const kps = track.keypoints

  if (kps && kps.length >= 17) {
    // 1. Draw neon skeleton limb vectors
    ctx.strokeStyle = neonColor
    ctx.lineWidth = isSilhouette ? 3 : 2
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'

    for (const [i, j] of COCO_EDGES) {
      const p1 = kps[i]
      const p2 = kps[j]
      if (p1 && p2 && p1.conf > 0.15 && p2.conf > 0.15) {
        ctx.beginPath()
        ctx.moveTo(p1.x * scaleX, p1.y * scaleY)
        ctx.lineTo(p2.x * scaleX, p2.y * scaleY)
        ctx.stroke()
      }
    }

    // 2. Draw joints (keypoints 5..16)
    ctx.fillStyle = '#FFFFFF'
    for (let idx = 5; idx < 17; idx++) {
      const kp = kps[idx]
      if (kp && kp.conf > 0.15) {
        ctx.beginPath()
        ctx.arc(kp.x * scaleX, kp.y * scaleY, isSilhouette ? 3.5 : 2.5, 0, Math.PI * 2)
        ctx.fill()
      }
    }

    // 3. Anonymized head ring
    const nose = kps[0]
    if (nose && nose.conf > 0.15) {
      ctx.strokeStyle = neonColor
      ctx.lineWidth = 2.5
      ctx.beginPath()
      const radius = track.role === 'TODDLER' ? 6.5 * scaleX : 9.5 * scaleX
      ctx.arc(nose.x * scaleX, (nose.y - 2) * scaleY, radius, 0, Math.PI * 2)
      ctx.stroke()
    }
  } else {
    // Fallback bounding box & stick figure
    const [bx1, by1, bx2, by2] = track.bbox
    ctx.strokeStyle = neonColor
    ctx.lineWidth = 2
    ctx.strokeRect(bx1 * scaleX, by1 * scaleY, (bx2 - bx1) * scaleX, (by2 - by1) * scaleY)
  }

  // 4. Track badge tag
  const [bx1, by1] = track.bbox
  const tagX = Math.max(10, bx1 * scaleX)
  const tagY = Math.max(22, by1 * scaleY - 8)

  let badgeText = `#${track.track_id} ${track.role}`
  if (track.is_flailing) badgeText += ' [FLAILING!]'
  else if (track.is_submerged) badgeText += ' [SUBMERGED!]'
  else if (track.near_deep_boundary) badgeText += ' [NEAR DEEP]'
  else if (track.suspected_violation !== 'NONE') badgeText += ` [${track.suspected_violation}]`

  ctx.fillStyle = 'rgba(11, 22, 34, 0.85)'
  ctx.font = '600 11px Outfit, sans-serif'
  const textWidth = ctx.measureText(badgeText).width
  ctx.fillRect(tagX - 4, tagY - 12, textWidth + 8, 16)

  ctx.fillStyle = neonColor
  ctx.fillText(badgeText, tagX, tagY)
}

function onVideoTimeUpdate() {
  if (videoRef.value) {
    store.playheadSec = videoRef.value.currentTime
  }
}

function onVideoEnded() {
  store.isPlaying = false
}

function togglePlay() {
  const vid = videoRef.value
  if (!vid) return
  if (store.isPlaying) {
    vid.pause()
    store.isPlaying = false
  } else {
    vid.play().catch(() => {})
    store.isPlaying = true
    renderCanvas()
  }
}

function onScrubberChange(e: Event) {
  const target = e.target as HTMLInputElement
  const newTime = parseFloat(target.value)
  store.seekTo(newTime)
  if (videoRef.value) {
    videoRef.value.currentTime = newTime
  }
  nextTick(renderCanvas)
}

function setSpeed(rate: number) {
  store.playbackRate = rate
  if (videoRef.value) {
    videoRef.value.playbackRate = rate
  }
}

watch(
  () => store.playheadSec,
  (t) => {
    if (videoRef.value && Math.abs(videoRef.value.currentTime - t) > 0.4) {
      videoRef.value.currentTime = t
    }
    renderCanvas()
  }
)

watch(() => store.privacyMode, () => nextTick(renderCanvas))
watch(() => store.activeJobId, () => nextTick(renderCanvas))
watch(() => store.isPlaying, (playing) => {
  if (playing) {
    renderCanvas()
  } else if (animationFrameId) {
    cancelAnimationFrame(animationFrameId)
  }
})

onMounted(() => {
  renderCanvas()
})

onUnmounted(() => {
  if (animationFrameId) cancelAnimationFrame(animationFrameId)
})
</script>

<template>
  <div ref="containerRef" class="privacy-viewer-card">
    <div class="viewer-topline">
      <div class="privacy-mode-toggle" role="group" aria-label="PDPA Privacy Mode Toggle">
        <button
          :class="{ active: store.privacyMode === 'SILHOUETTE' }"
          @click="store.setPrivacyMode('SILHOUETTE')"
          title="Tier-2 Neon Skeletal Vectors on Dark Blueprint Grid (0% Raw Camera Pixels)"
        >
          🛡️ Tier-2 Silhouette Shield
        </button>
        <button
          :class="{ active: store.privacyMode === 'TIER1_FACE_MASKED' }"
          @click="store.setPrivacyMode('TIER1_FACE_MASKED')"
          title="Tier-1 Face-Masked Video with Neon Skeleton Overlay"
        >
          👤 Tier-1 Face-Masked Video
        </button>
      </div>

      <div class="compliance-badge">
        <span class="compliance-dot"></span>
        <span>PDPA 2010 &amp; 2024 Compliant</span>
      </div>
    </div>

    <!-- Video + Canvas Stage -->
    <div class="stage-container">
      <video
        ref="videoRef"
        class="playback-video"
        :src="videoSrc"
        :style="{ opacity: store.privacyMode === 'TIER1_FACE_MASKED' ? 1.0 : 0.0 }"
        playsinline
        preload="auto"
        @timeupdate="onVideoTimeUpdate"
        @ended="onVideoEnded"
      ></video>

      <canvas
        ref="canvasRef"
        class="overlay-canvas"
        width="640"
        height="360"
      ></canvas>

      <div v-if="!store.activeJob || store.activeJob.status !== 'completed'" class="stage-placeholder">
        <div class="placeholder-content">
          <span class="placeholder-icon">
            {{ store.activeJob?.status === 'processing' ? '⚙️' : store.activeJob?.status === 'uploaded' ? '📹' : '🌊' }}
          </span>
          <h3>
            {{ store.activeJob?.status === 'processing' ? 'Vision AI Analysis in Progress...' : store.activeJob?.status === 'uploaded' ? `Clip Ready: ${store.activeJob.filename}` : 'No Video Loaded' }}
          </h3>
          <p>
            {{ store.activeJob?.status === 'processing' ? (store.processingProgress?.stage || 'Tracking pose keypoints, objects & agent states') : store.activeJob?.status === 'uploaded' ? 'Run YOLO26 neural inference to track swimmers, zone locations, and life safety timers.' : 'Upload a pool clip or choose a video from the library to begin' }}
          </p>

          <div v-if="store.activeJob?.status === 'uploaded'" class="placeholder-actions">
            <button class="primary-action-btn" @click="store.processVideo(store.activeJob.id)">
              ⚡ Run Vision AI Analysis Now
            </button>
          </div>

          <div v-if="store.activeJob?.status === 'processing'" class="placeholder-progress">
            <div class="prog-bar-track">
              <div class="prog-bar-fill" :style="{ width: `${(store.processingProgress?.progress || 0) * 100}%` }"></div>
            </div>
            <span class="prog-pct">{{ Math.round((store.processingProgress?.progress || 0) * 100) }}%</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Controls Bar -->
    <div class="viewer-controls">
      <button class="play-btn" :disabled="!store.activeJob || store.activeJob.status !== 'completed'" @click="togglePlay">
        {{ store.isPlaying ? '⏸ Pause' : '▶ Play' }}
      </button>

      <div class="time-display">
        <span>{{ store.playheadSec.toFixed(1) }}s</span>
        <span class="time-sep">/</span>
        <span>{{ (store.activeJob?.duration_sec || 0).toFixed(1) }}s</span>
      </div>

      <input
        type="range"
        class="scrubber"
        min="0"
        :max="store.activeJob?.duration_sec || 10"
        step="0.05"
        :value="store.playheadSec"
        :disabled="!store.activeJob || store.activeJob.status !== 'completed'"
        @input="onScrubberChange"
      />

      <div class="speed-selector">
        <button
          v-for="s in [0.5, 1.0, 1.5, 2.0]"
          :key="s"
          :class="{ active: store.playbackRate === s }"
          @click="setSpeed(s)"
        >
          {{ s }}x
        </button>
      </div>

      <button class="mute-btn" @click="store.isMuted = !store.isMuted">
        {{ store.isMuted ? '🔇 Muted' : '🔊 Audio On' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.privacy-viewer-card {
  background: rgba(15, 26, 36, 0.85);
  border: 1px solid rgba(51, 78, 104, 0.4);
  border-radius: 10px;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  backdrop-filter: blur(8px);
}

.viewer-topline {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.privacy-mode-toggle {
  display: flex;
  background: rgba(11, 22, 34, 0.8);
  border: 1px solid rgba(51, 78, 104, 0.4);
  border-radius: 6px;
  padding: 0.2rem;
  gap: 0.25rem;
}

.privacy-mode-toggle button {
  background: transparent;
  border: none;
  color: #9FB3C8;
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.35rem 0.65rem;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.privacy-mode-toggle button.active {
  background: rgba(0, 229, 255, 0.18);
  color: #00E5FF;
  box-shadow: 0 0 8px rgba(0, 229, 255, 0.2);
}

.compliance-badge {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  color: #00FF66;
  background: rgba(0, 255, 102, 0.1);
  padding: 0.25rem 0.6rem;
  border-radius: 4px;
}

.compliance-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #00FF66;
  box-shadow: 0 0 6px #00FF66;
}

.stage-container {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: #081018;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid rgba(51, 78, 104, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
}

.playback-video {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  transition: opacity 0.3s ease;
}

.overlay-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.stage-placeholder {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(8, 16, 24, 0.92);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 5;
}

.placeholder-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.6rem;
  text-align: center;
  max-width: 480px;
  padding: 1.5rem;
}

.placeholder-icon {
  font-size: 2.75rem;
}

.placeholder-content h3 {
  font-size: 1.25rem;
  font-weight: 700;
  color: #FFFFFF;
}

.placeholder-content p {
  font-size: 0.85rem;
  color: #9FB3C8;
  line-height: 1.45;
}

.placeholder-actions {
  display: flex;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.primary-action-btn {
  background: #00E5FF;
  color: #081018;
  border: none;
  font-size: 0.85rem;
  font-weight: 700;
  padding: 0.6rem 1.25rem;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 0 15px rgba(0, 229, 255, 0.4);
}

.primary-action-btn:hover {
  background: #84FFFF;
  transform: translateY(-1px);
}

.placeholder-progress {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.prog-bar-track {
  flex: 1;
  height: 8px;
  background: rgba(30, 41, 59, 0.8);
  border-radius: 4px;
  overflow: hidden;
}

.prog-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #00E5FF, #00FF66);
  border-radius: 4px;
  transition: width 0.3s ease;
}

.prog-pct {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  color: #00E5FF;
  font-weight: 700;
}

/* Controls */
.viewer-controls {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  background: rgba(11, 22, 34, 0.8);
  border: 1px solid rgba(51, 78, 104, 0.4);
  border-radius: 8px;
  padding: 0.5rem 0.75rem;
}

.play-btn {
  background: #00E5FF;
  color: #081018;
  border: none;
  font-size: 0.82rem;
  font-weight: 700;
  padding: 0.4rem 0.85rem;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.play-btn:hover:not(:disabled) {
  background: #84FFFF;
}

.play-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.time-display {
  display: flex;
  gap: 0.25rem;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.78rem;
  color: #FFFFFF;
}

.time-sep {
  color: #627D98;
}

.scrubber {
  flex: 1;
  accent-color: #00E5FF;
  cursor: pointer;
}

.speed-selector {
  display: flex;
  gap: 0.2rem;
  background: rgba(15, 26, 36, 0.6);
  padding: 0.15rem;
  border-radius: 4px;
}

.speed-selector button {
  background: transparent;
  border: none;
  color: #829AB1;
  font-size: 0.7rem;
  font-weight: 600;
  padding: 0.25rem 0.4rem;
  border-radius: 3px;
  cursor: pointer;
}

.speed-selector button.active {
  background: rgba(0, 229, 255, 0.2);
  color: #00E5FF;
}

.mute-btn {
  background: transparent;
  border: 1px solid rgba(51, 78, 104, 0.5);
  color: #9FB3C8;
  font-size: 0.72rem;
  padding: 0.35rem 0.6rem;
  border-radius: 4px;
  cursor: pointer;
}

.mute-btn:hover {
  color: #FFFFFF;
  border-color: #00E5FF;
}
</style>
