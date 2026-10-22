<script setup lang="ts">
import { computed } from 'vue'
import { useAquaStore } from '../store'
import { useTimelineSync } from '../composables/useTimelineSync'
import type { SwimmerTrack } from '../types/aquapulse'

const store = useAquaStore()
const framesRef = computed(() => store.frames)
const playheadRef = computed(() => store.playheadSec)
const { currentFrame, interpolatedTracks } = useTimelineSync(framesRef, playheadRef)

const poolWidthM = 25.0
const poolHeightM = 12.0

// Map physical pool meters (0..25m, 0..12m) to SVG viewBox coordinates (width=500, height=240)
const svgW = 500
const svgH = 240
const scale = svgW / poolWidthM // 20 px per meter

function toSvgX(x_m: number): number {
  return Math.max(0, Math.min(svgW, x_m * scale))
}

function toSvgY(y_m: number): number {
  return Math.max(0, Math.min(svgH, y_m * scale))
}

function trackColor(tr: SwimmerTrack): string {
  if (tr.is_flailing || tr.is_submerged) return '#A34E42'
  if (tr.near_deep_boundary) return '#B1782A'
  if (tr.suspected_violation !== 'NONE') return '#A56535'
  if (tr.role === 'TODDLER') return '#E040FB'
  if (tr.role === 'LAP_SWIMMER') return '#00E676'
  return '#176776'
}

// Pairwise distances for toddlers to nearest adults
const supervisionPairs = computed(() => {
  const tracks = interpolatedTracks.value
  const pairs: { toddler: SwimmerTrack; adult: SwimmerTrack; distM: number }[] = []

  const toddlers = tracks.filter(t => t.role === 'TODDLER')
  const adults = tracks.filter(t => t.role === 'ADULT' || t.role === 'LAP_SWIMMER')

  for (const tod of toddlers) {
    let nearestAdult: SwimmerTrack | null = null
    let minDist = 999.0
    for (const ad of adults) {
      const d = Math.hypot(tod.pool_coords_m[0] - ad.pool_coords_m[0], tod.pool_coords_m[1] - ad.pool_coords_m[1])
      if (d < minDist) {
        minDist = d
        nearestAdult = ad
      }
    }
    if (nearestAdult && minDist <= 5.0) {
      pairs.push({ toddler: tod, adult: nearestAdult, distM: Math.round(minDist * 10) / 10 })
    }
  }
  return pairs
})
</script>

<template>
  <div class="pool-map-card">
    <div class="map-header">
      <h4>🧭 25m × 12m Architectural Pool Zone Map</h4>
      <span class="map-sub">Physical Cartesian Coordinates &amp; 1.5m Supervision Rings</span>
    </div>

    <svg :viewBox="`0 0 ${svgW} ${svgH}`" class="pool-svg" preserveAspectRatio="xMidYMid meet">
      <!-- Zone A Shallow Basin (0m to 12.5m) -->
      <rect x="0" y="0" :width="svgW / 2" :height="svgH" fill="#142738" stroke="#1B354C" stroke-width="2" />
      <!-- Zone B Deep End Basin (12.5m to 25m) -->
      <rect :x="svgW / 2" y="0" :width="svgW / 2" :height="svgH" fill="#0E1D2B" stroke="#1B354C" stroke-width="2" />

      <!-- Lane dividers -->
      <line x1="0" :y1="svgH * 0.25" :x2="svgW" :y2="svgH * 0.25" stroke="#1E3E59" stroke-dasharray="4,4" />
      <line x1="0" :y1="svgH * 0.5" :x2="svgW" :y2="svgH * 0.5" stroke="#1E3E59" stroke-dasharray="4,4" />
      <line x1="0" :y1="svgH * 0.75" :x2="svgW" :y2="svgH * 0.75" stroke="#1E3E59" stroke-dasharray="4,4" />

      <!-- 12.5m Deep-End Transition Boundary -->
      <line :x1="svgW / 2" y1="0" :x2="svgW / 2" :y2="svgH" stroke="#176776" stroke-width="2.5" stroke-dasharray="6,4" />

      <!-- Zone labels -->
      <text x="14" y="24" fill="#94A3B8" font-size="11" font-weight="600" font-family="Outfit, sans-serif">
        ZONE A: SHALLOW (0.8m)
      </text>
      <text :x="svgW / 2 + 14" y="24" fill="#64FFDA" font-size="11" font-weight="600" font-family="Outfit, sans-serif">
        ZONE B: DEEP END (1.8m)
      </text>

      <!-- 1.5m Supervision Boundary line near Deep End -->
      <line :x1="svgW / 2 - 1.5 * scale" y1="0" :x2="svgW / 2 - 1.5 * scale" :y2="svgH" stroke="#B1782A" stroke-width="1.5" stroke-dasharray="3,3" opacity="0.6" />
      <text :x="svgW / 2 - 1.5 * scale - 6" y="svgH - 10" text-anchor="end" fill="#B1782A" font-size="9" opacity="0.8">1.5m Boundary</text>

      <!-- Adult-Toddler supervision lines -->
      <g v-for="(pair, idx) in supervisionPairs" :key="`pair-${idx}`">
        <line
          :x1="toSvgX(pair.toddler.pool_coords_m[0])"
          :y1="toSvgY(pair.toddler.pool_coords_m[1])"
          :x2="toSvgX(pair.adult.pool_coords_m[0])"
          :y2="toSvgY(pair.adult.pool_coords_m[1])"
          :stroke="pair.distM <= 1.5 ? '#00E676' : '#A34E42'"
          stroke-width="1.5"
          stroke-dasharray="3,2"
        />
        <text
          :x="(toSvgX(pair.toddler.pool_coords_m[0]) + toSvgX(pair.adult.pool_coords_m[0])) / 2"
          :y="(toSvgY(pair.toddler.pool_coords_m[1]) + toSvgY(pair.adult.pool_coords_m[1])) / 2 - 4"
          fill="#FFFFFF"
          font-size="9"
          font-weight="600"
          text-anchor="middle"
        >
          {{ pair.distM }}m
        </text>
      </g>

      <!-- Swimmer Track Positions & 1.5m Rings -->
      <g v-for="track in interpolatedTracks" :key="`track-dot-${track.track_id}`">
        <!-- 1.5m supervision radius ring around toddlers -->
        <circle
          v-if="track.role === 'TODDLER'"
          :cx="toSvgX(track.pool_coords_m[0])"
          :cy="toSvgY(track.pool_coords_m[1])"
          :r="1.5 * scale"
          fill="rgba(224, 64, 251, 0.15)"
          stroke="#E040FB"
          stroke-width="1.5"
          stroke-dasharray="4,2"
        />

        <!-- Main swimmer marker -->
        <circle
          :cx="toSvgX(track.pool_coords_m[0])"
          :cy="toSvgY(track.pool_coords_m[1])"
          :r="track.role === 'TODDLER' ? 7 : 9"
          :fill="trackColor(track)"
          stroke="#F5F8F9"
          stroke-width="2"
        />

        <!-- Track ID badge -->
        <text
          :x="toSvgX(track.pool_coords_m[0])"
          :y="toSvgY(track.pool_coords_m[1]) + 3"
          text-anchor="middle"
          fill="#F5F8F9"
          font-size="9"
          font-weight="700"
        >
          {{ track.track_id }}
        </text>
      </g>

      <!-- Detected Objects (Food/Pet) -->
      <g v-for="(obj, oIdx) in currentFrame?.objects || []" :key="`obj-${oIdx}`">
        <text
          :x="obj.zone === 'ZONE_B_DEEP_END' ? svgW * 0.75 : svgW * 0.25"
          :y="obj.zone === 'POOL_DECK' ? 15 : svgH * 0.65"
          font-size="14"
        >
          {{ obj.label === 'dog' ? '🐕' : obj.label === 'cat' ? '🐈' : '🥤' }}
        </text>
      </g>
    </svg>
  </div>
</template>

<style scoped>
.pool-map-card {
  background: rgba(15, 26, 36, 0.85);
  border: 1px solid rgba(51, 78, 104, 0.4);
  border-radius: 10px;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  backdrop-filter: blur(8px);
}

.map-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.map-header h4 {
  margin: 0;
  font-size: 0.95rem;
  color: #FFFFFF;
}

.map-legend {
  display: flex;
  gap: 0.75rem;
  font-size: 0.7rem;
  color: #5F737A;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.legend-dot.shallow { background: #176776; }
.legend-dot.toddler { background: #E040FB; }
.legend-dot.distress { background: #A34E42; }

.pool-map-svg {
  width: 100%;
  height: auto;
  border-radius: 6px;
  border: 1px solid rgba(51, 78, 104, 0.5);
  background: #F5F8F9;
}
</style>
