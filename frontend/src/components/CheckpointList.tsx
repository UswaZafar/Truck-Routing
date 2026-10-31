import { memo, useState, type CSSProperties } from 'react'

import type { Checkpoint, RouteOption } from '../api/types'
import { formatClock, formatWeekday } from '../lib/format'
import { riskMeta } from '../lib/risk'
import { RainIcon, SnowIcon, WindIcon } from './icons'

/** What produced the checkpoint's level, e.g. "Wind 48 mph, raised by the load rule". */
export function causeOf(cp: Checkpoint): string {
  const parts = cp.conditions.map((condition) => {
    if (condition === 'wind') return `Wind ${cp.wind_mph.toFixed(0)} mph`
    if (condition === 'rain') return `Rain ${cp.rain_in_hr.toFixed(2)} in/hr`
    return `Snow ${cp.snow_in_hr.toFixed(1)} in/hr`
  })
  return parts.join(' and ') + (cp.load_adjusted ? ', raised by the load-weight rule' : '')
}

/** The selected route's checkpoints in driving order, each with its ETA, forecast and risk. */
export const CheckpointList = memo(function CheckpointList({ route }: { route: RouteOption }) {
  const [riskyOnly, setRiskyOnly] = useState(false)
  const risky = route.checkpoints.filter((cp) => cp.risk !== 'low').length
  const shown = riskyOnly ? route.checkpoints.filter((cp) => cp.risk !== 'low') : route.checkpoints

  return (
    <section className="stops" aria-labelledby="stops-title">
      <div className="section-head">
        <h2 id="stops-title" className="section-title">
          Along Route {route.id}
        </h2>
        <label className="switch">
          <input type="checkbox" role="switch" checked={riskyOnly} onChange={(event) => setRiskyOnly(event.target.checked)} />
          Risky only ({risky})
        </label>
      </div>
      {shown.length === 0 ? (
        <p className="stops__empty">Every checkpoint on Route {route.id} is Low risk at its arrival time.</p>
      ) : (
        <ol className="stops__list">
          {shown.map((cp) => {
            const risk = riskMeta(cp.risk)
            return (
              <li key={cp.mile} className={`stop stop--${cp.risk}`} style={{ '--dot': risk.color } as CSSProperties}>
                <div className="stop__time">
                  <span>{formatClock(cp.eta)}</span>
                  <span className="stop__day">{formatWeekday(cp.eta)}</span>
                </div>
                <span className="stop__dot" aria-hidden="true" />
                <div className="stop__body">
                  <div className="stop__head">
                    <span className="stop__mile">Mile {cp.mile.toFixed(0)}</span>
                    <span className="risk-chip" style={{ background: risk.tint, color: risk.ink }}>
                      {risk.label}
                    </span>
                  </div>
                  {cp.conditions.length > 0 && <p className="stop__cause">{causeOf(cp)}</p>}
                  <p className="stop__wx">
                    <span>
                      <WindIcon />
                      <span className="sr-only">Wind </span>
                      {cp.wind_mph.toFixed(0)} mph
                    </span>
                    <span>
                      <RainIcon />
                      <span className="sr-only">Rain </span>
                      {cp.rain_in_hr.toFixed(2)} in/hr
                    </span>
                    <span>
                      <SnowIcon />
                      <span className="sr-only">Snow </span>
                      {cp.snow_in_hr.toFixed(1)} in/hr
                    </span>
                  </p>
                  {!cp.forecast_complete && <p className="stop__note">Forecast incomplete at this time.</p>}
                </div>
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
})
