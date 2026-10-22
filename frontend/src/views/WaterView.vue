<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAquaStore } from '../store'
import { api } from '../api'

const store = useAquaStore()

const loadingInspect = ref(false)
const waterInspectData = ref<any>(null)

// Current report from video frame or scenario or API
const currentWaterReport = computed(() => {
  if (store.mode === 'scenario') {
    return store.scenarioData?.water_report || waterInspectData.value?.report || null
  }
  return store.currentFrame?.water_report || waterInspectData.value?.report || null
})

// Current inspection image (from video frame or scenario rendered frame)
const inspectionImageUrl = computed(() => {
  if (store.mode === 'scenario') {
    return store.scenarioData?.rendered_frames?.water_annotated_bgr || null
  }
  const imgRel = store.currentFrame?.water_image
  if (imgRel && store.activeJobId) {
    return api.mediaUrl(store.activeJobId, imgRel)
  }
  return null
})

const turbidityScore = computed(() => currentWaterReport.value?.turbidity_score ?? 88.5)
const algaeIndex = computed(() => currentWaterReport.value?.algae_green_index ?? 12.0)
const debrisCount = computed(() => currentWaterReport.value?.floating_debris_count ?? 0)
const status = computed(() => currentWaterReport.value?.status ?? 'CRYSTAL_CLEAR')
const ticketOpened = computed(() => currentWaterReport.value?.cleaner_ticket_opened ?? false)
const recommendedAction = computed(() => currentWaterReport.value?.recommended_action ?? 'Normal automated filtration; no manual intervention required.')

const maintenanceTickets = computed(() => waterInspectData.value?.maintenance_tickets || [])

onMounted(async () => {
  await fetchWaterData()
})

async function fetchWaterData() {
  loadingInspect.value = true
  try {
    waterInspectData.value = await api.getWaterInspect()
  } catch (e) {
    console.error('Failed to load water inspect', e)
  } finally {
    loadingInspect.value = false
  }
}
</script>

<template>
  <div class="water-view">
    <!-- Header Banner -->
    <div class="water-hero-card">
      <div class="hero-left">
        <div class="hero-badge">SYNTHETIC VISUAL DEMO</div>
        <h2>Visual water indicators</h2>
        <p class="hero-desc">Image heuristics only. These values are not water-quality measurements and do not create facility work orders.</p>
      </div>
      <div class="hero-right">
        <button class="run-inspect-btn" :disabled="loadingInspect" @click="fetchWaterData">
          {{ loadingInspect ? 'Inspecting...' : '🔄 Re-Run Off-Peak Diagnostic' }}
        </button>
      </div>
    </div>

    <!-- Status & Core Gauges Row -->
    <div class="gauges-grid">
      <!-- Status Badge Card -->
      <div class="gauge-card status-card">
        <div class="gauge-label">Visual indicator summary</div>
        <div class="status-hero" :class="status.toLowerCase()">
          <span class="status-icon">
            {{ status === 'CRYSTAL_CLEAR' ? '✨' : status === 'ALGAE_WARNING' ? '⚠️' : '🍂' }}
          </span>
          <span class="status-name">{{ status.replace(/_/g, ' ') }}</span>
        </div>
        <div class="status-ticket-badge" v-if="ticketOpened">
          🎫 Sample maintenance action
        </div>
        <div class="action-note">
          <b>Recommended Action</b>: {{ recommendedAction }}
        </div>
      </div>

      <!-- Turbidity Score -->
      <div class="gauge-card">
        <div class="gauge-label">
          <span>TILE EDGE CONTRAST (TURBIDITY)</span>
          <span class="tag" :class="turbidityScore >= 70 ? 'tag-good' : 'tag-alert'">
            {{ turbidityScore >= 70 ? 'HIGH CONTRAST' : 'TURBID' }}
          </span>
        </div>
        <div class="gauge-hero-val" :class="turbidityScore >= 70 ? 'text-good' : 'text-alert'">
          {{ turbidityScore.toFixed(1) }}
          <span class="unit">/ 100</span>
        </div>
        <div class="gauge-sub-info">
          <span>Target: &ge; 70.0 (Crystal Clear)</span>
          <span>Method: Laplacian Variance</span>
        </div>
        <div class="bar-wrap">
          <div
            class="bar"
            :style="{ width: `${turbidityScore}%` }"
            :class="turbidityScore >= 70 ? 'bar-good' : 'bar-alert'"
          ></div>
        </div>
      </div>

      <!-- Algae Green Index -->
      <div class="gauge-card">
        <div class="gauge-label">
          <span>ALGAE GREEN DRIFT INDEX</span>
          <span class="tag" :class="algaeIndex < 25 ? 'tag-good' : 'tag-danger'">
            {{ algaeIndex < 25 ? 'NORMAL' : 'ALGAE RISK' }}
          </span>
        </div>
        <div class="gauge-hero-val" :class="algaeIndex < 25 ? 'text-good' : 'text-danger'">
          {{ algaeIndex.toFixed(1) }}
          <span class="unit">/ 100</span>
        </div>
        <div class="gauge-sub-info">
          <span>Threshold: &le; 25.0 Safe</span>
          <span>HSV Color Histogram Shift</span>
        </div>
        <div class="bar-wrap">
          <div
            class="bar"
            :style="{ width: `${Math.min(100, algaeIndex * 2)}%` }"
            :class="algaeIndex < 25 ? 'bar-good' : 'bar-danger'"
          ></div>
        </div>
      </div>

      <!-- Floating Debris Count -->
      <div class="gauge-card">
        <div class="gauge-label">
          <span>FLOATING DEBRIS / LEAVES</span>
          <span class="tag" :class="debrisCount === 0 ? 'tag-good' : 'tag-alert'">
            {{ debrisCount === 0 ? 'CLEAN' : 'DEBRIS DETECTED' }}
          </span>
        </div>
        <div class="gauge-hero-val" :class="debrisCount === 0 ? 'text-good' : 'text-alert'">
          {{ debrisCount }}
          <span class="unit">objects</span>
        </div>
        <div class="gauge-sub-info">
          <span>Surface Contours: {{ debrisCount > 0 ? 'Leaves / Twigs' : 'None' }}</span>
          <span>Monsoon Watch: Active</span>
        </div>
        <div class="bar-wrap">
          <div
            class="bar"
            :style="{ width: `${Math.min(100, debrisCount * 25)}%` }"
            :class="debrisCount === 0 ? 'bar-good' : 'bar-alert'"
          ></div>
        </div>
      </div>
    </div>

    <details class="data-details">
      <summary>View image and maintenance details</summary>
    <!-- Visual Diagnostic Frame + JMB Work Orders Grid -->
    <div class="diagnostic-grid">
      <!-- Left: Annotated Diagnostic Frame -->
      <div class="panel-box visual-panel">
        <div class="panel-header">
          <h3>Visual Water Analysis Overlay</h3>
          <span class="tag-live">ROI CONTOUR MASK</span>
        </div>
        <div class="image-stage">
          <img
            v-if="inspectionImageUrl"
            :src="inspectionImageUrl"
            alt="Water Clarity Overlay"
            class="water-img"
          />
          <div v-else class="no-img-placeholder">
            <span class="icon">🌊</span>
            <span class="msg">Image overlay appears after video or demo processing</span>
            <span class="hint">Upload clip or step into Monsoon Debris & Algae scenario</span>
          </div>
        </div>
        <div class="stage-footer">
          <span>Green Contours = Floating Debris</span>
          <span>Grid Contrast = Floor Tile Clarity</span>
          <span>HSV Spectrum = Algae Drift</span>
        </div>
      </div>

      <!-- Right: Automated JMB Facility Tickets -->
      <div class="panel-box tickets-panel">
        <div class="panel-header">
          <h3>Maintenance records</h3>
          <span class="tag-db">SAMPLE / API DATA</span>
        </div>

        <div class="tickets-table-wrap">
          <table class="tickets-table">
            <thead>
              <tr>
                <th>Ticket ID</th>
                <th>Timestamp</th>
                <th>Status</th>
                <th>Turbidity</th>
                <th>Algae</th>
                <th>Debris</th>
                <th>Action Taken</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="maintenanceTickets.length === 0">
                <td colspan="7" class="empty-data">No maintenance records available.</td>
              </tr>
              <tr v-for="t in maintenanceTickets" :key="t.id">
                <td class="mono">#WO-{{ t.id }}</td>
                <td class="timestamp">{{ t.timestamp }}</td>
                <td>
                  <span class="ticket-status-pill" :class="t.status.toLowerCase()">
                    {{ t.status }}
                  </span>
                </td>
                <td class="mono">{{ Number(t.turbidity_score).toFixed(1) }}</td>
                <td class="mono">{{ Number(t.algae_index).toFixed(1) }}</td>
                <td class="mono">{{ t.debris_count }}</td>
                <td class="action-text">{{ t.action_taken }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
    </details>
  </div>
</template>

<style scoped>
.water-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.water-hero-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(135deg, rgba(11, 22, 34, 0.95), rgba(8, 40, 50, 0.85));
  border: 1px solid rgba(0, 229, 255, 0.25);
  border-radius: 12px;
  padding: 1.5rem 1.75rem;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.37);
}

.hero-left {
  max-width: 72%;
}

.hero-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: #176776;
  letter-spacing: 0.1em;
  margin-bottom: 0.5rem;
}

.hero-left h2 {
  font-size: 1.5rem;
  color: #FFFFFF;
  margin: 0 0 0.5rem 0;
  font-weight: 700;
}

.hero-desc {
  font-size: 0.9rem;
  color: #5F737A;
  line-height: 1.45;
  margin: 0;
}

.run-inspect-btn {
  background: rgba(0, 229, 255, 0.15);
  color: #176776;
  border: 1px solid #176776;
  border-radius: 8px;
  padding: 0.75rem 1.25rem;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.run-inspect-btn:hover:not(:disabled) {
  background: #176776;
  color: #F5F8F9;
}

.run-inspect-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Gauges Grid */
.gauges-grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr 1fr 1fr;
  gap: 1.25rem;
}

.gauge-card {
  background: rgba(15, 26, 36, 0.85);
  border: 1px solid rgba(51, 78, 104, 0.4);
  border-radius: 10px;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  backdrop-filter: blur(8px);
}

.status-card {
  border-color: rgba(0, 229, 255, 0.35);
}

.gauge-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.72rem;
  color: #5F737A;
  font-weight: 600;
  letter-spacing: 0.05em;
}

.status-hero {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-size: 1.25rem;
  font-weight: 800;
  color: #FFFFFF;
  margin: 0.25rem 0;
}

.status-hero.crystal_clear {
  color: #397A68;
}

.status-hero.slight_turbidity {
  color: #B1782A;
}

.status-hero.algae_warning {
  color: #A56535;
}

.status-hero.monsoon_debris_alert {
  color: #A34E42;
}

.status-ticket-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: #A56535;
  background: rgba(255, 145, 0, 0.15);
  padding: 0.3rem 0.6rem;
  border-radius: 4px;
  width: fit-content;
  font-weight: 600;
}

.action-note {
  font-size: 0.8rem;
  color: #5F737A;
  line-height: 1.35;
  background: rgba(11, 22, 34, 0.5);
  padding: 0.5rem 0.7rem;
  border-radius: 6px;
  border-left: 2px solid #176776;
}

.gauge-hero-val {
  font-family: 'JetBrains Mono', monospace;
  font-size: 2rem;
  font-weight: 800;
  color: #FFFFFF;
}

.gauge-hero-val .unit {
  font-size: 0.9rem;
  color: #5F737A;
  font-weight: 500;
}

.text-good { color: #397A68; }
.text-alert { color: #A56535; }
.text-danger { color: #A34E42; }

.gauge-sub-info {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #617981;
}

.tag {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
  font-weight: 600;
}

.tag-good { background: rgba(0, 255, 102, 0.15); color: #397A68; }
.tag-alert { background: rgba(255, 145, 0, 0.15); color: #A56535; }
.tag-danger { background: rgba(255, 23, 68, 0.15); color: #A34E42; }

.bar-wrap {
  width: 100%;
  height: 6px;
  background: rgba(30, 41, 59, 0.8);
  border-radius: 3px;
  overflow: hidden;
  margin-top: 0.25rem;
}

.bar {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.bar-good { background: #397A68; }
.bar-alert { background: #A56535; }
.bar-danger { background: #A34E42; }

/* Diagnostic Grid */
.diagnostic-grid {
  display: grid;
  grid-template-columns: 1fr 1.2fr;
  gap: 1.25rem;
}

.panel-box {
  background: rgba(15, 26, 36, 0.85);
  border: 1px solid rgba(51, 78, 104, 0.4);
  border-radius: 10px;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.panel-header h3 {
  margin: 0;
  font-size: 1.05rem;
  color: #FFFFFF;
}

.tag-live {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  background: rgba(0, 229, 255, 0.15);
  color: #176776;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
}

.tag-db {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  background: rgba(0, 255, 102, 0.15);
  color: #397A68;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
}

.image-stage {
  min-height: 260px;
  background: #F5F8F9;
  border: 1px solid rgba(51, 78, 104, 0.5);
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.water-img {
  width: 100%;
  height: auto;
  display: block;
}

.no-img-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  color: #617981;
  text-align: center;
  padding: 2rem;
}

.no-img-placeholder .icon {
  font-size: 2.5rem;
}

.no-img-placeholder .msg {
  font-size: 0.9rem;
  color: #4B6269;
}

.no-img-placeholder .hint {
  font-size: 0.75rem;
  color: #72858B;
}

.stage-footer {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #617981;
  margin-top: 0.65rem;
  font-family: 'JetBrains Mono', monospace;
}

/* Tickets Table */
.tickets-table-wrap {
  overflow-x: auto;
}

.tickets-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
  text-align: left;
}

.tickets-table th {
  color: #617981;
  border-bottom: 1px solid rgba(51, 78, 104, 0.5);
  padding: 0.5rem 0.6rem;
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.7rem;
}

.tickets-table td {
  padding: 0.6rem;
  border-bottom: 1px solid rgba(51, 78, 104, 0.2);
  color: #213D46;
}

.tickets-table tr:hover td {
  background: rgba(0, 229, 255, 0.04);
}

.mono {
  font-family: 'JetBrains Mono', monospace;
}

.timestamp {
  font-size: 0.75rem;
  color: #5F737A;
}

.action-text {
  font-size: 0.78rem;
  color: #4B6269;
}

.ticket-status-pill {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.68rem;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-weight: 600;
}

.ticket-status-pill.resolved,
.ticket-status-pill.completed {
  background: rgba(0, 255, 102, 0.15);
  color: #397A68;
}

.ticket-status-pill.open,
.ticket-status-pill.pending {
  background: rgba(255, 145, 0, 0.15);
  color: #A56535;
}
</style>
