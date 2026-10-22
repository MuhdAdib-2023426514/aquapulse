<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useAquaStore } from '../store'
import { api } from '../api'
import VChart from 'vue-echarts'

const store = useAquaStore()

const selectedDayOfWeek = ref(5) // Default Friday
const loadingComfort = ref(false)
const residentApiData = ref<any>(null)

// Current real-time comfort status from video frame or scenario or API
const currentComfort = computed(() => {
  if (store.mode === 'scenario') {
    return store.scenarioData?.resident_comfort || residentApiData.value?.resident_comfort || null
  }
  return store.currentFrame?.resident_comfort || residentApiData.value?.resident_comfort || null
})

const liveHeadcount = computed(() => currentComfort.value?.live_headcount ?? 0)
const crowdLevel = computed(() => currentComfort.value?.crowd_level ?? 'QUIET')
const lapSwimmers = computed(() => currentComfort.value?.lap_swimmers ?? 0)
const familySwimmers = computed(() => currentComfort.value?.family_swimmers ?? 0)
const toddlerCount = computed(() => currentComfort.value?.toddler_count ?? 0)
const seniorCount = computed(() => currentComfort.value?.senior_count ?? 0)
const waterClarityLabel = computed(() => currentComfort.value?.water_clarity_label ?? 'Crystal Clear (88.5/100)')
const quietHours = computed(() => currentComfort.value?.recommended_quiet_hours ?? ['07:00 - 08:30 AM', '11:00 AM - 03:00 PM', '09:00 - 10:00 PM'])
const safeWindow = computed(() => currentComfort.value?.senior_toddler_safe_window ?? '09:00 - 11:00 AM (Low Bather Density)')

onMounted(async () => {
  await fetchResidentData()
})

watch(selectedDayOfWeek, async () => {
  await fetchResidentData()
})

async function fetchResidentData() {
  loadingComfort.value = true
  try {
    residentApiData.value = await api.getResidentComfort(selectedDayOfWeek.value)
  } catch (e) {
    console.error('Failed to load resident comfort', e)
  } finally {
    loadingComfort.value = false
  }
}

const days = [
  { id: 0, label: 'Mon' },
  { id: 1, label: 'Tue' },
  { id: 2, label: 'Wed' },
  { id: 3, label: 'Thu' },
  { id: 4, label: 'Fri' },
  { id: 5, label: 'Sat' },
  { id: 6, label: 'Sun' },
]

// ECharts: 24h Diurnal Crowd Forecast Chart
const forecastChartOption = computed(() => {
  const forecast = residentApiData.value?.forecast_24h || []
  if (!forecast.length) return {}

  const hours = forecast.map((f: any) => `${f.hour}:00`)
  const counts = forecast.map((f: any) => f.predicted_headcount)

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#FFFFFF',
      borderColor: '#176776',
      textStyle: { color: '#213D46', fontFamily: 'JetBrains Mono' },
      formatter: (params: any) => {
        const item = forecast[params[0].dataIndex]
        return `<b>${item.hour}:00</b><br/>Forecast: <b>${item.predicted_headcount} bathers</b> (${item.crowd_level})<br/>Focus: ${item.activity_focus}<br/>Recommended For: <i>${item.recommended_for}</i>`
      },
    },
    grid: { left: '8%', right: '8%', top: '15%', bottom: '15%' },
    xAxis: {
      type: 'category',
      data: hours,
      axisLine: { lineStyle: { color: '#DCE6E9' } },
      axisLabel: { color: '#5F737A', interval: 2 },
    },
    yAxis: {
      type: 'value',
      name: 'Expected Bathers',
      axisLine: { lineStyle: { color: '#DCE6E9' } },
      axisLabel: { color: '#5F737A' },
      splitLine: { lineStyle: { color: 'rgba(51, 78, 104, 0.2)' } },
    },
    series: [
      {
        name: 'Expected Bathers',
        type: 'bar',
        data: counts.map((c: number) => ({
          value: c,
          itemStyle: {
            color: c <= 4 ? '#397A68' : c <= 12 ? '#B1782A' : '#176776',
            borderRadius: [4, 4, 0, 0],
          },
        })),
        markLine: {
          silent: true,
          lineStyle: { color: '#A34E42', type: 'dashed' },
          data: [{ yAxis: 15, label: { formatter: 'High Crowd Threshold (15+)', color: '#A34E42' } }],
        },
      },
    ],
  }
})
</script>

<template>
  <div class="resident-view">
    <!-- Header Banner -->
    <div class="resident-hero-card">
      <div class="hero-left">
        <div class="hero-badge">SAMPLE FORECAST</div>
        <h2>Pool crowd preview</h2>
        <p class="hero-desc">Illustrative occupancy and visit-time examples. No live camera or resident data is connected.</p>
      </div>
      <div class="hero-right">
        <span class="privacy-seal">
          🔒 Prototype privacy view &bull; Zero Facial ID
        </span>
      </div>
    </div>

    <!-- Main Content: Mobile Mockup + Analytics Forecast -->
    <div class="resident-grid">
      <!-- Left: Mobile Phone App Preview Mockup -->
      <div class="phone-mockup-wrapper">
        <div class="smartphone-frame">
          <!-- Phone Speaker Notch -->
          <div class="phone-notch">
            <span class="speaker-pill"></span>
            <span class="camera-dot"></span>
          </div>

          <!-- Inside Screen -->
          <div class="phone-screen">
            <!-- App Header -->
            <div class="app-topbar">
              <span class="app-brand">Resident sample</span>
              <span class="live-pill">SAMPLE</span>
            </div>

            <!-- Crowd Hero Card -->
            <div class="app-crowd-card" :class="crowdLevel.toLowerCase()">
              <div class="crowd-status-row">
                <span class="crowd-title">Pool Occupancy</span>
                <span class="crowd-badge" :class="crowdLevel.toLowerCase()">{{ crowdLevel }}</span>
              </div>
              <div class="crowd-count-num">
                {{ liveHeadcount }}
                <span class="unit">swimmers active</span>
              </div>
              <p class="crowd-advice">
                {{ crowdLevel === 'QUIET' ? 'Ideal time for serene lap swimming and toddler safety.' : crowdLevel === 'MODERATE' ? 'Comfortable recreational atmosphere.' : 'High activity — pool deck busy.' }}
              </p>
            </div>

            <!-- Swimmer Demographic Breakdown -->
            <div class="demographic-card">
              <div class="card-subtitle">Swimmer Activity Mix</div>
              <div class="demo-bars">
                <div class="demo-item">
                  <span class="demo-label">🏊 Lap Swimmers</span>
                  <span class="demo-val">{{ lapSwimmers }}</span>
                </div>
                <div class="demo-item">
                  <span class="demo-label">👨‍👩‍👧 Family Recreation</span>
                  <span class="demo-val">{{ familySwimmers }}</span>
                </div>
                <div class="demo-item">
                  <span class="demo-label">👶 Toddlers & Infants</span>
                  <span class="demo-val">{{ toddlerCount }}</span>
                </div>
                <div class="demo-item">
                  <span class="demo-label">👵 Seniors</span>
                  <span class="demo-val">{{ seniorCount }}</span>
                </div>
              </div>
            </div>

            <!-- Water Quality Status Pill -->
            <div class="app-water-status">
              <span class="water-icon">💧</span>
              <div class="water-text">
                <span class="label">Water Clarity Status</span>
                <span class="val">{{ waterClarityLabel }}</span>
              </div>
            </div>

            <!-- Recommended Safe & Quiet Windows -->
            <div class="safe-window-card">
              <div class="card-subtitle">Recommended Visit Windows</div>
              <div class="window-entry">
                <span class="window-icon">🛡️</span>
                <div class="window-details">
                  <span class="title">Senior & Toddler Safe Hour</span>
                  <span class="time">{{ safeWindow }}</span>
                </div>
              </div>
              <div class="window-entry">
                <span class="window-icon">🧘</span>
                <div class="window-details">
                  <span class="title">Quiet Meditation & Laps</span>
                  <span class="time">{{ quietHours.join(', ') }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Right: Diurnal Crowd Forecaster & Planning -->
      <div class="forecast-panel">
        <div class="forecast-header">
          <div>
            <h3>Example crowd forecast</h3>
            <p class="forecast-subtitle">Seeded sample forecast; not a live occupancy feed</p>
          </div>
          <!-- Day of Week Selector -->
          <div class="dow-selector">
            <button
              v-for="d in days"
              :key="d.id"
              class="dow-btn"
              :class="{ active: selectedDayOfWeek === d.id }"
              @click="selectedDayOfWeek = d.id"
            >
              {{ d.label }}
            </button>
          </div>
        </div>

        <div class="chart-container">
          <VChart :option="forecastChartOption" autoresize />
        </div>

        <!-- Legend / Guidance Chips -->
        <div class="legend-chips-row">
          <div class="chip quiet-chip">
            <span class="dot"></span>
            <span>Quiet (&le;4 bathers) — Best for Lap Swimmers & Seniors</span>
          </div>
          <div class="chip mod-chip">
            <span class="dot"></span>
            <span>Moderate (5–12) — Balanced Family Leisure</span>
          </div>
          <div class="chip busy-chip">
            <span class="dot"></span>
            <span>Peak Crowd (>12) — High Energy & Children Play</span>
          </div>
        </div>
        <p class="data-note">All values on this page are illustrative sample data. They do not describe current residents or pool conditions.</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.resident-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.resident-hero-card {
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

.privacy-seal {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  background: rgba(0, 255, 102, 0.15);
  color: #397A68;
  border: 1px solid rgba(0, 255, 102, 0.4);
  padding: 0.5rem 0.85rem;
  border-radius: 20px;
  display: inline-block;
  white-space: nowrap;
}

/* Grid */
.resident-grid {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 1.75rem;
}

/* Smartphone Mockup */
.phone-mockup-wrapper {
  display: flex;
  justify-content: center;
}

.smartphone-frame {
  width: 340px;
  background: #F5F8F9;
  border: 8px solid #1E293B;
  border-radius: 36px;
  box-shadow: 0 20px 45px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(0, 229, 255, 0.2);
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
}

.phone-notch {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 0.5rem;
  padding-bottom: 0.5rem;
}

.speaker-pill {
  width: 48px;
  height: 4px;
  background: #DCE6E9;
  border-radius: 2px;
}

.camera-dot {
  width: 6px;
  height: 6px;
  background: #DCE6E9;
  border-radius: 50%;
}

.phone-screen {
  background: #FFFFFF;
  border-radius: 24px;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  min-height: 520px;
}

.app-topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(51, 78, 104, 0.3);
  padding-bottom: 0.5rem;
}

.app-brand {
  font-size: 0.8rem;
  font-weight: 700;
  color: #FFFFFF;
}

.live-pill {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  color: #397A68;
  background: rgba(0, 255, 102, 0.15);
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
  font-weight: 600;
}

.app-crowd-card {
  background: rgba(11, 22, 34, 0.8);
  border: 1px solid rgba(51, 78, 104, 0.5);
  border-radius: 12px;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.app-crowd-card.quiet {
  border-color: rgba(0, 255, 102, 0.4);
}

.app-crowd-card.moderate {
  border-color: rgba(255, 234, 0, 0.4);
}

.app-crowd-card.busy {
  border-color: rgba(255, 23, 68, 0.4);
}

.crowd-status-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.crowd-title {
  font-size: 0.75rem;
  color: #617981;
}

.crowd-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
}

.crowd-badge.quiet { background: rgba(0, 255, 102, 0.2); color: #397A68; }
.crowd-badge.moderate { background: rgba(255, 234, 0, 0.2); color: #B1782A; }
.crowd-badge.busy { background: rgba(255, 23, 68, 0.2); color: #A34E42; }

.crowd-count-num {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1.8rem;
  font-weight: 800;
  color: #FFFFFF;
}

.crowd-count-num .unit {
  font-size: 0.8rem;
  color: #5F737A;
  font-weight: 500;
}

.crowd-advice {
  font-size: 0.75rem;
  color: #4B6269;
  line-height: 1.35;
  margin: 0;
}

.demographic-card {
  background: rgba(11, 22, 34, 0.6);
  border: 1px solid rgba(51, 78, 104, 0.3);
  border-radius: 10px;
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.card-subtitle {
  font-size: 0.7rem;
  color: #617981;
  font-weight: 600;
  text-transform: uppercase;
}

.demo-bars {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.demo-item {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #4B6269;
}

.demo-val {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  color: #176776;
}

.app-water-status {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  background: rgba(0, 229, 255, 0.08);
  border: 1px solid rgba(0, 229, 255, 0.25);
  border-radius: 8px;
  padding: 0.6rem 0.75rem;
}

.water-icon {
  font-size: 1.25rem;
}

.water-text {
  display: flex;
  flex-direction: column;
}

.water-text .label {
  font-size: 0.65rem;
  color: #617981;
}

.water-text .val {
  font-size: 0.8rem;
  font-weight: 600;
  color: #FFFFFF;
}

.safe-window-card {
  background: rgba(11, 22, 34, 0.6);
  border: 1px solid rgba(51, 78, 104, 0.3);
  border-radius: 10px;
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.window-entry {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
}

.window-icon {
  font-size: 1rem;
}

.window-details {
  display: flex;
  flex-direction: column;
}

.window-details .title {
  font-size: 0.72rem;
  font-weight: 600;
  color: #FFFFFF;
}

.window-details .time {
  font-size: 0.7rem;
  color: #176776;
  font-family: 'JetBrains Mono', monospace;
}

/* Forecast Panel */
.forecast-panel {
  background: rgba(15, 26, 36, 0.85);
  border: 1px solid rgba(51, 78, 104, 0.4);
  border-radius: 10px;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.forecast-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.forecast-header h3 {
  margin: 0;
  font-size: 1.15rem;
  color: #FFFFFF;
}

.forecast-subtitle {
  font-size: 0.78rem;
  color: #617981;
  margin: 0.25rem 0 0 0;
}

.dow-selector {
  display: flex;
  gap: 0.35rem;
  background: rgba(11, 22, 34, 0.7);
  padding: 0.25rem;
  border-radius: 6px;
  border: 1px solid rgba(51, 78, 104, 0.4);
}

.dow-btn {
  background: transparent;
  border: none;
  color: #5F737A;
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.35rem 0.65rem;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.dow-btn:hover {
  color: #FFFFFF;
}

.dow-btn.active {
  background: #176776;
  color: #F5F8F9;
}

.chart-container {
  height: 270px;
  width: 100%;
}

.legend-chips-row {
  display: flex;
  gap: 1rem;
  font-size: 0.75rem;
}

.chip {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  color: #5F737A;
}

.chip .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.quiet-chip .dot { background: #397A68; }
.mod-chip .dot { background: #B1782A; }
.busy-chip .dot { background: #176776; }

.township-value-box {
  background: rgba(11, 22, 34, 0.6);
  border-left: 3px solid #176776;
  border-radius: 0 8px 8px 0;
  padding: 1rem 1.25rem;
}

.township-value-box h4 {
  margin: 0 0 0.5rem 0;
  font-size: 0.88rem;
  color: #FFFFFF;
}

.township-value-box ul {
  margin: 0;
  padding-left: 1.25rem;
  font-size: 0.8rem;
  color: #5F737A;
  line-height: 1.5;
}

.township-value-box li b {
  color: #213D46;
}
</style>
