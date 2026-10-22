export type PoolZone = 'ZONE_A_SHALLOW' | 'ZONE_B_DEEP_END' | 'POOL_DECK'

export type SwimmerRole = 'ADULT' | 'TODDLER' | 'SENIOR' | 'LAP_SWIMMER'

export type PostureState =
  | 'ACTIVE_SWIM'
  | 'VERTICAL_TREADING'
  | 'ACTIVE_FLAILING'
  | 'HORIZONTAL_SUBMERGED'
  | 'DECK_STANDING'
  | 'DECK_LOUNGING'

export type AgentState =
  | 'NORMAL'
  | 'VERIFY'
  | 'CRITICAL_EMERGENCY'
  | 'NUDGE_REQUIRED'
  | 'ESCALATED_GUARD_TICKET'

export type ViolationType =
  | 'NONE'
  | 'COTTON_ATTIRE'
  | 'FOOD_DRINK_POOLSIDE'
  | 'SMOKING_VAPING'
  | 'PET_OR_STRAY_ANIMAL'

export type PrivacyMode = 'SILHOUETTE' | 'TIER1_FACE_MASKED'

export type ScenarioName =
  | 'NORMAL_LAP_AND_FAMILY'
  | 'SILENT_DROWNING_RESCUE'
  | 'UNACCOMPANIED_TODDLER_DEEP_END'
  | 'COTTON_TSHIRT_AND_FOOD_NUDGE'
  | 'PET_AND_STRAY_ANIMAL_POOL'
  | 'MONSOON_DEBRIS_AND_ALGAE'
  | 'PEAK_CROWD_SURGE_ECO_DRIVE'

export interface Keypoint2D {
  x: number
  y: number
  conf: number
}

export interface SwimmerTrack {
  track_id: number
  role: SwimmerRole
  zone: PoolZone
  posture: PostureState
  bbox: [number, number, number, number]
  pool_coords_m: [number, number]
  keypoints: Keypoint2D[]
  is_flailing: boolean
  is_submerged: boolean
  near_deep_boundary: boolean
  suspected_violation: ViolationType
}

export interface DetectedObject {
  label: string
  confidence: number
  bbox: [number, number, number, number]
  zone: PoolZone
}

export interface TrackTemporalState {
  track_id: number
  role: SwimmerRole
  zone: PoolZone
  submersion_sec: number
  is_flailing: boolean
  is_submerged: boolean
  unaccompanied_infant_sec: number
  violation_sec: number
  nearest_adult_m: number | null
  is_supervised: boolean
  violation_type: ViolationType
  system2_verified: boolean
  nudge_count: number
  agent_state: AgentState
}

export interface System1ReflexTrace {
  execution_latency_ms: number
  within_latency_budget: boolean
  overall_state: AgentState
  tracks_evaluated: number
  active_alerts: string[]
  track_states: TrackTemporalState[]
}

export interface System2InspectionResult {
  track_id?: number
  target_type: string
  tier1_face_redacted: boolean
  verified_violation: boolean
  violation_type: ViolationType
  confidence: number
  inspector_backend: string
  vlm_used: boolean
  visual_tool_steps: string[]
  reasoning_summary: string
  inspection_latency_ms: number
}

export interface ToolExecutionLog {
  timestamp: string
  tool_name: string
  system_path: string
  zone: PoolZone
  track_id?: number
  message: string
  audio_tts_text?: string
  guard_route_hint?: string
}

export interface WaterClarityReport {
  turbidity_score: number
  algae_green_index: number
  floating_debris_count: number
  status: 'CRYSTAL_CLEAR' | 'SLIGHT_TURBIDITY' | 'ALGAE_WARNING' | 'MONSOON_DEBRIS_ALERT'
  cleaner_ticket_opened: boolean
  recommended_action: string
}

export interface ESGPumpMetrics {
  bather_count: number
  cotton_violations: number
  food_drink_events: number
  animal_events: number
  contamination_score: number
  recommended_vfd_speed_pct: number
  flow_rate_m3h: number
  fixed_pump_kw: number
  vfd_pump_kw: number
  hourly_kwh_saved: number
  hourly_rm_saved: number
  hourly_co2_saved_kg: number
  projected_daily_turnovers: number
  turnover_floor_compliant: boolean
}

export interface ResidentComfortStatus {
  live_headcount: number
  crowd_level: 'QUIET' | 'MODERATE' | 'BUSY'
  lap_swimmers: number
  family_swimmers: number
  toddler_count: number
  senior_count: number
  water_clarity_label: string
  recommended_quiet_hours: string[]
  senior_toddler_safe_window: string
}

export interface PoolCalibration {
  pool_corners_norm: [number, number][]
  deep_end_side: 'left' | 'right' | 'top' | 'bottom'
  deck_margin_norm: number
}

export interface VideoJob {
  id: string
  filename: string
  raw_filepath: string
  status: 'uploaded' | 'processing' | 'completed' | 'failed'
  progress: number
  current_stage: string
  duration_sec: number
  fps: number
  width: number
  height: number
  calibration: PoolCalibration
  sample_fps: number
  time_scale: number
  role_overrides: Record<number, SwimmerRole>
  error?: string | null
  created_at: string
}

export interface TimelineFrame {
  t: number
  tracks: SwimmerTrack[]
  objects: DetectedObject[]
  system1_trace: System1ReflexTrace
  system2_inspections: System2InspectionResult[]
  tool_logs: ToolExecutionLog[]
  reasoning_thoughts: string[]
  esg_metrics: ESGPumpMetrics
  water_report?: WaterClarityReport | null
  resident_comfort: ResidentComfortStatus
  roi_images: Record<string, string>
  water_image?: string | null
}

export interface TimelineEvent {
  t: number
  kind: string
  system_path: string
  track_id?: number
  zone: string
  message: string
  audio_tts_text?: string
  guard_route_hint?: string
}

export interface TimelineSummary {
  duration_sec: number
  sampled_frames_count: number
  peak_bathers: number
  max_agent_state: string
  system1_p95_latency_ms: number
  projected_daily_rm_saved: number
  turnover_compliant: boolean
}

export interface TimelinePayload {
  job: VideoJob
  frames: TimelineFrame[]
  events: TimelineEvent[]
  summary: TimelineSummary
}

export interface SystemCapabilities {
  yolo26_pose_available: boolean
  gemini_api_configured: boolean
  audio_synthesis_available: boolean
  minimum_daily_turnover_floor: number
  tnb_tariff_rm_kwh: number
  pdpa_silhouettes_supported: boolean
}
