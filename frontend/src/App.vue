<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useAquaStore } from './store'
import LiveVisionView from './views/LiveVisionView.vue'
import EsgView from './views/EsgView.vue'
import WaterView from './views/WaterView.vue'
import ResidentView from './views/ResidentView.vue'

const store = useAquaStore()

onMounted(async () => {
  await store.init()
})

const tabs = [
  { id: 'vision', label: 'Live Vision & Agentic Reflex', icon: '👁️', track: 'TRACK 1 & 2' },
  { id: 'esg', label: 'ESG & VFD Pump Eco-Drive', icon: '⚡', track: 'PLANET' },
  { id: 'water', label: 'Water Clarity & Monsoon', icon: '🌊', track: 'OPERATIONS' },
  { id: 'resident', label: 'Resident Township Widget', icon: '📱', track: 'PEOPLE' },
] as const

const overallState = computed(() => store.overallState)
const latencyMs = computed(() => {
  if (store.mode === 'scenario') {
    return store.scenarioData?.system1_trace?.execution_latency_ms ?? 11.2
  }
  return store.currentFrame?.system1_trace?.execution_latency_ms ?? 12.8
})
</script>

<template>
  <div class="aquapulse-root">
    <!-- Master Top Header Bar -->
    <header class="master-header">
      <!-- Left: Logo & Hackathon Identity -->
      <div class="header-left">
        <div class="brand-cluster">
          <div class="brand-logo">
            <span class="logo-pulse-circle"></span>
            <span class="logo-text">AquaPulse</span>
          </div>
          <div class="hackathon-tag">
            <span class="sime-darby-pill">SIME DARBY PROPERTY</span>
            <span class="township-label">Township of Tomorrow Hackathon</span>
          </div>
        </div>
      </div>

      <!-- Center: 4-Tab Navigation -->
      <nav class="header-nav">
        <button
          v-for="t in tabs"
          :key="t.id"
          class="nav-tab-btn"
          :class="{ active: store.activeTab === t.id }"
          @click="store.activeTab = t.id as any"
        >
          <span class="tab-icon">{{ t.icon }}</span>
          <div class="tab-info">
            <span class="tab-label">{{ t.label }}</span>
            <span class="tab-track">{{ t.track }}</span>
          </div>
        </button>
      </nav>

      <!-- Right: System Status & Audio Toggle -->
      <div class="header-right">
        <!-- Live State Pill -->
        <div class="state-indicator" :class="overallState.toLowerCase()">
          <span class="dot"></span>
          <span class="state-text">{{ overallState.replace(/_/g, ' ') }}</span>
        </div>

        <!-- Latency Badge -->
        <div class="latency-pill" title="System 1 Fast Reflex Loop Latency (<30ms SLA)">
          <span class="mono">{{ latencyMs.toFixed(1) }}ms</span>
          <span class="sub">SYS 1 REFLEX</span>
        </div>

        <!-- Audio Mute / Unmute Button -->
        <button
          class="audio-toggle-btn"
          :class="{ muted: store.isMuted }"
          @click="store.isMuted = !store.isMuted"
          :title="store.isMuted ? 'Poolside Audio Muted' : 'Poolside Audio Active'"
        >
          {{ store.isMuted ? '🔇' : '🔊' }}
        </button>
      </div>
    </header>

    <!-- Error Banner if any -->
    <div v-if="store.error" class="global-error-banner">
      <span>⚠️ {{ store.error }}</span>
      <button class="dismiss-btn" @click="store.error = null">&times;</button>
    </div>

    <!-- Main Viewport with KeepAlive for State Preservation -->
    <main class="master-main">
      <KeepAlive>
        <component
          :is="
            store.activeTab === 'vision'
              ? LiveVisionView
              : store.activeTab === 'esg'
              ? EsgView
              : store.activeTab === 'water'
              ? WaterView
              : ResidentView
          "
        />
      </KeepAlive>
    </main>

    <!-- Master Footer -->
    <footer class="master-footer">
      <div class="footer-left">
        <span><b>AquaPulse</b> &bull; Privacy-First Agentic Vision & ESG Monitoring System</span>
        <span class="sub-credit">Sime Darby Property University Hackathon &bull; People & Planet Tracks</span>
      </div>
      <div class="footer-right">
        <span class="pdpa-badge">
          🛡️ Malaysia PDPA 2010 & Amendment Act 2024 Compliant (Tier-2 Skeletal Silhouette Engine)
        </span>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.aquapulse-root {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #081018;
  color: #E0F2FE;
  font-family: 'Outfit', sans-serif;
}

/* Master Header */
.master-header {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 2rem;
  background: rgba(11, 22, 34, 0.95);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(0, 229, 255, 0.2);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
}

.header-left {
  display: flex;
  align-items: center;
}

.brand-cluster {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.brand-logo {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.logo-pulse-circle {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #00E5FF;
  box-shadow: 0 0 10px #00E5FF;
  animation: logo-glow 2s infinite ease-in-out;
}

@keyframes logo-glow {
  0% { transform: scale(0.9); opacity: 0.7; }
  50% { transform: scale(1.15); opacity: 1; filter: drop-shadow(0 0 6px #00E5FF); }
  100% { transform: scale(0.9); opacity: 0.7; }
}

.logo-text {
  font-size: 1.45rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  background: linear-gradient(90deg, #FFFFFF 30%, #00E5FF 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.hackathon-tag {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.7rem;
}

.sime-darby-pill {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.62rem;
  font-weight: 700;
  background: rgba(255, 23, 68, 0.15);
  color: #FF5252;
  border: 1px solid rgba(255, 23, 68, 0.35);
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
  letter-spacing: 0.05em;
}

.township-label {
  color: #829AB1;
}

/* Nav Tabs */
.header-nav {
  display: flex;
  gap: 0.5rem;
  background: rgba(15, 26, 36, 0.8);
  padding: 0.3rem;
  border-radius: 10px;
  border: 1px solid rgba(51, 78, 104, 0.4);
}

.nav-tab-btn {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 0.5rem 0.9rem;
  color: #9FB3C8;
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: left;
}

.nav-tab-btn:hover {
  background: rgba(0, 229, 255, 0.08);
  color: #E0F2FE;
}

.nav-tab-btn.active {
  background: rgba(0, 229, 255, 0.18);
  border-color: rgba(0, 229, 255, 0.5);
  color: #FFFFFF;
  box-shadow: 0 0 12px rgba(0, 229, 255, 0.25);
}

.tab-icon {
  font-size: 1.15rem;
}

.tab-info {
  display: flex;
  flex-direction: column;
}

.tab-label {
  font-size: 0.82rem;
  font-weight: 600;
  line-height: 1.2;
}

.tab-track {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  color: #00E5FF;
  letter-spacing: 0.05em;
}

/* Header Right */
.header-right {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.state-indicator {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  font-weight: 700;
}

.state-indicator .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.state-indicator.normal {
  background: rgba(0, 255, 102, 0.15);
  color: #00FF66;
  border: 1px solid rgba(0, 255, 102, 0.4);
}
.state-indicator.normal .dot { background: #00FF66; box-shadow: 0 0 6px #00FF66; }

.state-indicator.verify {
  background: rgba(255, 234, 0, 0.15);
  color: #FFEA00;
  border: 1px solid rgba(255, 234, 0, 0.4);
}
.state-indicator.verify .dot { background: #FFEA00; box-shadow: 0 0 6px #FFEA00; animation: blink 1s infinite; }

.state-indicator.critical_emergency {
  background: rgba(255, 23, 68, 0.25);
  color: #FF1744;
  border: 1px solid #FF1744;
  box-shadow: 0 0 10px rgba(255, 23, 68, 0.4);
}
.state-indicator.critical_emergency .dot { background: #FF1744; box-shadow: 0 0 8px #FF1744; animation: blink 0.5s infinite; }

.state-indicator.nudge_required {
  background: rgba(255, 145, 0, 0.2);
  color: #FF9100;
  border: 1px solid #FF9100;
}
.state-indicator.nudge_required .dot { background: #FF9100; }

@keyframes blink {
  0% { opacity: 0.3; }
  50% { opacity: 1; }
  100% { opacity: 0.3; }
}

.latency-pill {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  background: rgba(11, 22, 34, 0.8);
  border: 1px solid rgba(51, 78, 104, 0.4);
  padding: 0.25rem 0.55rem;
  border-radius: 6px;
}

.latency-pill .mono {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  font-weight: 700;
  color: #00FF66;
}

.latency-pill .sub {
  font-size: 0.55rem;
  color: #829AB1;
  letter-spacing: 0.05em;
}

.audio-toggle-btn {
  background: rgba(15, 26, 36, 0.8);
  border: 1px solid rgba(51, 78, 104, 0.4);
  color: #FFFFFF;
  border-radius: 8px;
  font-size: 1.15rem;
  padding: 0.4rem 0.65rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.audio-toggle-btn:hover {
  background: rgba(0, 229, 255, 0.15);
  border-color: #00E5FF;
}

.audio-toggle-btn.muted {
  opacity: 0.6;
}

/* Global Error Banner */
.global-error-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(255, 23, 68, 0.2);
  border-bottom: 1px solid #FF1744;
  color: #FF80AB;
  padding: 0.5rem 2rem;
  font-size: 0.85rem;
}

.dismiss-btn {
  background: transparent;
  border: none;
  color: #FF80AB;
  font-size: 1.25rem;
  cursor: pointer;
}

/* Master Main */
.master-main {
  flex: 1;
  max-width: 1600px;
  width: 100%;
  margin: 0 auto;
  padding: 1.5rem 2rem 2.5rem 2rem;
}

/* Master Footer */
.master-footer {
  margin-top: auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  background: rgba(11, 22, 34, 0.95);
  border-top: 1px solid rgba(51, 78, 104, 0.3);
  font-size: 0.78rem;
  color: #829AB1;
}

.footer-left {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.sub-credit {
  font-size: 0.7rem;
  color: #627D98;
}

.pdpa-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  color: #00E5FF;
  background: rgba(0, 229, 255, 0.08);
  border: 1px solid rgba(0, 229, 255, 0.2);
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
}
</style>
