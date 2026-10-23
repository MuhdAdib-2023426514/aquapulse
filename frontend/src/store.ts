import { defineStore } from 'pinia'
import { api } from './api'
import type {
  AgentState,
  PoolCalibration,
  PrivacyMode,
  ScenarioName,
  SwimmerRole,
  SystemCapabilities,
  TimelineFrame,
  TimelinePayload,
  VideoJob,
} from './types/aquapulse'

export const useAquaStore = defineStore('aquapulse', {
  state: () => ({
    videos: [] as VideoJob[],
    activeJobId: null as string | null,
    timeline: null as TimelinePayload | null,
    loadingTimeline: false,
    processingProgress: null as { stage: string; progress: number } | null,
    playheadSec: 0,
    isPlaying: false,
    playbackRate: 1.0,
    privacyMode: 'SILHOUETTE' as PrivacyMode,
    activeTab: 'vision' as 'vision' | 'esg' | 'water' | 'resident',
    mode: 'video' as 'video' | 'scenario',
    scenarioName: 'NORMAL_LAP_AND_FAMILY' as ScenarioName,
    scenarioData: null as any | null,
    scenarioElapsedSec: 0,
    scenarioLoading: false,
    capabilities: null as SystemCapabilities | null,
    isMuted: false,
    error: null as string | null,
  }),

  getters: {
    activeJob(state): VideoJob | null {
      return state.videos.find(v => v.id === state.activeJobId) || null
    },

    frames(state): TimelineFrame[] {
      return state.timeline?.frames || []
    },

    events(state) {
      return state.timeline?.events || []
    },

    summary(state) {
      return state.timeline?.summary || null
    },

    overallState(): AgentState {
      if (this.mode === 'scenario') {
        return (this.scenarioData?.system1_trace?.overall_state as AgentState) || 'NORMAL'
      }
      const cur = this.currentFrame
      return cur?.system1_trace?.overall_state || 'NORMAL'
    },

    currentFrame(state): TimelineFrame | null {
      const frames = state.timeline?.frames || []
      if (!frames.length) return null
      const t = state.playheadSec

      // Binary search for nearest frame at or before t
      let low = 0
      let high = frames.length - 1
      while (low <= high) {
        const mid = Math.floor((low + high) / 2)
        if (frames[mid].t <= t) {
          if (mid === frames.length - 1 || frames[mid + 1].t > t) {
            return frames[mid]
          }
          low = mid + 1
        } else {
          high = mid - 1
        }
      }
      return frames[Math.max(0, low)]
    },
  },

  actions: {
    async init() {
      try {
        const [caps, list] = await Promise.all([
          api.getCapabilities().catch(() => null),
          api.listVideos().catch(() => []),
        ])
        this.capabilities = caps
        this.videos = list
        if (list.length > 0 && !this.activeJobId) {
          await this.selectVideo(list[0].id)
        }
      } catch (e: any) {
        this.error = e.message || 'Initialization failed'
      }
    },

    async refreshVideos() {
      try {
        this.videos = await api.listVideos()
        if (this.activeJobId) {
          try {
            const freshJob = await api.getVideoJob(this.activeJobId)
            const idx = this.videos.findIndex(v => v.id === this.activeJobId)
            if (idx >= 0) this.videos[idx] = freshJob
            if (freshJob.status === 'completed') {
              await this.loadTimeline(this.activeJobId)
            }
          } catch {}
        }
      } catch {}
    },

    async selectVideo(id: string) {
      this.activeJobId = id
      this.playheadSec = 0
      this.isPlaying = false
      this.timeline = null
      this.error = null

      // Always refresh latest job info from server to ensure fresh status
      let targetJob = this.videos.find(v => v.id === id) || null
      try {
        const freshJob = await api.getVideoJob(id)
        const idx = this.videos.findIndex(v => v.id === id)
        if (idx >= 0) {
          this.videos[idx] = freshJob
        } else {
          this.videos.push(freshJob)
        }
        targetJob = freshJob
      } catch {}

      if (targetJob?.status === 'completed') {
        await this.loadTimeline(id)
      }
    },

    async loadTimeline(id: string) {
      this.loadingTimeline = true
      try {
        this.timeline = await api.getVideoTimeline(id)
        this.playheadSec = 0
      } catch (e: any) {
        this.error = e.message || 'Failed to load timeline'
      } finally {
        this.loadingTimeline = false
      }
    },

    async uploadVideo(file: File) {
      this.error = null
      try {
        const job = await api.uploadVideo(file)
        this.videos.unshift(job)
        this.activeJobId = job.id
        return job
      } catch (e: any) {
        this.error = e.message || 'Upload failed'
        throw e
      }
    },

    async saveConfig(
      id: string,
      cfg: {
        calibration?: PoolCalibration
        sample_fps?: number
        time_scale?: number
        role_overrides?: Record<number, SwimmerRole>
      }
    ) {
      try {
        const updated = await api.updateJobConfig(id, cfg)
        const idx = this.videos.findIndex(v => v.id === id)
        if (idx >= 0) this.videos[idx] = updated
        return updated
      } catch (e: any) {
        this.error = e.message || 'Config update failed'
        throw e
      }
    },

    async processVideo(id: string) {
      this.error = null
      try {
        await api.processVideo(id)
        this.pollProgress(id)
      } catch (e: any) {
        this.error = e.message || 'Failed to start processing'
      }
    },

    async pollProgress(id: string) {
      const interval = setInterval(async () => {
        try {
          const job = await api.getVideoJob(id)
          const idx = this.videos.findIndex(v => v.id === id)
          if (idx >= 0) this.videos[idx] = job

          if (job.status === 'processing') {
            this.processingProgress = {
              stage: job.current_stage,
              progress: job.progress,
            }
          } else if (job.status === 'completed') {
            clearInterval(interval)
            this.processingProgress = null
            if (this.activeJobId === id) {
              await this.loadTimeline(id)
            }
          } else if (job.status === 'failed') {
            clearInterval(interval)
            this.processingProgress = null
            this.error = job.error || 'Video processing failed'
          }
        } catch {
          clearInterval(interval)
          this.processingProgress = null
        }
      }, 1200)
    },

    async reevaluate(id: string) {
      this.loadingTimeline = true
      try {
        this.timeline = await api.reevaluateVideo(id)
      } catch (e: any) {
        this.error = e.message || 'Re-evaluation failed'
      } finally {
        this.loadingTimeline = false
      }
    },

    async deleteVideo(id: string) {
      try {
        await api.deleteVideo(id)
        this.videos = this.videos.filter(v => v.id !== id)
        if (this.activeJobId === id) {
          this.activeJobId = this.videos.length ? this.videos[0].id : null
          this.timeline = null
          if (this.activeJobId) await this.selectVideo(this.activeJobId)
        }
      } catch (e: any) {
        this.error = e.message || 'Delete failed'
      }
    },

    seekTo(sec: number) {
      this.playheadSec = Math.max(0, sec)
    },

    togglePlay() {
      this.isPlaying = !this.isPlaying
    },

    setPlaybackRate(rate: number) {
      this.playbackRate = rate
    },

    setPrivacyMode(mode: PrivacyMode) {
      this.privacyMode = mode
    },

    // Scenario Fallback Mode
    async stepScenario(scenario: ScenarioName, targetSec?: number) {
      this.scenarioLoading = true
      try {
        this.scenarioName = scenario
        const data = await api.stepScenario(scenario, targetSec, true)
        this.scenarioData = data
        this.scenarioElapsedSec = data.elapsed_sec
      } catch (e: any) {
        this.error = e.message || 'Scenario step failed'
      } finally {
        this.scenarioLoading = false
      }
    },
  },
})
