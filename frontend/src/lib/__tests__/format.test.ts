import { describe, expect, it } from 'vitest'

import { formatDuration, nextFullHour, toDateTimeLocal } from '../format'

describe('format helpers', () => {
  it('formats durations', () => {
    expect(formatDuration(41_880)).toBe('11h 38m')
    expect(formatDuration(1_500)).toBe('25m')
    expect(formatDuration(3_600)).toBe('1h 00m')
  })

  it('rounds up to the next full hour for the default departure', () => {
    expect(toDateTimeLocal(nextFullHour(new Date(2026, 10, 2, 9, 41)))).toBe('2026-11-02T10:00')
  })
})
