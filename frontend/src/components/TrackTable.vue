<script setup lang="ts">
import { computed, ref } from 'vue'
import { useAquaStore } from '../store'
import type { SwimmerRole, SwimmerTrack } from '../types/aquapulse'

const store = useAquaStore()

const tracks = computed<SwimmerTrack[]>(() => {
  if (store.mode === 'scenario') {
    return store.scenarioData?.tracks || []
  }
  return store.currentFrame?.tracks || []
})

const localOverrides = ref<Record<number, SwimmerRole>>({})
const isDirty = ref(false)

function onRoleChange(trackId: number, newRole: SwimmerRole) {
  localOverrides.value[trackId] = newRole
  isDirty.value = true
}

async function applyOverrides() {
  if (!store.activeJob) return
  try {
    await store.saveConfig(store.activeJob.id, {
      role_overrides: {
        ...store.activeJob.role_overrides,
        ...localOverrides.value,
      },
    })
    await store.reevaluate(store.activeJob.id)
    isDirty.value = false
  } catch (e: any) {
    alert(`Failed to apply role override: ${e.message}`)
  }
}
</script>

<template>
  <div class="track-table-card">
    <div class="table-topline">
      <h4>👥 Multi-Swimmer State Table (Persistent Track IDs)</h4>
      <button v-if="isDirty" class="apply-override-btn" @click="applyOverrides">
        ⚡ Apply Role Override &amp; Re-evaluate (&lt;1s)
      </button>
    </div>

    <div class="table-wrap">
      <table class="tracks-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Role (Override)</th>
            <th>Zone</th>
            <th>Posture</th>
            <th>Adult Dist</th>
            <th>Violation</th>
            <th>State</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="tr in tracks" :key="`track-row-${tr.track_id}`">
            <td><strong>#{{ tr.track_id }}</strong></td>
            <td>
              <select
                :value="localOverrides[tr.track_id] || tr.role"
                class="role-select"
                @change="onRoleChange(tr.track_id, ($event.target as HTMLSelectElement).value as SwimmerRole)"
              >
                <option value="ADULT">Adult</option>
                <option value="TODDLER">Toddler</option>
                <option value="SENIOR">Senior</option>
                <option value="LAP_SWIMMER">Lap Swimmer</option>
              </select>
            </td>
            <td>{{ tr.zone.replace('ZONE_', '').replace('_', ' ') }}</td>
            <td>
              <span class="posture-badge" :class="tr.posture.toLowerCase()">
                {{ tr.posture.replace('_', ' ') }}
              </span>
            </td>
            <td>
              <span v-if="tr.role === 'TODDLER'">
                {{ tr.near_deep_boundary ? '⚠️ Deep End' : 'Safe Zone' }}
              </span>
              <span v-else>—</span>
            </td>
            <td>
              <span v-if="tr.suspected_violation !== 'NONE'" class="violation-chip">
                {{ tr.suspected_violation }}
              </span>
              <span v-else class="text-muted">None</span>
            </td>
            <td>
              <span
                class="status-dot"
                :class="{
                  emergency: tr.is_flailing || tr.is_submerged,
                  caution: tr.near_deep_boundary,
                  nudge: tr.suspected_violation !== 'NONE',
                  normal: !tr.is_flailing && !tr.is_submerged && !tr.near_deep_boundary && tr.suspected_violation === 'NONE'
                }"
              ></span>
            </td>
          </tr>
          <tr v-if="!tracks.length">
            <td colspan="7" class="empty-cell">No active swimmers at this timestamp.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.track-table-card {
  background: rgba(15, 26, 36, 0.85);
  border: 1px solid rgba(51, 78, 104, 0.4);
  border-radius: 10px;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  backdrop-filter: blur(8px);
}

.table-topline {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.table-topline h4 {
  margin: 0;
  font-size: 0.95rem;
  color: #FFFFFF;
}

.apply-override-btn {
  background: #176776;
  color: #F5F8F9;
  border: none;
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.35rem 0.75rem;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 0 10px rgba(0, 229, 255, 0.3);
}

.table-wrap {
  overflow-x: auto;
}

.tracks-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
  text-align: left;
}

.tracks-table th {
  color: #617981;
  border-bottom: 1px solid rgba(51, 78, 104, 0.5);
  padding: 0.45rem 0.6rem;
  font-size: 0.7rem;
  text-transform: uppercase;
}

.tracks-table td {
  padding: 0.5rem 0.6rem;
  border-bottom: 1px solid rgba(51, 78, 104, 0.2);
  color: #213D46;
}

.role-select {
  background: #F5F8F9;
  border: 1px solid rgba(51, 78, 104, 0.5);
  color: #176776;
  font-size: 0.75rem;
  padding: 0.2rem 0.45rem;
  border-radius: 4px;
}

.posture-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
  text-transform: uppercase;
  background: rgba(51, 78, 104, 0.3);
}

.posture-badge.horizontal_submerged,
.posture-badge.active_flailing {
  background: rgba(255, 23, 68, 0.2);
  color: #A34E42;
}

.violation-chip {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  color: #A56535;
  background: rgba(255, 145, 0, 0.15);
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
}

.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot.normal { background: #397A68; }
.status-dot.caution { background: #B1782A; }
.status-dot.emergency { background: #A34E42; box-shadow: 0 0 6px #A34E42; }
.status-dot.nudge { background: #A56535; }

.text-muted { color: #72858B; }

.empty-cell {
  text-align: center;
  color: #617981;
  padding: 1.25rem;
  font-size: 0.78rem;
}
</style>
