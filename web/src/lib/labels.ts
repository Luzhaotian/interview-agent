export const labels: Record<string, string> = {
  frontend: '前端',
  agent: 'Agent',
  backend: '后端',
  easy: '简单',
  medium: '中等',
  hard: '困难',
  foundation: '基础',
  framework: '框架',
  architecture: '架构经验',
  experience: '过往经历',
}

export const stageOrder = ['foundation', 'framework', 'architecture', 'experience'] as const

export function label(value: string) {
  return labels[value] || value
}
