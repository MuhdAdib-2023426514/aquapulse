import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAquaStore } from './store'
import type { TimelineFrame, TimelinePayload } from './types/aquapulse'

describe('AquaPulse Store & Timeline Search', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('initializes with default values', () => {
    const store = useAquaStore()
    expect(store.activeTab).toBe('vision')
    expect(store.mode).toBe('video')
    expect(store.privacyMode).toBe('SILHOUETTE')
    expect(store.overallState).toBe('NORMAL')
  })

  it('performs binary search for current frame correctly', () => {
    const store = useAquaStore()

    const mockFrames: TimelineFrame[] = [
      {
        t: 0.0,
        tracks: [],
        objects: [],
        system1_trace: {
          execution_latency_ms: 12.0,
          within_latency_budget: true,
          overall_state: 'NORMAL',
          tracks_evaluated: 0,
          active_alerts: [],
          track_states: [],
        },
        system2_inspections: [],
        tool_logs: [],
        reasoning_thoughts: [],
        esg_metrics: {
          bather_count: 0,
          cotton_violations: 0,
          food_drink_events: 0,
          animal_events: 0,
          contamination_score: 0,
          recommended_vfd_speed_pct: 40,
          flow_rate_m3h: 28,
          fixed_pump_kw: 5.5,
          vfd_pump_kw: 0.352,
          hourly_kwh_saved: 5.148,
          hourly_rm_saved: 2.625,
          hourly_co2_saved_kg: 3.902,
          projected_daily_turnovers: 3.73,
          turnover_floor_compliant: true,
        },
        resident_comfort: {
          live_headcount: 0,
          crowd_level: 'QUIET',
          lap_swimmers: 0,
          family_swimmers: 0,
          toddler_count: 0,
          senior_count: 0,
          water_clarity_label: 'Crystal Clear',
          recommended_quiet_hours: [],
          senior_toddler_safe_window: '',
        },
        roi_images: {},
      },
      {
        t: 5.0,
        tracks: [],
        objects: [],
        system1_trace: {
          execution_latency_ms: 11.5,
          within_latency_budget: true,
          overall_state: 'VERIFY',
          tracks_evaluated: 1,
          active_alerts: ['Submersion timer 5.0s'],
          track_states: [],
        },
        system2_inspections: [],
        tool_logs: [],
        reasoning_thoughts: [],
        esg_metrics: {
          bather_count: 1,
          cotton_violations: 0,
          food_drink_events: 0,
          animal_events: 0,
          contamination_score: 1.0,
          recommended_vfd_speed_pct: 71.3,
          flow_rate_m3h: 49.9,
          fixed_pump_kw: 5.5,
          vfd_pump_kw: 1.99,
          hourly_kwh_saved: 3.51,
          hourly_rm_saved: 1.79,
          hourly_co2_saved_kg: 2.66,
          projected_daily_turnovers: 3.8,
          turnover_floor_compliant: true,
        },
        resident_comfort: {
          live_headcount: 1,
          crowd_level: 'QUIET',
          lap_swimmers: 1,
          family_swimmers: 0,
          toddler_count: 0,
          senior_count: 0,
          water_clarity_label: 'Crystal Clear',
          recommended_quiet_hours: [],
          senior_toddler_safe_window: '',
        },
        roi_images: {},
      },
      {
        t: 10.0,
        tracks: [],
        objects: [],
        system1_trace: {
          execution_latency_ms: 14.1,
          within_latency_budget: true,
          overall_state: 'CRITICAL_EMERGENCY',
          tracks_evaluated: 1,
          active_alerts: ['Submerged 10s confirmed'],
          track_states: [],
        },
        system2_inspections: [],
        tool_logs: [],
        reasoning_thoughts: [],
        esg_metrics: {
          bather_count: 1,
          cotton_violations: 0,
          food_drink_events: 0,
          animal_events: 0,
          contamination_score: 1.0,
          recommended_vfd_speed_pct: 71.3,
          flow_rate_m3h: 49.9,
          fixed_pump_kw: 5.5,
          vfd_pump_kw: 1.99,
          hourly_kwh_saved: 3.51,
          hourly_rm_saved: 1.79,
          hourly_co2_saved_kg: 2.66,
          projected_daily_turnovers: 3.8,
          turnover_floor_compliant: true,
        },
        resident_comfort: {
          live_headcount: 1,
          crowd_level: 'QUIET',
          lap_swimmers: 1,
          family_swimmers: 0,
          toddler_count: 0,
          senior_count: 0,
          water_clarity_label: 'Crystal Clear',
          recommended_quiet_hours: [],
          senior_toddler_safe_window: '',
        },
        roi_images: {},
      },
    ]

    store.timeline = {
      job: {
        id: 'test-job',
        filename: 'test.mp4',
        raw_filepath: 'raw.mp4',
        status: 'completed',
        progress: 100,
        current_stage: 'Completed',
        duration_sec: 15,
        fps: 30,
        width: 1280,
        height: 720,
        calibration: {
          pool_corners_norm: [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
          deep_end_side: 'right',
          deck_margin_norm: 0.05,
        },
        sample_fps: 5,
        time_scale: 1.0,
        role_overrides: {},
        created_at: '2026-10-22T00:00:00Z',
      },
      frames: mockFrames,
      events: [],
      summary: {
        duration_sec: 15,
        sampled_frames_count: 3,
        peak_bathers: 1,
        max_agent_state: 'CRITICAL_EMERGENCY',
        system1_p95_latency_ms: 13.0,
        projected_daily_rm_saved: 42.0,
        turnover_compliant: true,
      },
    }

    // At playhead 0.0s -> frame 0
    store.seekTo(0.0)
    expect(store.currentFrame?.t).toBe(0.0)
    expect(store.overallState).toBe('NORMAL')

    // At playhead 7.5s -> frame 1 (t=5.0)
    store.seekTo(7.5)
    expect(store.currentFrame?.t).toBe(5.0)
    expect(store.overallState).toBe('VERIFY')

    // At playhead 11.2s -> frame 2 (t=10.0)
    store.seekTo(11.2)
    expect(store.currentFrame?.t).toBe(10.0)
    expect(store.overallState).toBe('CRITICAL_EMERGENCY')
  })
})
