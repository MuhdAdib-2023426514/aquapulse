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
  if (tr.is_flailing || tr.is_submerged) return '#EF4444'
  if (tr.near_deep_boundary) return '#F59E0B'
  if (tr.suspected_violation !== 'NONE') return '#F97316'
  if (tr.role === 'TODDLER') return '#E040FB'
  if (tr.role === 'LAP_SWIMMER') return '#10B981'
  return '#38BDF8'
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
      <div class="header-titles">
        <h4>🧭 25m × 12m Architectural Pool Zone Map</h4>
        <span class="map-sub">Physical Cartesian Coordinates &amp; Dynamic 1.5m Supervision Rings</span>
      </div>
    </div>

    <svg :viewBox="`0 0 ${svgW} ${svgH}`" class="pool-svg" preserveAspectRatio="xMidYMid meet">
      <defs>
        <!-- Amber hazard stripe pattern for toddler buffer zone -->
        <pattern id="hazardStripe" width="8" height="8" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
          <line x1="0" y1="0" x2="0" y2="8" stroke="#F59E0B" stroke-width="2.5" opacity="0.3" />
        </pattern>
      </defs>

      <!-- Zone A Shallow Basin (0m to 12.5m) -->
      <rect x="0" y="0" :width="svgW / 2" :height="svgH" fill="#0C1B2A" stroke="#1E3E59" stroke-width="2" />

      <!-- 1.5m Toddler Buffer Danger Zone (11.0m to 12.5m -> 220px to 250px) -->
      <rect
        :x="svgW / 2 - 1.5 * scale"
        y="0"
        :width="1.5 * scale"
        :height="svgH"
        fill="url(#hazardStripe)"
      />
      <rect
        :x="svgW / 2 - 1.5 * scale"
        y="0"
        :width="1.5 * scale"
        :height="svgH"
        fill="rgba(245, 158, 11, 0.12)"
      />

      <!-- Zone B Deep End Basin (12.5m to 25m) -->
      <rect :x="svgW / 2" y="0" :width="svgW / 2" :height="svgH" fill="#081422" stroke="#1E3E59" stroke-width="2" />

      <!-- Lane dividers -->
      <line x1="0" :y1="svgH * 0.25" :x2="svgW" :y2="svgH * 0.25" stroke="#162E44" stroke-dasharray="4,4" />
      <line x1="0" :y1="svgH * 0.5" :x2="svgW" :y2="svgH * 0.5" stroke="#162E44" stroke-dasharray="4,4" />
      <line x1="0" :y1="svgH * 0.75" :x2="svgW" :y2="svgH * 0.75" stroke="#162E44" stroke-dasharray="4,4" />

      <!-- 1.5m Boundary line near Deep End (Orange) -->
      <line
        :x1="svgW / 2 - 1.5 * scale"
        y1="0"
        :x2="svgW / 2 - 1.5 * scale"
        :y2="svgH"
        stroke="#F59E0B"
        stroke-width="2"
        stroke-dasharray="4,3"
      />

      <!-- 12.5m Deep-End Transition Boundary (Cyan) -->
      <line
        :x1="svgW / 2"
        y1="0"
        :x2="svgW / 2"
        :y2="svgH"
        stroke="#00E5FF"
        stroke-width="2.5"
        stroke-dasharray="6,4"
      />

      <!-- Zone A & B Labels -->
      <text x="14" y="24" fill="#94A3B8" font-size="11" font-weight="700" font-family="'Outfit', sans-serif">
        ZONE A: SHALLOW (0.8m)
      </text>
      <text :x="svgW / 2 + 14" y="24" fill="#00E5FF" font-size="11" font-weight="700" font-family="'Outfit', sans-serif">
        ZONE B: DEEP END (1.8m)
      </text>

      <!-- Clear Self-Explanatory Toddler Buffer Badge at Top of Corridor -->
      <g :transform="`translate(${svgW / 2 - (1.5 * scale) / 2}, 38)`">
        <rect
          x="-58"
          y="-12"
          width="116"
          height="18"
          rx="4"
          fill="rgba(15, 23, 42, 0.95)"
          stroke="#F59E0B"
          stroke-width="1.2"
        />
        <text
          x="0"
          y="1"
          text-anchor="middle"
          fill="#F59E0B"
          font-size="8"
          font-weight="700"
          font-family="'JetBrains Mono', monospace"
        >
          ⚠️ 1.5m TODDLER BUFFER
        </text>
      </g>

      <!-- Adult-Toddler supervision lines -->
      <g v-for="(pair, idx) in supervisionPairs" :key="`pair-${idx}`">
        <line
          :x1="toSvgX(pair.toddler.pool_coords_m[0])"
          :y1="toSvgY(pair.toddler.pool_coords_m[1])"
          :x2="toSvgX(pair.adult.pool_coords_m[0])"
          :y2="toSvgY(pair.adult.pool_coords_m[1])"
          :stroke="pair.distM <= 1.5 ? '#10B981' : '#EF4444'"
          stroke-width="2"
          stroke-dasharray="3,2"
        />
        <rect
          :x="(toSvgX(pair.toddler.pool_coords_m[0]) + toSvgX(pair.adult.pool_coords_m[0])) / 2 - 16"
          :y="(toSvgY(pair.toddler.pool_coords_m[1]) + toSvgY(pair.adult.pool_coords_m[1])) / 2 - 14"
          width="32"
          height="14"
          rx="3"
          fill="rgba(0,0,0,0.85)"
        />
        <text
          :x="(toSvgX(pair.toddler.pool_coords_m[0]) + toSvgX(pair.adult.pool_coords_m[0])) / 2"
          :y="(toSvgY(pair.toddler.pool_coords_m[1]) + toSvgY(pair.adult.pool_coords_m[1])) / 2 - 3"
          :fill="pair.distM <= 1.5 ? '#10B981' : '#EF4444'"
          font-size="9"
          font-weight="700"
          text-anchor="middle"
          font-family="'JetBrains Mono', monospace"
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
          stroke="#FFFFFF"
          stroke-width="2"
        />

        <!-- Track ID badge -->
        <text
          :x="toSvgX(track.pool_coords_m[0])"
          :y="toSvgY(track.pool_coords_m[1]) + 3"
          text-anchor="middle"
          fill="#FFFFFF"
          font-size="9"
          font-weight="800"
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

    <!-- Visual Self-Explanatory Legend -->
    <div class="map-legend">
      <div class="legend-item">
        <span class="legend-box shallow-box"></span>
        <span class="legend-text">Zone A Shallow (0.8m)</span>
      </div>
      <div class="legend-item">
        <span class="legend-box buffer-box"></span>
        <span class="legend-text highlight-buffer">⚠️ 1.5m Toddler Buffer Zone</span>
      </div>
      <div class="legend-item">
        <span class="legend-box deep-box"></span>
        <span class="legend-text">Zone B Deep End (1.8m)</span>
      </div>
      <div class="legend-item">
        <span class="legend-dot toddler-dot"></span>
        <span class="legend-text">Toddler (1.5m Ring)</span>
      </div>
      <div class="legend-item">
        <span class="legend-dot adult-dot"></span>
        <span class="legend-text">Adult / Lap</span>
      </div>
      <div class="legend-item">
        <span class="legend-dot distress-dot"></span>
        <span class="legend-text">Submerged / Distress</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pool-map-card {
  background: rgba(13, 23, 33, 0.95);
  border: 1px solid rgba(0, 229, 255, 0.3);
  border-radius: 10px;
  padding: 1.1rem;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  backdrop-filter: blur(8px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
}

.map-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(51, 78, 104, 0.3);
  padding-bottom: 0.5rem;
}

.header-titles h4 {
  margin: 0;
  font-size: 0.98rem;
  font-weight: 700;
  color: #FFFFFF;
}

.map-sub {
  font-size: 0.72rem;
  color: #94A3B8;
  font-family: 'JetBrains Mono', monospace;
}

.pool-svg {
  width: 100%;
  height: auto;
  border-radius: 8px;
  border: 1px solid rgba(0, 229, 255, 0.35);
  background: #08121D;
  box-shadow: inset 0 0 16px rgba(0, 0, 0, 0.6);
}

/* Legend Styling */
.map-legend {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.85rem 1.1rem;
  padding: 0.65rem 0.85rem;
  background: rgba(16, 28, 42, 0.8);
  border: 1px solid rgba(51, 78, 104, 0.45);
  border-radius: 8px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.legend-text {
  font-size: 0.74rem;
  color: #CBD5E1;
  font-weight: 500;
}

.highlight-buffer {
  color: #F59E0B;
  font-weight: 700;
}

.legend-box {
  width: 14px;
  height: 10px;
  border-radius: 2px;
}

.shallow-box {
  background: #0C1B2A;
  border: 1px solid #1E3E59;
}

.buffer-box {
  background: repeating-linear-gradient(
    45deg,
    rgba(245, 158, 11, 0.25),
    rgba(245, 158, 11, 0.25) 3px,
    rgba(245, 158, 11, 0.5) 3px,
    rgba(245, 158, 11, 0.5) 6px
  );
  border: 1px solid #F59E0B;
}

.deep-box {
  background: #081422;
  border: 1px solid #00E5FF;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 1.5px solid #FFFFFF;
}

.toddler-dot {
  background: #E040FB;
}

.adult-dot {
  background: #38BDF8;
}

.distress-dot {
  background: #EF4444;
}
</style>
