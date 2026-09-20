import { describe, expect, it } from 'vitest'

import { transcriptMarkdown, type ChatMessage } from '../lib/transcript'

describe('transcriptMarkdown', () => {
  it('includes stages, direction and reference answers', () => {
    const messages: ChatMessage[] = [
      { id: '1', role: 'user', text: '出题', fileName: 'resume.pdf' },
      {
        id: '2',
        role: 'assistant',
        text: '已选题',
        thinking: ['正在检索知识库'],
        questions: [
          {
            id: 'fe-vue-001',
            category: 'frontend',
            topic: 'Vue',
            difficulty: 'medium',
            stage: 'framework',
            question: '响应式有什么差别？',
            reason: '简历用了 Vue 3',
            answer_direction: '先讲 Proxy，再对比 Vue 2。',
            reference_answer: 'Vue 3 用 Proxy。',
          },
        ],
      },
    ]
    const markdown = transcriptMarkdown(messages)
    expect(markdown).toContain('## 你')
    expect(markdown).toContain('resume.pdf')
    expect(markdown).toContain('过程：')
    expect(markdown).toContain('框架')
    expect(markdown).toContain('回答方向：先讲 Proxy')
    expect(markdown).toContain('参考答案：Vue 3 用 Proxy。')
  })

  it('keeps one result per resume', () => {
    const messages: ChatMessage[] = [
      {
        id: '2',
        role: 'assistant',
        text: '',
        reports: [
          {
            key: '1-a.pdf',
            name: 'a.pdf',
            text: '甲的介绍',
            reasoning: '',
            thinking: [],
            questions: [],
            decision: { recommend: true, reasons: ['有企业级 AI 项目'] },
          },
          {
            key: '2-b.pdf',
            name: 'b.pdf',
            text: '乙的介绍',
            reasoning: '',
            thinking: [],
            questions: [],
            decision: { recommend: false, reasons: ['缺少企业级 AI 项目'] },
          },
        ],
      },
    ]
    const markdown = transcriptMarkdown(messages)
    expect(markdown).toContain('a.pdf')
    expect(markdown).toContain('b.pdf')
    expect(markdown).toContain('甲的介绍')
    expect(markdown).toContain('乙的介绍')
    expect(markdown).toContain('推荐面试')
    expect(markdown).toContain('不推荐面试')
    expect(markdown.indexOf('a.pdf')).toBeLessThan(markdown.indexOf('b.pdf'))
  })
})
