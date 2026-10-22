<script setup lang="ts">
import { ref } from 'vue'
import { useAquaStore } from '../store'

const emit = defineEmits<{ calibrate: [jobId: string] }>()

const store = useAquaStore()
const fileInput = ref<HTMLInputElement | null>(null)
const isUploading = ref(false)

async function onFileSelected(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  isUploading.value = true
  try {
    const job = await store.uploadVideo(file)
    emit('calibrate', job.id)
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
            <span class="status-chip" :class="job.status">{{ job.status }}</span>
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
  color: #00E5FF;
  font-size: 0.78rem;
  font-weight: 700;
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.upload-btn:hover:not(:disabled) {
  background: #00E5FF;
  color: #081018;
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
  color: #00E5FF;
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
  background: #00E5FF;
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
  border-color: #00E5FF;
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
  color: #829AB1;
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
  color: #00FF66;
}

.status-chip.processing {
  background: rgba(0, 229, 255, 0.15);
  color: #00E5FF;
}

.status-chip.uploaded {
  background: rgba(255, 234, 0, 0.15);
  color: #FFEA00;
}

.status-chip.failed {
  background: rgba(255, 23, 68, 0.15);
  color: #FF1744;
}

.vid-actions {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.action-btn {
  background: transparent;
  border: 1px solid rgba(51, 78, 104, 0.5);
  color: #CBD2D9;
  font-size: 0.7rem;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-btn:hover {
  color: #FFFFFF;
  border-color: #00E5FF;
}

.run-btn {
  background: #00E5FF;
  color: #081018;
  border-color: #00E5FF;
  font-weight: 700;
}

.run-btn:hover {
  background: #84FFFF;
}

.play-badge {
  background: rgba(0, 255, 102, 0.15);
  border-color: rgba(0, 255, 102, 0.4);
  color: #00FF66;
  font-weight: 600;
}

.del-btn:hover {
  color: #FF1744;
  border-color: #FF1744;
}

.empty-list {
  text-align: center;
  padding: 1.5rem 0.5rem;
  color: #829AB1;
}

.empty-list p {
  font-size: 0.82rem;
  margin-bottom: 0.25rem;
}

.empty-list small {
  font-size: 0.72rem;
  color: #627D98;
}
</style>
