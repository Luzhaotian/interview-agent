export type KbQuestion = {
  id: string
  category: string
  topic: string
  tags: string[]
  difficulty: string
  question: string
  answer_outline: string
}

export type KbFilterState = {
  category: string
  difficulties: string[]
  tags: string[]
  keyword: string
}

export const KB_CATEGORIES = [
  { id: 'all', name: '全部' },
  { id: 'frontend', name: '前端' },
  { id: 'agent', name: 'Agent' },
  { id: 'backend', name: '后端' },
] as const

export const KB_DIFFICULTIES = [
  { id: 'easy', name: '简单' },
  { id: 'medium', name: '中等' },
  { id: 'hard', name: '困难' },
] as const

export function emptyKbFilters(): KbFilterState {
  return { category: 'all', difficulties: [], tags: [], keyword: '' }
}

export function hasActiveKbFilters(filters: KbFilterState): boolean {
  return (
    filters.category !== 'all' ||
    filters.difficulties.length > 0 ||
    filters.tags.length > 0 ||
    filters.keyword.trim().length > 0
  )
}

function matchesKeyword(item: KbQuestion, needle: string): boolean {
  if (!needle) return true
  const haystack = [item.question, item.topic, item.id, item.tags.join(' ')].join(' ').toLowerCase()
  return haystack.includes(needle)
}

function matchesCategory(item: KbQuestion, category: string): boolean {
  return category === 'all' || item.category === category
}

function matchesDifficulties(item: KbQuestion, difficulties: string[]): boolean {
  return difficulties.length === 0 || difficulties.includes(item.difficulty)
}

/** Tags use AND: item must include every selected tag. */
function matchesTags(item: KbQuestion, tags: string[]): boolean {
  return tags.every((tag) => item.tags.includes(tag))
}

export function filterQuestions(questions: KbQuestion[], filters: KbFilterState): KbQuestion[] {
  const needle = filters.keyword.trim().toLowerCase()
  return questions.filter(
    (item) =>
      matchesCategory(item, filters.category) &&
      matchesDifficulties(item, filters.difficulties) &&
      matchesTags(item, filters.tags) &&
      matchesKeyword(item, needle),
  )
}

export type KbFacetCounts = {
  categories: Record<string, number>
  difficulties: Record<string, number>
  tags: Record<string, number>
}

/**
 * Faceted counts: each option is counted under all other active dimensions,
 * ignoring the dimension being counted (except other selected tags stay on
 * when counting a single tag).
 */
export function facetCounts(questions: KbQuestion[], filters: KbFilterState): KbFacetCounts {
  const needle = filters.keyword.trim().toLowerCase()

  const categories: Record<string, number> = { all: 0 }
  for (const item of questions) {
    if (
      matchesDifficulties(item, filters.difficulties) &&
      matchesTags(item, filters.tags) &&
      matchesKeyword(item, needle)
    ) {
      categories.all = (categories.all ?? 0) + 1
      categories[item.category] = (categories[item.category] || 0) + 1
    }
  }

  const difficulties: Record<string, number> = {}
  for (const item of questions) {
    if (
      matchesCategory(item, filters.category) &&
      matchesTags(item, filters.tags) &&
      matchesKeyword(item, needle)
    ) {
      difficulties[item.difficulty] = (difficulties[item.difficulty] || 0) + 1
    }
  }

  const tags: Record<string, number> = {}
  const tagUniverse = new Set<string>()
  for (const item of questions) {
    for (const tag of item.tags) tagUniverse.add(tag)
  }

  for (const tag of tagUniverse) {
    const otherTags = filters.tags.filter((t) => t !== tag)
    let count = 0
    for (const item of questions) {
      if (!item.tags.includes(tag)) continue
      if (
        matchesCategory(item, filters.category) &&
        matchesDifficulties(item, filters.difficulties) &&
        matchesTags(item, otherTags) &&
        matchesKeyword(item, needle)
      ) {
        count += 1
      }
    }
    tags[tag] = count
  }

  return { categories, difficulties, tags }
}

export function tagFrequency(questions: KbQuestion[]): { name: string; count: number }[] {
  const freq: Record<string, number> = {}
  for (const item of questions) {
    for (const tag of item.tags) {
      freq[tag] = (freq[tag] || 0) + 1
    }
  }
  return Object.entries(freq)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, 'zh'))
}

export function toggleInList(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value]
}
