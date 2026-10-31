import { useId, useState, type KeyboardEvent } from 'react'

import { useGeocode } from '../api/queries'
import type { Place } from '../api/types'
import type { PlaceValue } from '../lib/validation'

interface Props {
  label: string
  value: PlaceValue
  onChange: (value: PlaceValue) => void
  error?: string
  placeholder?: string
  /** Journey-line marker drawn beside the input. */
  marker?: 'origin' | 'destination'
}

/** Text input with debounced place suggestions (WAI-ARIA combobox pattern). */
export function PlaceInput({ label, value, onChange, error, placeholder, marker }: Props) {
  const id = useId()
  const listId = `${id}-list`
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  // Only search while the user is typing free text, not for a label they already picked.
  const suggestions = useGeocode(open && !value.place ? value.text : '')
  const results = suggestions.data ?? []
  const showList = open && !value.place && value.text.trim().length >= 3

  const pick = (place: Place) => {
    onChange({ text: place.label, place })
    setOpen(false)
    setActive(-1)
  }

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (!showList || results.length === 0) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActive((i) => (i + 1) % results.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive((i) => (i <= 0 ? results.length - 1 : i - 1))
    } else if (event.key === 'Enter' && active >= 0) {
      event.preventDefault()
      pick(results[active])
    } else if (event.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className={`field place-input${marker ? ` place-input--${marker}` : ''}`}>
      {marker && <span className="place-input__marker" aria-hidden="true" />}
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="text"
        role="combobox"
        autoComplete="off"
        aria-autocomplete="list"
        aria-expanded={showList}
        aria-controls={listId}
        aria-activedescendant={showList && active >= 0 ? `${listId}-${active}` : undefined}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
        placeholder={placeholder}
        value={value.text}
        onChange={(event) => {
          onChange({ text: event.target.value, place: null })
          setOpen(true)
          setActive(-1)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
      />
      {showList && (
        <ul id={listId} role="listbox" className="suggestions">
          {suggestions.isError && <li className="suggestions__note">Suggestions unavailable — you can still submit the text.</li>}
          {!suggestions.isError && results.length === 0 && (
            <li className="suggestions__note">{suggestions.isFetching ? 'Searching…' : 'No matches found.'}</li>
          )}
          {results.map((place, index) => (
            <li
              key={`${place.lat},${place.lng}`}
              id={`${listId}-${index}`}
              role="option"
              aria-selected={index === active}
              className={index === active ? 'is-active' : undefined}
              // mousedown (not click) so the input's blur doesn't close the list first
              onMouseDown={(event) => {
                event.preventDefault()
                pick(place)
              }}
            >
              {place.label}
            </li>
          ))}
        </ul>
      )}
      {error && (
        <p id={`${id}-error`} className="field__error">
          {error}
        </p>
      )}
    </div>
  )
}
