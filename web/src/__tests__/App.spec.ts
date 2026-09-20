import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'

import App from '../App.vue'
import router from '../router'

describe('App', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo) => {
        const url = String(input)
        if (url.includes('/api/kb')) {
          return {
            ok: true,
            json: async () => ({
              total: 215,
              counts: { frontend: 120, agent: 45, backend: 50 },
            }),
          }
        }
        return { ok: true, json: async () => ({ ok: true }) }
      }),
    )
  })

  it('shows the chat shell when the backend is reachable', async () => {
    const wrapper = mount(App, {
      global: { plugins: [createPinia(), router] },
    })
    await router.isReady()
    await flushPromises()
    expect(wrapper.text()).toContain('新建对话')
    expect(wrapper.text()).toContain('长期记忆')
    expect(wrapper.text()).toContain('知识库')
    expect(wrapper.text()).toContain('MCP')
    expect(wrapper.text()).toContain('后端已连接')
    expect(wrapper.text()).toContain('新对话')
    expect(wrapper.text()).toContain('复制')
    expect(wrapper.text()).toContain('导出')
  })
})
