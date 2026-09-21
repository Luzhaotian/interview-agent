import { describe, expect, it } from 'vitest'

import {
  emptyKbFilters,
  facetCounts,
  filterQuestions,
  hasActiveKbFilters,
  tagFrequency,
  toggleInList,
  type KbQuestion,
} from '../lib/kbFilter'

const sample: KbQuestion[] = [
  {
    id: 'fe-vue-1',
    category: 'frontend',
    topic: 'Vue',
    tags: ['vue', '性能'],
    difficulty: 'medium',
    question: 'Vue 响应式原理？',
    answer_outline: 'Proxy',
  },
  {
    id: 'fe-css-1',
    category: 'frontend',
    topic: 'CSS',
    tags: ['css'],
    difficulty: 'easy',
    question: 'BFC 是什么？',
    answer_outline: '块级格式化上下文',
  },
  {
    id: 'ag-rag-1',
    category: 'agent',
    topic: 'RAG',
    tags: ['rag', 'agent'],
    difficulty: 'hard',
    question: '如何做混合检索？',
    answer_outline: '向量 + BM25',
  },
  {
    id: 'be-sql-1',
    category: 'backend',
    topic: '数据库',
    tags: ['sql', 'mysql'],
    difficulty: 'medium',
    question: '索引失效场景？',
    answer_outline: '函数、类型转换',
  },
]

describe('filterQuestions', () => {
  it('returns all when filters empty', () => {
    expect(filterQuestions(sample, emptyKbFilters())).toHaveLength(4)
  })

  it('filters by category', () => {
    const result = filterQuestions(sample, { ...emptyKbFilters(), category: 'frontend' })
    expect(result.map((q) => q.id)).toEqual(['fe-vue-1', 'fe-css-1'])
  })

  it('filters difficulties with OR', () => {
    const result = filterQuestions(sample, {
      ...emptyKbFilters(),
      difficulties: ['easy', 'hard'],
    })
    expect(result.map((q) => q.id).sort()).toEqual(['ag-rag-1', 'fe-css-1'])
  })

  it('filters tags with AND', () => {
    const one = filterQuestions(sample, { ...emptyKbFilters(), tags: ['vue'] })
    expect(one.map((q) => q.id)).toEqual(['fe-vue-1'])

    const both = filterQuestions(sample, { ...emptyKbFilters(), tags: ['vue', '性能'] })
    expect(both.map((q) => q.id)).toEqual(['fe-vue-1'])

    const miss = filterQuestions(sample, { ...emptyKbFilters(), tags: ['vue', 'css'] })
    expect(miss).toHaveLength(0)
  })

  it('matches keyword across question topic id tags', () => {
    expect(filterQuestions(sample, { ...emptyKbFilters(), keyword: 'BFC' })).toHaveLength(1)
    expect(filterQuestions(sample, { ...emptyKbFilters(), keyword: 'fe-vue' })).toHaveLength(1)
    expect(filterQuestions(sample, { ...emptyKbFilters(), keyword: 'mysql' })).toHaveLength(1)
    expect(filterQuestions(sample, { ...emptyKbFilters(), keyword: '  ' })).toHaveLength(4)
  })

  it('combines dimensions with AND', () => {
    const result = filterQuestions(sample, {
      category: 'frontend',
      difficulties: ['medium'],
      tags: ['vue'],
      keyword: '响应式',
    })
    expect(result.map((q) => q.id)).toEqual(['fe-vue-1'])
  })
})

describe('facetCounts', () => {
  it('counts categories under other filters', () => {
    const counts = facetCounts(sample, { ...emptyKbFilters(), difficulties: ['medium'] })
    expect(counts.categories.all).toBe(2)
    expect(counts.categories.frontend).toBe(1)
    expect(counts.categories.backend).toBe(1)
    expect(counts.categories.agent || 0).toBe(0)
  })

  it('counts difficulties ignoring difficulty selection', () => {
    const counts = facetCounts(sample, {
      ...emptyKbFilters(),
      category: 'frontend',
      difficulties: ['easy'],
    })
    expect(counts.difficulties.easy).toBe(1)
    expect(counts.difficulties.medium).toBe(1)
    expect(counts.difficulties.hard || 0).toBe(0)
  })

  it('counts a tag while keeping other selected tags', () => {
    const counts = facetCounts(sample, { ...emptyKbFilters(), tags: ['vue'] })
    expect(counts.tags['性能']).toBe(1)
    expect(counts.tags.css).toBe(0)
    expect(counts.tags.vue).toBe(1)
  })
})

describe('helpers', () => {
  it('detects active filters', () => {
    expect(hasActiveKbFilters(emptyKbFilters())).toBe(false)
    expect(hasActiveKbFilters({ ...emptyKbFilters(), category: 'agent' })).toBe(true)
    expect(hasActiveKbFilters({ ...emptyKbFilters(), keyword: 'x' })).toBe(true)
  })

  it('toggles list membership', () => {
    expect(toggleInList(['a'], 'b')).toEqual(['a', 'b'])
    expect(toggleInList(['a', 'b'], 'a')).toEqual(['b'])
  })

  it('ranks tags by frequency', () => {
    const ranked = tagFrequency(sample)
    expect(ranked.length).toBeGreaterThan(0)
    const first = ranked[0]!
    const last = ranked[ranked.length - 1]!
    expect(first.count).toBeGreaterThanOrEqual(last.count)
    expect(ranked.map((t) => t.name)).toContain('vue')
  })
})
