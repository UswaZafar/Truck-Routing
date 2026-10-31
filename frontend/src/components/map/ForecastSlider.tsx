import { memo, type CSSProperties } from 'react'

import { formatDateTime, formatWeekday } from '../../lib/format'
import { RISK_LEVELS } from '../../lib/risk'
import { PauseIcon, PlayIcon } from '../icons'

/** The selected route's time on the road, as fractions of the 0–48 h timeline. */
export interface TripWindow {
  from: number
  to: number
  label: string
}

interface Props {
  start: string | undefined
  hours: number
  hour: number
  onChange: (hour: number) => void
  playing: boolean
  onTogglePlay: () => void
  visible: boolean
  onToggleVisible: (visible: boolean) => void
  /** Worst risk index (0–4) in the corridor for each hour. */
  hourlyWorst: number[] | null
  trip: TripWindow | null
  status: 'loading' | 'error' | 'ready'
  error?: string
  onRetry: () => void
}

const HOUR_MS = 60 * 60 * 1000
const TICKS = [0, 12, 24, 36, 48]
const at = (fraction: number) => ({ '--at': fraction }) as CSSProperties

/** One bar per hour, coloured by the worst level in the corridor; the current hour is emphasised. */
const HourBars = memo(function HourBars({ worst, hour }: { worst: number[]; hour: number }) {
  const last = Math.max(worst.length - 1, 1)
  return (
    <div className="forecast-slider__bars" aria-hidden="true">
      {worst.map((index, h) => {
        const level = Math.min(Math.floor(index), 4)
        return (
          <span
            key={h}
            className={h === hour ? 'is-current' : undefined}
            style={{
              ...at(h / last),
              height: `${16 + (index / 4) * 84}%`,
              background: level === 0 ? undefined : RISK_LEVELS[level].color,
            }}
          />
        )
      })}
    </div>
  )
})

export function ForecastSlider(props: Props) {
  const { start, hours, hour, onChange, playing, onTogglePlay, visible, onToggleVisible, hourlyWorst, trip, status, error, onRetry } =
    props
  const maxHour = hours - 1
  const ready = status === 'ready' && start !== undefined
  const startMs = start ? Date.parse(start) : 0
  const days = ready
    ? Array.from({ length: maxHour }, (_, i) => i + 1)
        .filter((h) => new Date(startMs + h * HOUR_MS).getHours() === 0)
        .map((h) => ({ h, label: formatWeekday(new Date(startMs + h * HOUR_MS)) }))
    : []

  return (
    <section className="forecast-slider" aria-label="Weather forecast timeline">
      <div className="forecast-slider__head">
        <button
          type="button"
          className="play-button"
          onClick={onTogglePlay}
          disabled={!ready}
          aria-label={playing ? 'Pause forecast playback' : 'Play forecast'}
        >
          {playing ? <PauseIcon /> : <PlayIcon />}
        </button>
        <div className="forecast-slider__now" aria-live="off">
          {ready && (
            <>
              <span className="forecast-slider__offset">+{hour} h</span>
              <span className="forecast-slider__clock">{formatDateTime(new Date(startMs + hour * HOUR_MS))}</span>
            </>
          )}
          {status === 'loading' && <span className="forecast-slider__status">Loading corridor forecast…</span>}
          {status === 'error' && (
            <span className="forecast-slider__status forecast-slider__status--error" role="alert">
              {error ?? 'Heatmap unavailable.'}{' '}
              <button type="button" className="text-button" onClick={onRetry}>
                Retry
              </button>
            </span>
          )}
        </div>
        <label className="switch">
          <input
            type="checkbox"
            role="switch"
            checked={visible}
            disabled={!ready}
            onChange={(event) => onToggleVisible(event.target.checked)}
          />
          Heatmap
        </label>
      </div>

      <div className="forecast-slider__track">
        {days.map((day) => (
          <span key={day.h} className="forecast-slider__day" style={at(day.h / maxHour)} aria-hidden="true">
            {day.label}
          </span>
        ))}
        {hourlyWorst && ready && <HourBars worst={hourlyWorst} hour={hour} />}
        <span className="forecast-slider__rail" aria-hidden="true">
          {trip && (
            <span
              className="forecast-slider__trip"
              style={{ left: `${trip.from * 100}%`, width: `${Math.max(trip.to - trip.from, 0) * 100}%` }}
            />
          )}
        </span>
        <input
          type="range"
          min={0}
          max={maxHour}
          step={1}
          value={hour}
          disabled={!ready}
          aria-label="Forecast hour after departure"
          aria-valuetext={ready ? `${hour} hours after departure, ${formatDateTime(new Date(startMs + hour * HOUR_MS))}` : undefined}
          onChange={(event) => onChange(Number(event.target.value))}
        />
      </div>

      <div className="forecast-slider__ticks" aria-hidden="true">
        {TICKS.filter((tick) => tick <= maxHour).map((tick) => (
          <span key={tick} style={at(tick / maxHour)}>
            {tick === 0 ? 'Depart' : `+${tick} h`}
          </span>
        ))}
      </div>

      {ready && (
        <p className="forecast-slider__key">
          {trip && (
            <span>
              <i className="forecast-slider__key-trip" aria-hidden="true" />
              {trip.label}
            </span>
          )}
          <span>
            <i className="forecast-slider__key-bars" aria-hidden="true" />
            Bars: worst risk in the corridor each hour
          </span>
        </p>
      )}
    </section>
  )
}
