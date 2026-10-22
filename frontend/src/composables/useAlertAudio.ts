import { ref, watch, type Ref } from 'vue'
import { api } from '../api'
import type { TimelineEvent } from '../types/aquapulse'

export function useAlertAudio(
  eventsRef: Ref<TimelineEvent[]>,
  playheadSec: Ref<number>,
  isMuted: Ref<boolean>
) {
  const isAudioUnlocked = ref(false)
  const lastPlayhead = ref(0)
  const firedEvents = ref(new Set<string>())

  function unlockAudio() {
    isAudioUnlocked.value = true
    // Prime audio context with a silent sound
    try {
      const a = new Audio()
      a.play().catch(() => {})
      if ('speechSynthesis' in window) {
        window.speechSynthesis.getVoices()
      }
    } catch {}
  }

  function playAlertSound(kind: 'critical_siren' | 'verify_beacon' | 'polite_nudge') {
    if (isMuted.value || !isAudioUnlocked.value) return
    try {
      const audio = new Audio(api.audioUrl(kind))
      audio.volume = kind === 'critical_siren' ? 1.0 : 0.75
      audio.play().catch(() => {})
    } catch {}
  }

  function speakTts(text: string) {
    if (isMuted.value || !isAudioUnlocked.value) return
    if ('speechSynthesis' in window && text) {
      try {
        window.speechSynthesis.cancel()
        const utterance = new SpeechSynthesisUtterance(text)
        utterance.rate = 1.05
        utterance.pitch = 1.0
        // Prefer English/Malay voice if available
        const voices = window.speechSynthesis.getVoices()
        const matchVoice = voices.find(v => v.lang.startsWith('en') || v.lang.startsWith('ms'))
        if (matchVoice) utterance.voice = matchVoice
        window.speechSynthesis.speak(utterance)
      } catch {}
    }
  }

  watch(playheadSec, (curr, prev) => {
    // If seeked backward by more than 1.5s, reset fired set so events can re-trigger on replay
    if (curr < prev - 1.5) {
      firedEvents.value.clear()
    }
    lastPlayhead.value = curr

    if (!isAudioUnlocked.value || isMuted.value) return

    const events = eventsRef.value
    for (const ev of events) {
      const evKey = `${ev.t}_${ev.kind}_${ev.track_id || 0}`
      if (curr >= ev.t && curr - ev.t <= 1.2 && !firedEvents.value.has(evKey)) {
        firedEvents.value.add(evKey)

        if (ev.kind.includes('siren') || ev.kind.includes('emergency')) {
          playAlertSound('critical_siren')
          if (ev.audio_tts_text) {
            setTimeout(() => speakTts(ev.audio_tts_text!), 1200)
          }
        } else if (ev.kind.includes('beacon') || ev.kind.includes('caution')) {
          playAlertSound('verify_beacon')
        } else if (ev.kind.includes('nudge') || ev.kind.includes('speaker')) {
          playAlertSound('polite_nudge')
          if (ev.audio_tts_text) {
            setTimeout(() => speakTts(ev.audio_tts_text!), 800)
          }
        }
      }
    }
  })

  return {
    isAudioUnlocked,
    unlockAudio,
    playAlertSound,
    speakTts,
  }
}
