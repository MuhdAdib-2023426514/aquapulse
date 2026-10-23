import type {
  CalibrationProfile,
  CalibrationValidationResult,
  Camera,
  Pool,
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

  async uploadVideo(file: File, cameraId?: string): Promise<VideoJob> {
    const form = new FormData()
    form.append('file', file)
    if (cameraId) {
      form.append('camera_id', cameraId)
    }
    return request<VideoJob>('/api/v1/videos', { method: 'POST', body: form })
  },

  async getVideoJob(id: string): Promise<VideoJob> {
    return request<VideoJob>(`/api/v1/videos/${id}`)
  },

  async updateJobConfig(
    id: string,
    cfg: {
      calibration?: PoolCalibration
      camera_id?: string
      calibration_profile_id?: string
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

  // Pool & Camera Calibration Management
  async listPools(): Promise<Pool[]> {
    return request<Pool[]>('/api/v1/pools')
  },

  async createPool(pool: Partial<Pool>): Promise<Pool> {
    return request<Pool>('/api/v1/pools', {
      method: 'POST',
      body: JSON.stringify(pool),
    })
  },

  async getPool(id: string): Promise<Pool> {
    return request<Pool>(`/api/v1/pools/${id}`)
  },

  async listCameras(poolId?: string): Promise<Camera[]> {
    const q = poolId ? `?pool_id=${encodeURIComponent(poolId)}` : ''
    return request<Camera[]>(`/api/v1/cameras${q}`)
  },

  async createCamera(camera: Partial<Camera>): Promise<Camera> {
    return request<Camera>('/api/v1/cameras', {
      method: 'POST',
      body: JSON.stringify(camera),
    })
  },

  async getCamera(id: string): Promise<Camera> {
    return request<Camera>(`/api/v1/cameras/${id}`)
  },

  async listCalibrations(cameraId?: string, poolId?: string): Promise<CalibrationProfile[]> {
    const params = new URLSearchParams()
    if (cameraId) params.append('camera_id', cameraId)
    if (poolId) params.append('pool_id', poolId)
    const q = params.toString() ? `?${params.toString()}` : ''
    return request<CalibrationProfile[]>(`/api/v1/calibrations${q}`)
  },

  async createCalibration(cal: Partial<CalibrationProfile>): Promise<CalibrationProfile> {
    return request<CalibrationProfile>('/api/v1/calibrations', {
      method: 'POST',
      body: JSON.stringify(cal),
    })
  },

  async getCalibration(id: string): Promise<CalibrationProfile> {
    return request<CalibrationProfile>(`/api/v1/calibrations/${id}`)
  },

  async updateCalibration(id: string, updates: Partial<CalibrationProfile>): Promise<CalibrationProfile> {
    return request<CalibrationProfile>(`/api/v1/calibrations/${id}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    })
  },

  async validateCalibration(id: string): Promise<CalibrationValidationResult> {
    return request<CalibrationValidationResult>(`/api/v1/calibrations/${id}/validate`, {
      method: 'POST',
    })
  },

  async activateCalibration(id: string): Promise<CalibrationProfile> {
    return request<CalibrationProfile>(`/api/v1/calibrations/${id}/activate`, {
      method: 'POST',
    })
  },

  async createCalibrationVersion(id: string, updates?: Partial<CalibrationProfile>): Promise<CalibrationProfile> {
    return request<CalibrationProfile>(`/api/v1/calibrations/${id}/versions`, {
      method: 'POST',
      body: updates ? JSON.stringify(updates) : undefined,
    })
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
