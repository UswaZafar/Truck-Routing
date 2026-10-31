import type { Interval, Place, TripRequest } from '../api/types'

// Mirrors backend/trips/serializers.py — keep the two in sync.
export const LOAD_MIN_LB = 0
export const LOAD_MAX_LB = 80_000
export const INTERVALS: readonly Interval[] = [10, 25, 50]
export const DEPARTURE_PAST_GRACE_MS = 60 * 60 * 1000
export const DEPARTURE_MAX_AHEAD_MS = 7 * 24 * 60 * 60 * 1000
export const PLACE_TEXT_MIN = 2
export const PLACE_TEXT_MAX = 200

export interface PlaceValue {
  text: string
  /** Set when the user picked a suggestion; cleared as soon as they edit the text. */
  place: Place | null
}

export interface TripFormValues {
  origin: PlaceValue
  destination: PlaceValue
  /** datetime-local value, browser time zone */
  departure: string
  load: string
  interval: Interval
}

export type TripFormErrors = Partial<Record<'origin' | 'destination' | 'departure_at' | 'load_weight_lb' | 'interval_miles', string>>

function placeError(value: PlaceValue): string | undefined {
  if (value.place) return undefined
  const text = value.text.trim()
  if (!text) return 'Required.'
  if (text.length < PLACE_TEXT_MIN) return `Enter at least ${PLACE_TEXT_MIN} characters.`
  if (text.length > PLACE_TEXT_MAX) return `Enter at most ${PLACE_TEXT_MAX} characters.`
  return undefined
}

const placeKey = (value: PlaceValue) =>
  value.place ? `${value.place.lat.toFixed(4)},${value.place.lng.toFixed(4)}` : value.text.trim().toLowerCase()

export function validateTrip(values: TripFormValues, now = Date.now()): TripFormErrors {
  const errors: TripFormErrors = {}

  errors.origin = placeError(values.origin)
  errors.destination = placeError(values.destination)
  if (!errors.origin && !errors.destination && placeKey(values.origin) === placeKey(values.destination)) {
    errors.destination = 'Destination must be different from the origin.'
  }

  const departure = values.departure ? new Date(values.departure).getTime() : NaN
  if (Number.isNaN(departure)) errors.departure_at = 'Required.'
  else if (departure < now - DEPARTURE_PAST_GRACE_MS) errors.departure_at = 'Departure cannot be more than 1 hour in the past.'
  else if (departure > now + DEPARTURE_MAX_AHEAD_MS) errors.departure_at = 'Departure must be within the next 7 days (forecast range).'

  const load = values.load.trim()
  if (!load) errors.load_weight_lb = 'Required.'
  else if (!/^\d+$/.test(load)) errors.load_weight_lb = 'Enter a whole number of pounds.'
  else if (Number(load) < LOAD_MIN_LB || Number(load) > LOAD_MAX_LB)
    errors.load_weight_lb = `Enter a weight between ${LOAD_MIN_LB.toLocaleString()} and ${LOAD_MAX_LB.toLocaleString()} lb.`

  if (!INTERVALS.includes(values.interval)) errors.interval_miles = 'Choose 10, 25 or 50 miles.'

  return Object.fromEntries(Object.entries(errors).filter(([, message]) => message)) as TripFormErrors
}

export function toTripRequest(values: TripFormValues): TripRequest {
  const place = (value: PlaceValue) => value.place ?? value.text.trim()
  return {
    origin: place(values.origin),
    destination: place(values.destination),
    departure_at: new Date(values.departure).toISOString(),
    load_weight_lb: Number(values.load),
    interval_miles: values.interval,
  }
}
