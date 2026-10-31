import { describe, expect, it } from 'vitest'

import { toTripRequest, validateTrip, type TripFormValues } from '../validation'

const NOW = new Date('2026-11-02T12:00:00').getTime()
const dallas = { label: 'Dallas, Texas, United States', lat: 32.7767, lng: -96.797 }
const houston = { label: 'Houston, Texas, United States', lat: 29.7604, lng: -95.3698 }

const valid = (overrides: Partial<TripFormValues> = {}): TripFormValues => ({
  origin: { text: dallas.label, place: dallas },
  destination: { text: houston.label, place: houston },
  departure: '2026-11-02T14:00',
  load: '42000',
  interval: 25,
  ...overrides,
})

describe('validateTrip (mirrors backend serializer rules)', () => {
  it('accepts a complete trip', () => {
    expect(validateTrip(valid(), NOW)).toEqual({})
  })

  it('requires every field', () => {
    const errors = validateTrip(
      valid({ origin: { text: '', place: null }, destination: { text: ' ', place: null }, departure: '', load: '' }),
      NOW,
    )
    expect(Object.keys(errors).sort()).toEqual(['departure_at', 'destination', 'load_weight_lb', 'origin'])
  })

  it.each([
    ['-1', 'whole number'],
    ['80001', 'between'],
    ['12.5', 'whole number'],
    ['abc', 'whole number'],
  ])('rejects load weight %s', (load, message) => {
    expect(validateTrip(valid({ load }), NOW).load_weight_lb).toContain(message)
  })

  it.each(['0', '80000', '30001'])('accepts load weight %s', (load) => {
    expect(validateTrip(valid({ load }), NOW).load_weight_lb).toBeUndefined()
  })

  it('enforces the departure window (1 h grace, 7 days ahead)', () => {
    expect(validateTrip(valid({ departure: '2026-11-02T10:30' }), NOW).departure_at).toContain('past')
    expect(validateTrip(valid({ departure: '2026-11-02T11:15' }), NOW).departure_at).toBeUndefined()
    expect(validateTrip(valid({ departure: '2026-11-09T13:00' }), NOW).departure_at).toContain('7 days')
  })

  it('rejects identical origin and destination', () => {
    expect(validateTrip(valid({ destination: { text: 'x', place: dallas } }), NOW).destination).toContain('different')
    expect(
      validateTrip(valid({ origin: { text: 'Austin', place: null }, destination: { text: 'austin ', place: null } }), NOW)
        .destination,
    ).toContain('different')
  })

  it('rejects one-character free text', () => {
    expect(validateTrip(valid({ origin: { text: 'D', place: null } }), NOW).origin).toContain('at least 2')
  })
})

describe('toTripRequest', () => {
  it('sends picked places as coordinates and typed places as text, with an ISO departure', () => {
    const request = toTripRequest(valid({ destination: { text: ' Houston TX ', place: null } }))
    expect(request).toEqual({
      origin: dallas,
      destination: 'Houston TX',
      departure_at: new Date('2026-11-02T14:00').toISOString(),
      load_weight_lb: 42000,
      interval_miles: 25,
    })
  })
})
