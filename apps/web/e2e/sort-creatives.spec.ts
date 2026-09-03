// Pure logic for the creative grid. No browser — Playwright is just the runner here,
// so this needs no new dependency.
import { expect, test } from '@playwright/test'
import { DEFAULT_WINDOW_MONTHS, sortCreatives, withinMonths } from '../lib/sortCreatives'
import type { Creative } from '../lib/types'

const NOW = new Date('2026-09-03T00:00:00Z')

function c(over: Partial<Creative>): Creative {
  return {
    id: 1, competitor_id: 1, creative_id: 'CR', format: 'text', platform: null,
    target_domain: null, image_url: null, details_url: null,
    first_shown: null, last_shown: null, active: true,
    first_seen_run_id: 1, last_seen_run_id: 1, text: null,
    ...over,
  }
}

test.describe('the six-month window', () => {
  test('keeps a creative shown inside the window', () => {
    const rows = [c({ creative_id: 'recent', last_shown: '2026-08-01' })]
    expect(withinMonths(rows, DEFAULT_WINDOW_MONTHS, NOW).map((r) => r.creative_id)).toEqual(['recent'])
  })

  test('drops a creative last shown before the window', () => {
    // A large advertiser carries years of history — one live account returned a
    // creative with 947 days of run — and showing all of it buries what is live now.
    const rows = [c({ creative_id: 'stale', last_shown: '2024-01-01' })]
    expect(withinMonths(rows, DEFAULT_WINDOW_MONTHS, NOW)).toEqual([])
  })

  test('keeps a creative with no last_shown rather than hiding it', () => {
    // We cannot date it. Dropping data because a field is missing is how a grid ends
    // up lying about what an advertiser is running.
    const rows = [c({ creative_id: 'undated', last_shown: null })]
    expect(withinMonths(rows, DEFAULT_WINDOW_MONTHS, NOW).map((r) => r.creative_id)).toEqual(['undated'])
  })

  test('keeps a creative whose date will not parse', () => {
    const rows = [c({ creative_id: 'junk', last_shown: 'not-a-date' })]
    expect(withinMonths(rows, DEFAULT_WINDOW_MONTHS, NOW).map((r) => r.creative_id)).toEqual(['junk'])
  })

  test('the boundary is inclusive', () => {
    const rows = [c({ creative_id: 'edge', last_shown: '2026-03-03' })]
    expect(withinMonths(rows, DEFAULT_WINDOW_MONTHS, NOW).map((r) => r.creative_id)).toEqual(['edge'])
  })
})

test.describe('sorting', () => {
  const rows = [
    c({ creative_id: 'a', last_shown: '2026-01-01', total_days_shown: 10, format: 'text' }),
    c({ creative_id: 'b', last_shown: '2026-06-01', total_days_shown: 200, format: 'image' }),
    c({ creative_id: 'c', last_shown: '2026-03-01', total_days_shown: 50, format: 'text' }),
  ]

  test('descending on last shown puts the most recent first', () => {
    expect(sortCreatives(rows, 'last_shown', 'desc').map((r) => r.creative_id)).toEqual(['b', 'c', 'a'])
  })

  test('ascending on last shown reverses it', () => {
    expect(sortCreatives(rows, 'last_shown', 'asc').map((r) => r.creative_id)).toEqual(['a', 'c', 'b'])
  })

  test('descending on days running finds the longest-serving creative', () => {
    expect(sortCreatives(rows, 'total_days_shown', 'desc').map((r) => r.creative_id)).toEqual(['b', 'c', 'a'])
  })

  test('format sorts alphabetically', () => {
    expect(sortCreatives(rows, 'format', 'asc').map((r) => r.format)).toEqual(['image', 'text', 'text'])
  })

  test('missing values sort last in both directions', () => {
    // An undated creative is not "the oldest", it is unknown. Letting it lead an
    // ascending sort would put the least informative rows first in both directions.
    const withGap = [...rows, c({ creative_id: 'unknown', last_shown: null })]
    expect(sortCreatives(withGap, 'last_shown', 'asc').at(-1)?.creative_id).toBe('unknown')
    expect(sortCreatives(withGap, 'last_shown', 'desc').at(-1)?.creative_id).toBe('unknown')
  })

  test('the input array is not mutated', () => {
    const before = rows.map((r) => r.creative_id)
    sortCreatives(rows, 'last_shown', 'asc')
    expect(rows.map((r) => r.creative_id)).toEqual(before)
  })
})
