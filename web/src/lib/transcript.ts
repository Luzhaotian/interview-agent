import { label } from './labels'

export type Profile = {
  years: string
  focus: string
  skills: string[]
  projects: string[]
  summary: string
}

export type Question = {
  id: string
  category: string
  topic: string
  difficulty: string
  stage: string
  question: string
  reason: string
  answer_direction: string
  reference_answer: string
  answer_outline?: string
  source?: string
  source_title?: string
  source_url?: string
}

export type WebCandidate = {
  id: string
  category: string
  topic: string
  tags: string[]
  difficulty: string
  question: string
  answer_outline: string
  source?: string
  source_title?: string
  source_url?: string
}

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  text: string
  fileName?: string
  profile?: Profile
  questions?: Question[]
  thinking?: string[]
  reasoning?: string
  webCandidates?: WebCandidate[]
  decision?: InterviewDecision
  reports?: ResumeReport[]
  streaming?: boolean
  error?: boolean
}

export type InterviewDecision = {
  recommend: boolean
  reasons: string[]
}

export type ResumeReport = {
  key: string
  name: string
  text: string
  reasoning: string
  thinking: string[]
  profile?: Profile
  questions: Question[]
  webCandidates?: WebCandidate[]
  decision?: InterviewDecision
  error?: string
}

export function formatQuestions(questions: Question[]) {
  return questions
    .map((item, index) => {
      const head = `${index + 1}. [${label(item.stage)} / ${label(item.category)} / ${item.topic} / ${label(item.difficulty)}] ${item.question}`
      const reason = item.reason ? `\n为什么问：${item.reason}` : ''
      const direction = item.answer_direction ? `\n回答方向：${item.answer_direction}` : ''
      const reference = item.reference_answer || item.answer_outline || ''
      return `${head}${reason}${direction}\n参考答案：${reference}`
    })
    .join('\n\n')
}

export function formatProfile(profile: Profile) {
  return [
    `方向：${label(profile.focus)}`,
    `年限：${profile.years}`,
    `技能：${profile.skills.join('、') || '未识别'}`,
    `项目：${profile.projects.join('、') || '未识别'}`,
    `摘要：${profile.summary || '无'}`,
  ].join('\n')
}

export function messageText(message: ChatMessage) {
  const parts: string[] = []
  if (message.fileName) parts.push(`简历：${message.fileName}`)
  if (message.reasoning) parts.push(`模型思考：\n${message.reasoning}`)
  if (message.thinking?.length) parts.push(`过程：\n- ${message.thinking.join('\n- ')}`)
  if (message.text) parts.push(message.text)
  if (message.profile) parts.push(formatProfile(message.profile))
  if (message.questions?.length) parts.push(formatQuestions(message.questions))
  if (message.decision) {
    parts.push(message.decision.recommend ? '推荐面试' : '不推荐面试')
    parts.push(message.decision.reasons.map((item) => `- ${item}`).join('\n'))
  }
  if (message.reports?.length) {
    for (const report of message.reports) {
      parts.push(`## ${report.name}`)
      if (report.reasoning) parts.push(`模型思考：\n${report.reasoning}`)
      if (report.thinking.length) parts.push(`过程：\n- ${report.thinking.join('\n- ')}`)
      if (report.text) parts.push(report.text)
      if (report.error) parts.push(report.error)
      if (report.profile) parts.push(formatProfile(report.profile))
      if (report.decision) {
        parts.push(report.decision.recommend ? '推荐面试' : '不推荐面试')
        parts.push(report.decision.reasons.map((item) => `- ${item}`).join('\n'))
      }
      if (report.questions.length) parts.push(formatQuestions(report.questions))
    }
  }
  return parts.join('\n\n')
}

export function transcriptMarkdown(messages: ChatMessage[]) {
  const body = messages
    .filter(
      (message) =>
        message.text ||
        message.fileName ||
        message.questions?.length ||
        message.reports?.length ||
        message.decision,
    )
    .map((message) => {
      const who = message.role === 'user' ? '你' : '助手'
      return `## ${who}\n\n${messageText(message)}`
    })
    .join('\n\n')
  return `# 面试助手对话\n\n${body}\n`
}
