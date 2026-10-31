import { describe, expect, it } from 'vitest'

import type { Checkpoint } from '../../api/types'
import { causeOf } from '../CheckpointList'
import { splitExplanation } from '../Results'

const checkpoint = (overrides: Partial<Checkpoint>): Checkpoint => ({
  mile: 0,
  lat: 0,
  lng: 0,
  eta: '2026-10-31T22:00:00Z',
  wind_mph: 0,
  rain_in_hr: 0,
  snow_in_hr: 0,
  risk: 'low',
  conditions: [],
  load_adjusted: false,
  miles: 25,
  forecast_complete: true,
  ...overrides,
})

describe('splitExplanation', () => {
  it('separates the deciding criterion from the tie note', () => {
    expect(splitExplanation('Shortest travel time: 7h 46m vs 7h 50m on Route B (tied on No Travel miles, Severe miles)')).toEqual([
      'Shortest travel time: 7h 46m vs 7h 50m on Route B',
      'Tied on No Travel miles, Severe miles',
    ])
  })

  it('keeps an explanation without ties whole', () => {
    expect(splitExplanation('Fewest Severe miles: 0.0 mi vs 37.5 mi on Route B')).toEqual([
      'Fewest Severe miles: 0.0 mi vs 37.5 mi on Route B',
      null,
    ])
  })
})

describe('causeOf', () => {
  it('names the condition that set the level', () => {
    expect(causeOf(checkpoint({ risk: 'high', conditions: ['snow'], snow_in_hr: 1.26 }))).toBe('Snow 1.3 in/hr')
  })

  it('lists every condition at the worst level', () => {
    expect(causeOf(checkpoint({ risk: 'moderate', conditions: ['wind', 'rain'], wind_mph: 27.4, rain_in_hr: 0.12 }))).toBe(
      'Wind 27 mph and Rain 0.12 in/hr',
    )
  })

  it('mentions the load rule when it raised the wind level', () => {
    expect(causeOf(checkpoint({ risk: 'no_travel', conditions: ['wind'], wind_mph: 48, load_adjusted: true }))).toBe(
      'Wind 48 mph, raised by the load-weight rule',
    )
  })
})
