import { computed, type Ref } from 'vue'
import type { Keypoint2D, SwimmerTrack, TimelineFrame } from '../types/aquapulse'

export function useTimelineSync(
  framesRef: Ref<TimelineFrame[]>,
  playheadSec: Ref<number>
) {
  // Binary search for the frame at or immediately preceding playheadSec
  const frameIndex = computed(() => {
    const frames = framesRef.value
    if (!frames.length) return -1
    const t = playheadSec.value
    if (t <= frames[0].t) return 0
    if (t >= frames[frames.length - 1].t) return frames.length - 1

    let low = 0
    let high = frames.length - 1
    while (low <= high) {
      const mid = Math.floor((low + high) / 2)
      if (frames[mid].t <= t) {
        if (mid === frames.length - 1 || frames[mid + 1].t > t) {
          return mid
        }
        low = mid + 1
      } else {
        high = mid - 1
      }
    }
    return Math.max(0, low)
  })

  const currentFrame = computed<TimelineFrame | null>(() => {
    const idx = frameIndex.value
    if (idx < 0 || idx >= framesRef.value.length) return null
    return framesRef.value[idx]
  })

  const nextFrame = computed<TimelineFrame | null>(() => {
    const idx = frameIndex.value
    if (idx < 0 || idx + 1 >= framesRef.value.length) return null
    return framesRef.value[idx + 1]
  })

  // Interpolation factor between currentFrame and nextFrame (0.0 to 1.0)
  const alpha = computed(() => {
    const curr = currentFrame.value
    const next = nextFrame.value
    if (!curr || !next || next.t <= curr.t) return 0.0
    const val = (playheadSec.value - curr.t) / (next.t - curr.t)
    return Math.max(0.0, Math.min(1.0, val))
  })

  // Interpolated swimmer tracks with smooth keypoint and bbox positions
  const interpolatedTracks = computed<SwimmerTrack[]>(() => {
    const curr = currentFrame.value
    if (!curr) return []
    const next = nextFrame.value
    const a = alpha.value

    if (!next || a <= 0.01) return curr.tracks

    const nextTrackMap = new Map<number, SwimmerTrack>()
    for (const t of next.tracks) {
      nextTrackMap.set(t.track_id, t)
    }

    return curr.tracks.map(tCurr => {
      const tNext = nextTrackMap.get(tCurr.track_id)
      if (!tNext) return tCurr

      // Lerp bbox
      const lerpBbox: [number, number, number, number] = [
        Math.round(tCurr.bbox[0] + (tNext.bbox[0] - tCurr.bbox[0]) * a),
        Math.round(tCurr.bbox[1] + (tNext.bbox[1] - tCurr.bbox[1]) * a),
        Math.round(tCurr.bbox[2] + (tNext.bbox[2] - tCurr.bbox[2]) * a),
        Math.round(tCurr.bbox[3] + (tNext.bbox[3] - tCurr.bbox[3]) * a),
      ]

      // Lerp keypoints
      const lerpKps: Keypoint2D[] = tCurr.keypoints.map((kp, kIdx) => {
        const nextKp = tNext.keypoints[kIdx]
        if (!nextKp) return kp
        return {
          x: Math.round((kp.x + (nextKp.x - kp.x) * a) * 10) / 10,
          y: Math.round((kp.y + (nextKp.y - kp.y) * a) * 10) / 10,
          conf: Math.max(kp.conf, nextKp.conf),
        }
      })

      // Lerp pool coordinates
      const lerpPoolCoords: [number, number] = [
        Math.round((tCurr.pool_coords_m[0] + (tNext.pool_coords_m[0] - tCurr.pool_coords_m[0]) * a) * 100) / 100,
        Math.round((tCurr.pool_coords_m[1] + (tNext.pool_coords_m[1] - tCurr.pool_coords_m[1]) * a) * 100) / 100,
      ]

      return {
        ...tCurr,
        bbox: lerpBbox,
        keypoints: lerpKps,
        pool_coords_m: lerpPoolCoords,
      }
    })
  })

  return {
    frameIndex,
    currentFrame,
    nextFrame,
    alpha,
    interpolatedTracks,
  }
}
