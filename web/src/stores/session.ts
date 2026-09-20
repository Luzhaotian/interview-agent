import { ref } from 'vue'
import { defineStore } from 'pinia'

export type KbStats = {
  total: number
  counts: Record<string, number>
}

export const useSessionStore = defineStore('session', () => {
  const connected = ref(false)
  const statusText = ref('正在连接后端…')
  const kb = ref<KbStats | null>(null)

  async function refresh() {
    try {
      const health = await fetch('/api/health')
      if (!health.ok) throw new Error('health')
      const kbResponse = await fetch('/api/kb')
      if (!kbResponse.ok) throw new Error('kb')
      kb.value = (await kbResponse.json()) as KbStats
      connected.value = true
      statusText.value = '后端已连接'
    } catch {
      connected.value = false
      kb.value = null
      statusText.value = '后端未连接'
    }
  }

  return { connected, statusText, kb, refresh }
})
