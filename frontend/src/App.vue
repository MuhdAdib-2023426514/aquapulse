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
  { id: 'vision', label: 'Monitoring' },
  { id: 'esg', label: 'Operations' },
  { id: 'water', label: 'Water check' },
  { id: 'resident', label: 'Resident preview' },
] as const

const modelStatus = computed(() => {
  if (store.capabilities === null) return 'AI status unavailable'
  return store.capabilities.yolo26_pose_available ? 'Pose weight file present' : 'Pose weights missing'
})
</script>

<template>
  <div class="aquapulse-root">
    <!-- Master Top Header Bar -->
    <header class="master-header">
      <!-- Brand -->
      <div class="header-left">
        <div class="brand-logo">
          <span class="logo-pulse-circle" aria-hidden="true"></span>
          <span class="logo-text">AquaPulse</span>
          <span class="prototype-label">Pool prototype</span>
        </div>
      </div>

      <!-- Center: 4-Tab Navigation -->
      <nav class="header-nav" aria-label="Main navigation">
        <button
          v-for="t in tabs"
          :key="t.id"
          class="nav-tab-btn"
          :class="{ active: store.activeTab === t.id }"
          :aria-current="store.activeTab === t.id ? 'page' : undefined"
          @click="store.activeTab = t.id as any"
        >
          <span class="menu-symbol" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
            <template v-if="t.id === 'vision'"><rect x="3" y="4" width="18" height="13" rx="3"/><path d="M8 21h8m-4-4v4m-5-10 3 2 4-4 3 2"/></template>
            <path v-else-if="t.id === 'esg'" d="m13 2-9 12h7l-1 8 10-13h-7z"/>
            <template v-else-if="t.id === 'water'"><path d="M12 3s-7 7-7 12a7 7 0 0 0 14 0c0-5-7-12-7-12Z"/><path d="M9 15a3 3 0 0 0 3 3"/></template>
            <template v-else><path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1Z"/><path d="M9 21v-8h6v8"/></template>
          </svg></span><span class="tab-label">{{ t.label }}</span><span class="menu-dot" aria-hidden="true"></span>
        </button>
      </nav>

      <!-- Runtime status -->
      <div class="header-right">
        <span class="model-status">{{ modelStatus }}</span>

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

    <!-- Prototype boundary -->
    <footer class="master-footer">
      <span>AquaPulse · experimental local prototype</span>
      <span>Analysis cues are unvalidated. Keep a person responsible for pool safety.</span>
    </footer>
  </div>
</template>

<style scoped>
.aquapulse-root {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #F5F8F9;
  color: #213D46;
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
  background: #176776;
  box-shadow: 0 0 10px #176776;
  animation: logo-glow 2s infinite ease-in-out;
}

@keyframes logo-glow {
  0% { transform: scale(0.9); opacity: 0.7; }
  50% { transform: scale(1.15); opacity: 1; filter: drop-shadow(0 0 6px #176776); }
  100% { transform: scale(0.9); opacity: 0.7; }
}

.logo-text {
  font-size: 1.45rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  background: linear-gradient(90deg, #FFFFFF 30%, #176776 100%);
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
  color: #A34E42;
  border: 1px solid rgba(255, 23, 68, 0.35);
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
  letter-spacing: 0.05em;
}

.township-label {
  color: #617981;
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
  color: #5F737A;
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: left;
}

.nav-tab-btn:hover {
  background: rgba(0, 229, 255, 0.08);
  color: #213D46;
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
  color: #176776;
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
  color: #397A68;
  border: 1px solid rgba(0, 255, 102, 0.4);
}
.state-indicator.normal .dot { background: #397A68; box-shadow: 0 0 6px #397A68; }

.state-indicator.verify {
  background: rgba(255, 234, 0, 0.15);
  color: #B1782A;
  border: 1px solid rgba(255, 234, 0, 0.4);
}
.state-indicator.verify .dot { background: #B1782A; box-shadow: 0 0 6px #B1782A; animation: blink 1s infinite; }

.state-indicator.critical_emergency {
  background: rgba(255, 23, 68, 0.25);
  color: #A34E42;
  border: 1px solid #A34E42;
  box-shadow: 0 0 10px rgba(255, 23, 68, 0.4);
}
.state-indicator.critical_emergency .dot { background: #A34E42; box-shadow: 0 0 8px #A34E42; animation: blink 0.5s infinite; }

.state-indicator.nudge_required {
  background: rgba(255, 145, 0, 0.2);
  color: #A56535;
  border: 1px solid #A56535;
}
.state-indicator.nudge_required .dot { background: #A56535; }

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
  color: #397A68;
}

.latency-pill .sub {
  font-size: 0.55rem;
  color: #617981;
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
  border-color: #176776;
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
  border-bottom: 1px solid #A34E42;
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
  color: #617981;
}

.footer-left {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.sub-credit {
  font-size: 0.7rem;
  color: #72858B;
}

.pdpa-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  color: #176776;
  background: rgba(0, 229, 255, 0.08);
  border: 1px solid rgba(0, 229, 255, 0.2);
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
}
</style>
