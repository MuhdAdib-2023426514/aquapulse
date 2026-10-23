import type {
  PoolCalibration,
  ScenarioName,
  SwimmerRole,
  SystemCapabilities,
  TimelinePayload,
  VideoJob,
} from './types/aquapulse'

const BASE_URL = ''

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (!(options.body instanceof FormData) && options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const response = await fetch(`${BASE_URL}${path}`, {
    cache: 'no-store',
    ...options,
    headers,
  })
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(errorBody.detail || `Request failed with status ${response.status}`)
  }
  return response.json()
}

export const api = {
  // Video Management & Processing
  async listVideos(): Promise<VideoJob[]> {
    return request<VideoJob[]>('/api/v1/videos')
  },

  async uploadVideo(file: File): Promise<VideoJob> {
    const form = new FormData()
    form.append('file', file)
    return request<VideoJob>('/api/v1/videos', { method: 'POST', body: form })
  },

  async getVideoJob(id: string): Promise<VideoJob> {
    return request<VideoJob>(`/api/v1/videos/${id}`)
  },

  async updateJobConfig(
    id: string,
    cfg: {
      calibration?: PoolCalibration
      sample_fps?: number
      time_scale?: number
      role_overrides?: Record<number, SwimmerRole>
    }
  ): Promise<VideoJob> {
    return request<VideoJob>(`/api/v1/videos/${id}/config`, {
      method: 'PUT',
      body: JSON.stringify(cfg),
    })
  },

  async processVideo(id: string): Promise<{ status: string; job_id: string }> {
    return request<{ status: string; job_id: string }>(`/api/v1/videos/${id}/process`, {
      method: 'POST',
    })
  },

  async reevaluateVideo(id: string): Promise<TimelinePayload> {
    return request<TimelinePayload>(`/api/v1/videos/${id}/reevaluate`, {
      method: 'POST',
    })
  },

  async getVideoTimeline(id: string): Promise<TimelinePayload> {
    return request<TimelinePayload>(`/api/v1/videos/${id}/timeline`)
  },

  async deleteVideo(id: string): Promise<{ status: string; job_id: string }> {
    return request<{ status: string; job_id: string }>(`/api/v1/videos/${id}`, {
      method: 'DELETE',
    })
  },

  mediaUrl(jobId: string, filePath: string): string {
    return `/api/v1/videos/${jobId}/media/${filePath}`
  },

  audioUrl(kind: 'critical_siren' | 'verify_beacon' | 'polite_nudge'): string {
    return `/api/v1/audio/${kind}.wav`
  },

  // Capabilities & ESG / Resident Endpoints
  async getCapabilities(): Promise<SystemCapabilities> {
    return request<SystemCapabilities>('/api/v1/system/capabilities')
  },

  async getEsgSummary(): Promise<any> {
    return request<any>('/api/v1/esg/summary')
  },

  async getResidentComfort(dayOfWeek: number = 5): Promise<any> {
    return request<any>(`/api/v1/resident/comfort?day_of_week=${dayOfWeek}`)
  },

  async getWaterInspect(): Promise<any> {
    return request<any>('/api/v1/water/inspect?scenario=MONSOON_DEBRIS_AND_ALGAE')
  },

  // Fallback Scenario Mode
  async stepScenario(
    scenario: ScenarioName,
    targetElapsedSec?: number,
    includeFrames: boolean = true
  ): Promise<any> {
    return request<any>('/api/v1/vision/step', {
      method: 'POST',
      body: JSON.stringify({
        scenario,
        target_elapsed_sec: targetElapsedSec,
        reset: targetElapsedSec === 0,
        include_frames: includeFrames,
      }),
    })
  },
}
