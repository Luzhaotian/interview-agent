import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import App from '../App.vue'

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo) => {
        const url = String(input)
        if (url.includes('/api/kb')) {
          return {
            ok: true,
            json: async () => ({
              total: 137,
              counts: { frontend: 82, agent: 25, backend: 30 },
            }),
          }
        }
        return { ok: true, json: async () => ({ ok: true }) }
      }),
    )
  })

  it('shows the backend is reachable', async () => {
    const wrapper = mount(App)
    await flushPromises()
    expect(wrapper.text()).toContain('面试题推荐')
    expect(wrapper.text()).toContain('后端已连接')
  })
})
