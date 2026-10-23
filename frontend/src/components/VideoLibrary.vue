<script setup lang="ts">
import { ref } from 'vue'
import { useAquaStore } from '../store'

const emit = defineEmits<{ calibrate: [jobId: string] }>()

const store = useAquaStore()
const fileInput = ref<HTMLInputElement | null>(null)
const isUploading = ref(false)

function getCameraName(cid?: string | null): string {
  if (!cid) return 'Main Pool CCTV'
  const cam = store.cameras.find(c => c.id === cid)
  return cam ? cam.name : cid
}

async function onFileSelected(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  isUploading.value = true
  try {
    const job = await store.uploadVideo(file, store.selectedCameraId || undefined)
    // If camera already has active calibration, notify user
    if (job.calibration_profile_id) {
      // Already calibrated; ready to run or edit
    } else {
      emit('calibrate', job.id)
    }
  } catch (err: any) {
    alert(`Upload failed: ${err.message}`)
  } finally {
    isUploading.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}
</script>

<template>
  <div class="video-library-card">
    <div class="lib-top">
      <div class="lib-title-row">
        <h4>📁 Pool Video Footage Library</h4>
        <button class="icon-refresh-btn" title="Refresh Videos" @click="store.refreshVideos()">🔄</button>
      </div>

      <!-- Camera selection for automatic calibration reuse -->
      <div class="camera-picker-row">
        <label class="camera-picker-label">📹 Active Camera:</label>
        <select v-model="store.selectedCameraId" class="camera-select">
          <option v-for="cam in store.cameras" :key="cam.id" :value="cam.id">
            {{ cam.name }} {{ cam.active_calibration_version ? `(v${cam.active_calibration_version} Calibrated)` : '(Uncalibrated)' }}
          </option>
        </select>
      </div>

      <button class="upload-btn" :disabled="isUploading" @click="fileInput?.click()">
        {{ isUploading ? 'Uploading...' : '+ Upload Pool Video' }}
      </button>
      <input
        ref="fileInput"
        type="file"
        accept="video/mp4,video/quicktime,video/x-msvideo,video/x-matroska,video/webm"
        class="visually-hidden"
        @change="onFileSelected"
      />
    </div>

    <!-- Processing Progress Notification -->
    <div v-if="store.processingProgress" class="processing-banner">
      <div class="prog-top">
        <span>⚙️ {{ store.processingProgress.stage }}</span>
        <span>{{ Math.round(store.processingProgress.progress * 100) }}%</span>
      </div>
      <div class="prog-bar">
        <div class="prog-bar-fill" :style="{ width: `${store.processingProgress.progress * 100}%` }"></div>
      </div>
    </div>

    <!-- Video List -->
    <div class="video-list">
      <div
        v-for="job in store.videos"
        :key="job.id"
        class="video-row"
        :class="{ active: job.id === store.activeJobId }"
        @click="store.selectVideo(job.id)"
      >
        <div class="vid-info">
          <strong class="vid-title">{{ job.filename }}</strong>
          <div class="vid-meta">
            <span>{{ job.duration_sec }}s &bull; {{ job.fps.toFixed(0) }}fps</span>
            <span v-if="job.camera_id" class="cam-tag">
              📹 {{ getCameraName(job.camera_id) }} (v{{ job.calibration_version || 1 }})
            </span>
            <span class="status-chip" :class="job.status">
              {{ job.status === 'completed' ? '✓ Analyzed' : job.status === 'uploaded' ? 'Needs Analysis' : job.status }}
            </span>
          </div>
        </div>

        <div class="vid-actions" @click.stop>
          <!-- Run analysis directly without needing modal if already uploaded -->
          <button
            v-if="job.status === 'uploaded' || job.status === 'failed'"
            class="action-btn run-btn"
            title="Start YOLO26 Analysis & Detection"
            @click="store.processVideo(job.id)"
          >
            ⚡ Analyze
          </button>

          <button
            v-if="job.status === 'uploaded' || job.status === 'failed'"
            class="action-btn cal-btn"
            title="Calibrate Pool Geometry"
            @click="emit('calibrate', job.id)"
          >
            📐 Calibrate
          </button>

          <button
            v-if="job.status === 'completed'"
            class="action-btn play-badge"
            title="Active Clip"
            @click="store.selectVideo(job.id)"
          >
            {{ job.id === store.activeJobId ? '✓ Active' : '▶ Play' }}
          </button>

          <button
            v-if="job.status === 'completed'"
            class="action-btn run-btn-subtle"
            title="Re-run YOLO26 Detection & Tracking"
            @click="store.processVideo(job.id)"
          >
            ⚡ Re-analyze
          </button>

          <button
            v-if="job.status === 'completed'"
            class="action-btn re-btn"
            title="Recalibrate / Settings"
            @click="emit('calibrate', job.id)"
          >
            ⚙️ Setup
          </button>

          <button
            class="action-btn del-btn"
            title="Delete Video"
            @click="store.deleteVideo(job.id)"
          >
            🗑
          </button>
        </div>
      </div>

      <div v-if="!store.videos.length" class="empty-list">
        <p>No video clips uploaded yet.</p>
        <small>Upload a test clip to start evaluating drowning, toddler, cotton or pet scenarios.</small>
      </div>
    </div>
  </div>
</template>

<style scoped>
.video-library-card {
  background: rgba(15, 26, 36, 0.85);
  border: 1px solid rgba(51, 78, 104, 0.4);
  border-radius: 10px;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  backdrop-filter: blur(8px);
}

.lib-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.lib-title-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.lib-title-row h4 {
  margin: 0;
  font-size: 0.95rem;
  color: #FFFFFF;
}

.icon-refresh-btn {
  background: transparent;
  border: none;
  font-size: 0.85rem;
  cursor: pointer;
  padding: 0.2rem;
  opacity: 0.7;
}

.icon-refresh-btn:hover {
  opacity: 1.0;
}

.upload-btn {
  background: rgba(0, 229, 255, 0.15);
  border: 1px solid rgba(0, 229, 255, 0.4);
  color: #176776;
  font-size: 0.78rem;
  font-weight: 700;
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.upload-btn:hover:not(:disabled) {
  background: #176776;
  color: #F5F8F9;
}

.upload-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
}

/* Progress */
.camera-picker-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: rgba(23, 103, 118, 0.08);
  border: 1px solid var(--line);
  padding: 0.35rem 0.6rem;
  border-radius: 6px;
}

.camera-picker-label {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--accent);
  white-space: nowrap;
}

.camera-select {
  flex: 1;
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--text);
  font-size: 0.72rem;
  padding: 0.25rem 0.4rem;
  border-radius: 4px;
}

.cam-tag {
  background: rgba(23, 103, 118, 0.12);
  color: var(--accent);
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
  font-size: 0.68rem;
  font-weight: 600;
  white-space: nowrap;
}

.processing-banner {
  background: rgba(11, 22, 34, 0.8);
  border: 1px solid rgba(0, 229, 255, 0.3);
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.prog-top {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #176776;
  font-family: 'JetBrains Mono', monospace;
}

.prog-bar {
  width: 100%;
  height: 6px;
  background: rgba(30, 41, 59, 0.8);
  border-radius: 3px;
  overflow: hidden;
}

.prog-bar-fill {
  height: 100%;
  background: #176776;
  border-radius: 3px;
  transition: width 0.3s ease;
}

/* List */
.video-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 240px;
  overflow-y: auto;
}

.video-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(11, 22, 34, 0.6);
  border: 1px solid rgba(51, 78, 104, 0.3);
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.video-row:hover {
  background: rgba(0, 229, 255, 0.05);
  border-color: rgba(0, 229, 255, 0.3);
}

.video-row.active {
  background: rgba(0, 229, 255, 0.12);
  border-color: #176776;
  box-shadow: 0 0 8px rgba(0, 229, 255, 0.2);
}

.vid-info {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 0;
}

.vid-title {
  font-size: 0.82rem;
  color: #FFFFFF;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 220px;
}

.vid-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.7rem;
  color: #617981;
}

.status-chip {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.62rem;
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  text-transform: uppercase;
  font-weight: 600;
}

.status-chip.completed {
  background: rgba(0, 255, 102, 0.15);
  color: #397A68;
}

.status-chip.processing {
  background: rgba(0, 229, 255, 0.15);
  color: #176776;
}

.status-chip.uploaded {
  background: rgba(255, 234, 0, 0.15);
  color: #B1782A;
}

.status-chip.failed {
  background: rgba(255, 23, 68, 0.15);
  color: #A34E42;
}

.vid-actions {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.action-btn {
  background: transparent;
  border: 1px solid rgba(51, 78, 104, 0.5);
  color: #4B6269;
  font-size: 0.7rem;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-btn:hover {
  color: #FFFFFF;
  border-color: #176776;
}

.run-btn {
  background: #176776;
  color: #F5F8F9;
  border-color: #176776;
  font-weight: 700;
}

.run-btn:hover {
  background: #84FFFF;
}

.run-btn-subtle {
  background: transparent;
  color: #176776;
  border-color: #176776;
  font-weight: 600;
}

.run-btn-subtle:hover {
  background: #176776;
  color: #FFFFFF;
}

.play-badge {
  background: rgba(0, 255, 102, 0.15);
  border-color: rgba(0, 255, 102, 0.4);
  color: #397A68;
  font-weight: 600;
}

.del-btn:hover {
  color: #A34E42;
  border-color: #A34E42;
}

.empty-list {
  text-align: center;
  padding: 1.5rem 0.5rem;
  color: #617981;
}

.empty-list p {
  font-size: 0.82rem;
  margin-bottom: 0.25rem;
}

.empty-list small {
  font-size: 0.72rem;
  color: #72858B;
}
</style>
