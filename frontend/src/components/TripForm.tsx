import { useState, type FormEvent } from 'react'

import { ApiError } from '../api/client'
import type { Interval, TripRequest } from '../api/types'
import { nextFullHour, toDateTimeLocal } from '../lib/format'
import {
  DEPARTURE_MAX_AHEAD_MS,
  DEPARTURE_PAST_GRACE_MS,
  INTERVALS,
  LOAD_MAX_LB,
  LOAD_MIN_LB,
  toTripRequest,
  validateTrip,
  type TripFormErrors,
  type TripFormValues,
} from '../lib/validation'
import { SwapIcon } from './icons'
import { PlaceInput } from './PlaceInput'

interface Props {
  onSubmit: (request: TripRequest) => void
  submitting: boolean
  serverError: Error | null
  /** Hidden (not unmounted) while a plan is shown, so the entered values survive. */
  hidden?: boolean
  /** Back to the current plan without re-planning. */
  onCancel?: () => void
}

const initialValues = (): TripFormValues => ({
  origin: { text: '', place: null },
  destination: { text: '', place: null },
  departure: toDateTimeLocal(nextFullHour()),
  load: '',
  interval: 25,
})

export function TripForm({ onSubmit, submitting, serverError, hidden = false, onCancel }: Props) {
  const [values, setValues] = useState(initialValues)
  const [errors, setErrors] = useState<TripFormErrors>({})
  const [submitted, setSubmitted] = useState(false)

  const change = (next: TripFormValues) => {
    setValues(next)
    if (submitted) setErrors(validateTrip(next)) // re-validate live once the user has tried to submit
  }
  const update = <K extends keyof TripFormValues>(key: K, value: TripFormValues[K]) => change({ ...values, [key]: value })
  const swap = () => change({ ...values, origin: values.destination, destination: values.origin })

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    setSubmitted(true)
    const found = validateTrip(values)
    setErrors(found)
    if (Object.keys(found).length === 0) onSubmit(toTripRequest(values))
  }

  // Server-side field errors (e.g. a place the geocoder can't find) show under the matching input.
  const serverFields = serverError instanceof ApiError ? serverError.fieldErrors : {}
  const fieldError = (key: keyof TripFormErrors) => errors[key] ?? serverFields[key]
  const now = Date.now()

  return (
    <form className="trip-form" onSubmit={handleSubmit} noValidate hidden={hidden} aria-labelledby="trip-form-title">
      <div className="trip-form__head">
        <h2 id="trip-form-title" className="panel-title">
          Plan a trip
        </h2>
        {onCancel && (
          <button type="button" className="text-button" onClick={onCancel}>
            Back to routes
          </button>
        )}
      </div>

      <div className="places">
        <PlaceInput
          label="Origin"
          marker="origin"
          placeholder="City or address"
          value={values.origin}
          onChange={(value) => update('origin', value)}
          error={fieldError('origin')}
        />
        <PlaceInput
          label="Destination"
          marker="destination"
          placeholder="City or address"
          value={values.destination}
          onChange={(value) => update('destination', value)}
          error={fieldError('destination')}
        />
        <button type="button" className="icon-button places__swap" onClick={swap} aria-label="Swap origin and destination">
          <SwapIcon />
        </button>
      </div>

      <div className="field-row">
        <div className="field">
          <label htmlFor="departure">Departure</label>
          <input
            id="departure"
            type="datetime-local"
            value={values.departure}
            min={toDateTimeLocal(new Date(now - DEPARTURE_PAST_GRACE_MS))}
            max={toDateTimeLocal(new Date(now + DEPARTURE_MAX_AHEAD_MS))}
            aria-invalid={Boolean(fieldError('departure_at'))}
            aria-describedby={fieldError('departure_at') ? 'departure-error' : undefined}
            onChange={(event) => update('departure', event.target.value)}
          />
          {fieldError('departure_at') && (
            <p id="departure-error" className="field__error">
              {fieldError('departure_at')}
            </p>
          )}
        </div>
        <div className="field">
          <label htmlFor="load">
            Load weight<span className="sr-only"> (lb)</span>
          </label>
          <div className="input-unit">
            <input
              id="load"
              type="number"
              inputMode="numeric"
              min={LOAD_MIN_LB}
              max={LOAD_MAX_LB}
              step={1}
              placeholder="42000"
              value={values.load}
              aria-invalid={Boolean(fieldError('load_weight_lb'))}
              aria-describedby={fieldError('load_weight_lb') ? 'load-error' : undefined}
              onChange={(event) => update('load', event.target.value)}
            />
            <span aria-hidden="true">lb</span>
          </div>
          {fieldError('load_weight_lb') && (
            <p id="load-error" className="field__error">
              {fieldError('load_weight_lb')}
            </p>
          )}
        </div>
      </div>

      <fieldset className="field interval">
        <legend>Weather checkpoint every</legend>
        <div className="segmented">
          {INTERVALS.map((interval) => (
            <label key={interval} className={values.interval === interval ? 'is-selected' : undefined}>
              <input
                type="radio"
                name="interval"
                value={interval}
                checked={values.interval === interval}
                onChange={() => update('interval', interval as Interval)}
              />
              {interval} mi
            </label>
          ))}
        </div>
        {fieldError('interval_miles') && <p className="field__error">{fieldError('interval_miles')}</p>}
      </fieldset>

      <button type="submit" className="button button--primary" disabled={submitting}>
        {submitting ? 'Planning…' : 'Plan routes'}
      </button>
    </form>
  )
}
