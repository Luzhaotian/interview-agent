import { describe, expect, it } from 'vitest'

import { renderMarkdown } from '../lib/markdown'

describe('renderMarkdown', () => {
  it('renders bold and lists', () => {
    const html = renderMarkdown('**标题**\n\n- 第一项\n- 第二项')
    expect(html).toContain('<strong>标题</strong>')
    expect(html).toContain('<li>')
    expect(html).toContain('第一项')
  })
})
