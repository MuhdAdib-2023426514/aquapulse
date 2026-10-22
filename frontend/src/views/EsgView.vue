<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useAquaStore } from '../store'
import { api } from '../api'
import VChart from 'vue-echarts'
import * as echarts from 'echarts'

const store = useAquaStore()

const loadingSummary = ref(false)
const esgSummary = ref<any>(null)

// Current real-time metrics (synced to video playhead or scenario step)
const currentEsg = computed(() => {
  if (store.mode === 'scenario') {
    return store.scenarioData?.esg_metrics || null
  }
  return store.currentFrame?.esg_metrics || null
})

const batherCount = computed(() => currentEsg.value?.bather_count ?? 0)
const contaminationScore = computed(() => currentEsg.value?.contamination_score ?? 0)
const vfdSpeedPct = computed(() => currentEsg.value?.recommended_vfd_speed_pct ?? 40.0)
const flowRate = computed(() => currentEsg.value?.flow_rate_m3h ?? 28.0)
const vfdKw = computed(() => currentEsg.value?.vfd_pump_kw ?? 0.352)
const fixedKw = computed(() => currentEsg.value?.fixed_pump_kw ?? 5.5)
const hourlyKwhSaved = computed(() => currentEsg.value?.hourly_kwh_saved ?? 5.148)
const hourlyRmSaved = computed(() => currentEsg.value?.hourly_rm_saved ?? 2.625)
const hourlyCo2Saved = computed(() => currentEsg.value?.hourly_co2_saved_kg ?? 3.902)
const turnovers = computed(() => currentEsg.value?.projected_daily_turnovers ?? 3.73)
const isTurnoverCompliant = computed(() => currentEsg.value?.turnover_floor_compliant ?? true)

onMounted(async () => {
  loadingSummary.value = true
  try {
    esgSummary.value = await api.getEsgSummary()
  } catch (e) {
    console.error('Failed to load ESG summary', e)
  } finally {
    loadingSummary.value = false
  }
})

// ECharts: Affinity Law Curve P ∝ N^3 with real-time operating point
const affinityChartOption = computed(() => {
  const curve = esgSummary.value?.affinity_law_curve || [
    { speed_pct: 0, power_pct: 0, typical_kw: 0 },
    { speed_pct: 20, power_pct: 0.8, typical_kw: 0.044 },
    { speed_pct: 40, power_pct: 6.4, typical_kw: 0.352 },
    { speed_pct: 60, power_pct: 21.6, typical_kw: 1.188 },
    { speed_pct: 70, power_pct: 34.3, typical_kw: 1.887 },
    { speed_pct: 80, power_pct: 51.2, typical_kw: 2.816 },
    { speed_pct: 90, power_pct: 72.9, typical_kw: 4.01 },
    { speed_pct: 100, power_pct: 100, typical_kw: 5.5 },
  ]

  const speeds = curve.map((c: any) => c.speed_pct)
  const powers = curve.map((c: any) => c.typical_kw)

  const curSpeed = vfdSpeedPct.value
  const curKw = vfdKw.value

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0F1A24',
      borderColor: '#00E5FF',
      textStyle: { color: '#E0F2FE', fontFamily: 'JetBrains Mono' },
      formatter: (params: any) => {
        const p = params[0]
        return `<b>VFD Speed: ${p.axisValue}%</b><br/>Pump Power: <b>${p.data} kW</b><br/>vs Fixed: <b>5.50 kW</b>`
      },
    },
    grid: { left: '12%', right: '8%', top: '15%', bottom: '15%' },
    xAxis: {
      type: 'category',
      data: speeds,
      name: 'Pump Speed (%)',
      nameLocation: 'middle',
      nameGap: 24,
      axisLine: { lineStyle: { color: '#334E68' } },
      axisLabel: { color: '#9FB3C8', formatter: '{value}%' },
    },
    yAxis: {
      type: 'value',
      name: 'Power (kW)',
      axisLine: { lineStyle: { color: '#334E68' } },
      axisLabel: { color: '#9FB3C8', formatter: '{value} kW' },
      splitLine: { lineStyle: { color: 'rgba(51, 78, 104, 0.3)' } },
    },
    series: [
      {
        name: 'VFD Power (Affinity Law)',
        type: 'line',
        smooth: true,
        data: powers,
        lineStyle: { color: '#00E5FF', width: 3 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(0, 229, 255, 0.35)' },
            { offset: 1, color: 'rgba(0, 229, 255, 0.02)' },
          ]),
        },
        markPoint: {
          data: [
            {
              coord: [String(Math.round(curSpeed / 10) * 10), curKw],
              symbol: 'pin',
              symbolSize: 45,
              itemStyle: { color: '#FF1744' },
              label: {
                formatter: `LIVE\n${curSpeed}%\n${curKw}kW`,
                fontSize: 9,
                color: '#fff',
                fontFamily: 'JetBrains Mono',
              },
            },
          ],
        },
        markLine: {
          silent: true,
          lineStyle: { color: '#FF9100', type: 'dashed' },
          data: [{ yAxis: 5.5, label: { formatter: 'Fixed Baseline (5.5 kW)', color: '#FF9100' } }],
        },
      },
    ],
  }
})

// ECharts: 24-Hour Diurnal Schedule & VFD Modulation
const schedule24hOption = computed(() => {
  const sched = esgSummary.value?.schedule_24h || []
  if (!sched.length) return {}

  const hours = sched.map((s: any) => `${s.hour}:00`)
  const bathers = sched.map((s: any) => s.bather_count)
  const speeds = sched.map((s: any) => s.vfd_speed_pct)

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0F1A24',
      borderColor: '#00E5FF',
      textStyle: { color: '#E0F2FE', fontFamily: 'JetBrains Mono' },
    },
    legend: {
      data: ['Bather Headcount', 'VFD Speed %'],
      textStyle: { color: '#9FB3C8' },
      top: '2%',
    },
    grid: { left: '8%', right: '8%', top: '18%', bottom: '15%' },
    xAxis: {
      type: 'category',
      data: hours,
      axisLine: { lineStyle: { color: '#334E68' } },
      axisLabel: { color: '#9FB3C8', interval: 2 },
    },
    yAxis: [
      {
        type: 'value',
        name: 'Bathers',
        min: 0,
        axisLine: { lineStyle: { color: '#334E68' } },
        axisLabel: { color: '#9FB3C8' },
        splitLine: { lineStyle: { color: 'rgba(51, 78, 104, 0.2)' } },
      },
      {
        type: 'value',
        name: 'VFD %',
        min: 0,
        max: 100,
        axisLine: { lineStyle: { color: '#334E68' } },
        axisLabel: { color: '#00E5FF', formatter: '{value}%' },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: 'Bather Headcount',
        type: 'bar',
        data: bathers,
        itemStyle: { color: 'rgba(0, 229, 255, 0.4)', borderRadius: [3, 3, 0, 0] },
      },
      {
        name: 'VFD Speed %',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        data: speeds,
        lineStyle: { color: '#00FF66', width: 2.5 },
      },
    ],
  }
})
</script>

<template>
  <div class="esg-view">
    <!-- Header Banner -->
    <div class="esg-hero-card">
      <div class="hero-left">
        <div class="hero-badge">TRACK 2: PLANET — ENERGY & WATER CONSERVATION</div>
        <h2>Dynamic "Bather-Load" VFD Pump & Chemical Eco-Drive</h2>
        <p class="hero-desc">
          Continuous modulation of Malaysian high-rise pool filtration pumps based on vision-derived occupancy,
          cotton-streetwear violations, and animal incidents via the <b>Pump Affinity Law</b> ($P \propto N^3$)
          while guaranteeing statutory sanitation via the <b>Turnover Floor ($\ge 3.5$ turns/day)</b>.
        </p>
      </div>
      <div class="hero-right">
        <div class="turnover-pill" :class="{ compliant: isTurnoverCompliant }">
          <span class="pulse-dot"></span>
          <div class="pill-text">
            <span class="label">Daily Turnover Floor</span>
            <span class="val">{{ turnovers.toFixed(2) }} / 3.50 Floor</span>
            <span class="sub">{{ isTurnoverCompliant ? '100% SANITATION COMPLIANT' : 'SUB-FLOOR ALERT' }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Live Real-Time Telemetry Row (Synced to Video Playhead) -->
    <div class="metrics-grid">
      <!-- 1. Bather Load & Contamination -->
      <div class="metric-card">
        <div class="card-title">
          <span>BIOLOGICAL CONTAMINATION</span>
          <span class="tag live-tag">LIVE SYNC</span>
        </div>
        <div class="card-hero-val" :class="{ alert: contaminationScore > 10 }">
          {{ contaminationScore.toFixed(1) }}
          <span class="unit">pts</span>
        </div>
        <div class="card-sub-info">
          <span>Active Bathers: <b>{{ batherCount }}</b></span>
          <span class="pill-mini">Score = (N &times; t) + w&middot;Violations</span>
        </div>
        <div class="progress-bar-wrap">
          <div
            class="progress-bar"
            :style="{ width: `${Math.min(100, (contaminationScore / 25) * 100)}%` }"
            :class="{ warning: contaminationScore > 8, danger: contaminationScore > 15 }"
          ></div>
        </div>
      </div>

      <!-- 2. VFD Speed & Flow Rate -->
      <div class="metric-card">
        <div class="card-title">
          <span>VFD PUMP SPEED</span>
          <span class="tag speed-tag">{{ vfdSpeedPct <= 45 ? 'ECO MODE' : vfdSpeedPct >= 95 ? 'PURGE CYCLE' : 'MODULATING' }}</span>
        </div>
        <div class="card-hero-val accent-cyan">
          {{ vfdSpeedPct.toFixed(0) }}%
          <span class="unit">@ {{ flowRate.toFixed(1) }} m³/h</span>
        </div>
        <div class="card-sub-info">
          <span>Power: <b>{{ vfdKw.toFixed(3) }} kW</b></span>
          <span class="fixed-compare">Fixed Baseline: {{ fixedKw.toFixed(2) }} kW</span>
        </div>
        <div class="progress-bar-wrap">
          <div class="progress-bar cyan" :style="{ width: `${vfdSpeedPct}%` }"></div>
        </div>
      </div>

      <!-- 3. Real-Time Energy & TNB Savings -->
      <div class="metric-card">
        <div class="card-title">
          <span>ENERGY & COST REDUCTION</span>
          <span class="tag tnb-tag">TNB RM 0.51/kWh</span>
        </div>
        <div class="card-hero-val accent-green">
          RM {{ hourlyRmSaved.toFixed(3) }}
          <span class="unit">/ hr</span>
        </div>
        <div class="card-sub-info">
          <span>Saved: <b>{{ hourlyKwhSaved.toFixed(2) }} kWh/h</b></span>
          <span>CO₂ Avoided: <b>{{ hourlyCo2Saved.toFixed(2) }} kg/h</b></span>
        </div>
        <div class="savings-pct-badge">
          &darr; {{ (((fixedKw - vfdKw) / fixedKw) * 100).toFixed(1) }}% Instantaneous Reduction
        </div>
      </div>
    </div>

    <!-- Charts Row: Affinity Law Curve + 24-Hour Diurnal Profile -->
    <div class="charts-row">
      <div class="chart-card">
        <div class="chart-header">
          <div>
            <h3>Pump Affinity Law: Cubic Power Curve</h3>
            <p class="chart-subtitle">P₂ = P₁ &times; (N₂ / N₁)&sup3; &bull; Live operating point updates as video plays</p>
          </div>
          <span class="formula-chip">P &prop; N&sup3;</span>
        </div>
        <div class="chart-container">
          <VChart :option="affinityChartOption" autoresize />
        </div>
        <div class="chart-footer-note">
          💡 <b>Cubic Advantage</b>: At 40% zero-occupancy eco-throttle, power drops from 5.50 kW down to 0.352 kW (<b>93.6% reduction</b>) while sustaining surface skimming.
        </div>
      </div>

      <div class="chart-card">
        <div class="chart-header">
          <div>
            <h3>24-Hour Diurnal Bather Load vs VFD Schedule</h3>
            <p class="chart-subtitle">Optimized schedule ensuring baseline turnover floor while reducing off-peak power</p>
          </div>
          <span class="formula-chip">24H PROFILE</span>
        </div>
        <div class="chart-container">
          <VChart :option="schedule24hOption" autoresize />
        </div>
        <div class="chart-footer-note">
          🌊 Maintains <b>3.73 turnovers/day</b> floor through automated daytime surge filtering and overnight 40% eco-skimming.
        </div>
      </div>
    </div>

    <!-- 30-Day Strata Condo Historical Impact (SQLite Seed) -->
    <div class="history-card" v-if="esgSummary?.summary_30d">
      <div class="history-header">
        <div>
          <h3>30-Day Malaysian Strata Condo Pool Telemetry</h3>
          <p class="chart-subtitle">Historical records pre-seeded from Malaysian high-rise pool facility data (450 m³ pool)</p>
        </div>
        <span class="days-badge">{{ esgSummary.summary_30d.days_recorded || 30 }} Days Tracked</span>
      </div>

      <div class="history-stats-grid">
        <div class="stat-box">
          <span class="label">Fixed Pump Baseline</span>
          <span class="val">{{ (esgSummary.summary_30d.total_fixed_kwh || 3960).toLocaleString() }} kWh</span>
          <span class="sub">100% 24/7 fixed speed</span>
        </div>
        <div class="stat-box">
          <span class="label">AquaPulse VFD Drive</span>
          <span class="val accent-cyan">{{ (esgSummary.summary_30d.total_vfd_kwh || 2760).toLocaleString() }} kWh</span>
          <span class="sub">Dynamic bather-load throttle</span>
        </div>
        <div class="stat-box">
          <span class="label">Net Energy Saved</span>
          <span class="val accent-green">&darr; {{ esgSummary.summary_30d.pct_saved || 30.3 }}%</span>
          <span class="sub">{{ (esgSummary.summary_30d.kwh_saved || 1200).toLocaleString() }} kWh avoided</span>
        </div>
        <div class="stat-box highlight-rm">
          <span class="label">JMB / MC Fund Savings</span>
          <span class="val">RM {{ (esgSummary.summary_30d.rm_saved || 612).toLocaleString() }}</span>
          <span class="sub">@ RM 0.51 / kWh TNB commercial</span>
        </div>
        <div class="stat-box">
          <span class="label">Carbon Abatement</span>
          <span class="val">{{ (esgSummary.summary_30d.co2_saved_kg || 909.6).toLocaleString() }} kg</span>
          <span class="sub">0.91 Metric Tons CO₂</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.esg-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.esg-hero-card {
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
  max-width: 68%;
}

.hero-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: #00E5FF;
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
  color: #9FB3C8;
  line-height: 1.45;
  margin: 0;
}

.turnover-pill {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  background: rgba(15, 26, 36, 0.9);
  border: 1px solid rgba(255, 23, 68, 0.4);
  padding: 0.85rem 1.25rem;
  border-radius: 10px;
}

.turnover-pill.compliant {
  border-color: rgba(0, 255, 102, 0.5);
  box-shadow: 0 0 15px rgba(0, 255, 102, 0.15);
}

.pulse-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #FF1744;
}

.turnover-pill.compliant .pulse-dot {
  background: #00FF66;
  box-shadow: 0 0 8px #00FF66;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% { transform: scale(0.95); opacity: 0.8; }
  50% { transform: scale(1.15); opacity: 1; }
  100% { transform: scale(0.95); opacity: 0.8; }
}

.pill-text {
  display: flex;
  flex-direction: column;
}

.pill-text .label {
  font-size: 0.7rem;
  color: #9FB3C8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.pill-text .val {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1.15rem;
  font-weight: 700;
  color: #FFFFFF;
}

.pill-text .sub {
  font-size: 0.65rem;
  color: #00FF66;
  font-weight: 600;
}

/* Metrics Grid */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.25rem;
}

.metric-card {
  background: rgba(15, 26, 36, 0.85);
  border: 1px solid rgba(51, 78, 104, 0.4);
  border-radius: 10px;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  backdrop-filter: blur(8px);
}

.card-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.75rem;
  color: #9FB3C8;
  font-weight: 600;
  letter-spacing: 0.05em;
}

.tag {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-weight: 600;
}

.live-tag {
  background: rgba(0, 229, 255, 0.15);
  color: #00E5FF;
}

.speed-tag {
  background: rgba(0, 255, 102, 0.15);
  color: #00FF66;
}

.tnb-tag {
  background: rgba(255, 145, 0, 0.15);
  color: #FF9100;
}

.card-hero-val {
  font-family: 'JetBrains Mono', monospace;
  font-size: 2.1rem;
  font-weight: 800;
  color: #FFFFFF;
}

.card-hero-val .unit {
  font-size: 0.95rem;
  color: #9FB3C8;
  font-weight: 500;
}

.accent-cyan {
  color: #00E5FF;
}

.accent-green {
  color: #00FF66;
}

.card-hero-val.alert {
  color: #FF9100;
}

.card-sub-info {
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
  color: #9FB3C8;
}

.pill-mini {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  color: #627D98;
}

.progress-bar-wrap {
  width: 100%;
  height: 6px;
  background: rgba(30, 41, 59, 0.8);
  border-radius: 3px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: #00E5FF;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.progress-bar.cyan {
  background: #00E5FF;
}

.progress-bar.warning {
  background: #FF9100;
}

.progress-bar.danger {
  background: #FF1744;
}

.savings-pct-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: #00FF66;
  background: rgba(0, 255, 102, 0.1);
  padding: 0.3rem 0.5rem;
  border-radius: 4px;
  text-align: center;
  font-weight: 600;
}

/* Charts */
.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.25rem;
}

.chart-card {
  background: rgba(15, 26, 36, 0.85);
  border: 1px solid rgba(51, 78, 104, 0.4);
  border-radius: 10px;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 0.75rem;
}

.chart-header h3 {
  margin: 0;
  font-size: 1.05rem;
  color: #FFFFFF;
}

.chart-subtitle {
  font-size: 0.75rem;
  color: #829AB1;
  margin: 0.2rem 0 0 0;
}

.formula-chip {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  background: rgba(0, 229, 255, 0.15);
  color: #00E5FF;
}

.chart-container {
  height: 280px;
  width: 100%;
}

.chart-footer-note {
  font-size: 0.78rem;
  color: #9FB3C8;
  background: rgba(11, 22, 34, 0.6);
  border-left: 3px solid #00E5FF;
  padding: 0.5rem 0.75rem;
  border-radius: 0 6px 6px 0;
  margin-top: 0.5rem;
}

/* History Card */
.history-card {
  background: rgba(15, 26, 36, 0.85);
  border: 1px solid rgba(51, 78, 104, 0.4);
  border-radius: 10px;
  padding: 1.25rem;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.25rem;
}

.history-header h3 {
  margin: 0;
  font-size: 1.05rem;
  color: #FFFFFF;
}

.days-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  background: rgba(0, 229, 255, 0.15);
  color: #00E5FF;
  padding: 0.25rem 0.6rem;
  border-radius: 6px;
}

.history-stats-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 1rem;
}

.stat-box {
  background: rgba(11, 22, 34, 0.7);
  border: 1px solid rgba(51, 78, 104, 0.3);
  border-radius: 8px;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.stat-box.highlight-rm {
  border-color: rgba(0, 255, 102, 0.4);
  background: rgba(0, 255, 102, 0.05);
}

.stat-box .label {
  font-size: 0.7rem;
  color: #829AB1;
  text-transform: uppercase;
}

.stat-box .val {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1.35rem;
  font-weight: 700;
  color: #FFFFFF;
}

.stat-box.highlight-rm .val {
  color: #00FF66;
}

.stat-box .sub {
  font-size: 0.68rem;
  color: #627D98;
}
</style>
