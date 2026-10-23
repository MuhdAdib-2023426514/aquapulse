<script setup lang="ts">
import { computed } from 'vue'
import { useAquaStore } from '../store'
import type { TimelineEvent } from '../types/aquapulse'

const store = useAquaStore()

const duration = computed(() => store.activeJob?.duration_sec || 1.0)
const events = computed(() => store.events)

function eventColor(ev: TimelineEvent): string {
  if (ev.kind.includes('emergency') || ev.kind.includes('siren')) return '#A34E42'
  if (ev.kind.includes('beacon') || ev.kind.includes('caution')) return '#B1782A'
  if (ev.kind.includes('nudge')) return '#176776'
  if (ev.kind.includes('guard')) return '#B388FF'
  if (ev.kind.includes('cleaner')) return '#69F0AE'
  return '#FFFFFF'
}

function seekToEvent(ev: TimelineEvent) {
  store.seekTo(ev.t)
}
</script>

<template>
  <div class="event-timeline-card">
    <div class="timeline-header">
      <span class="events-count">⚡ {{ events.length }} Actuation Events Detected</span>
      <small>Click any marker below to jump video playhead directly to that escalation moment</small>
    </div>

    <!-- Interactive Scrubber Track with Markers -->
    <div class="markers-track">
      <div
        class="playhead-line"
        :style="{ left: `${Math.min(100, (store.playheadSec / duration) * 100)}%` }"
      ></div>

      <div
        v-for="(ev, idx) in events"
        :key="`marker-${idx}`"
        class="event-marker"
        :style="{
          left: `${Math.min(99, (ev.t / duration) * 100)}%`,
          backgroundColor: eventColor(ev)
        }"
        :title="`t=${ev.t}s: ${ev.kind} - ${ev.message}`"
        @click="seekToEvent(ev)"
      >
        <span class="marker-dot"></span>
      </div>
    </div>

    <!-- Legend -->
    <div class="markers-legend">
      <span><i style="background:#B1782A"></i> Verify Beacon (5s)</span>
      <span><i style="background:#A34E42"></i> Emergency Siren (8s)</span>
      <span><i style="background:#176776"></i> Polite Nudge (5s)</span>
      <span><i style="background:#B388FF"></i> Guard Ticket (8s)</span>
      <span><i style="background:#69F0AE"></i> Cleaner Ticket</span>
    </div>
  </div>
</template>

<style scoped>
.event-timeline-card {
  background: rgba(15, 26, 36, 0.85);
  border: 1px solid rgba(51, 78, 104, 0.4);
  border-radius: 10px;
  padding: 0.85rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  backdrop-filter: blur(8px);
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.78rem;
}

.events-count {
  font-weight: 700;
  color: #176776;
  font-family: 'JetBrains Mono', monospace;
}

.timeline-header small {
  color: #617981;
  font-size: 0.7rem;
}

.markers-track {
  position: relative;
  width: 100%;
  height: 24px;
  background: rgba(11, 22, 34, 0.9);
  border: 1px solid rgba(51, 78, 104, 0.5);
  border-radius: 6px;
  cursor: pointer;
}

.playhead-line {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: #FFFFFF;
  box-shadow: 0 0 6px #FFFFFF;
  z-index: 5;
}

.event-marker {
  position: absolute;
  top: 3px;
  bottom: 3px;
  width: 6px;
  border-radius: 3px;
  cursor: pointer;
  transition: transform 0.15s ease;
  z-index: 3;
}

.event-marker:hover {
  transform: scaleY(1.3);
}

.markers-legend {
  display: flex;
  gap: 0.85rem;
  font-size: 0.68rem;
  color: #5F737A;
  flex-wrap: wrap;
}

.markers-legend span {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.markers-legend i {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
</style>
