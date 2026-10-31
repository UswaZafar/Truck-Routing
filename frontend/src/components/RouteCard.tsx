import { memo, type CSSProperties } from 'react'

import type { RiskKey, RouteOption } from '../api/types'
import { formatClock, formatDuration, formatMiles, formatWeekday } from '../lib/format'
import { riskMeta } from '../lib/risk'

interface Props {
  route: RouteOption
  selected: boolean
  /** Ranking criterion that separated the top two routes (highlighted on every card). */
  decidedBy: string | null
  onSelect: (id: string) => void
}

/** Consecutive checkpoints with the same level merged into one segment, sized by the miles they cover. */
function riskRuns(route: RouteOption): Array<{ risk: RiskKey; miles: number }> {
  const runs: Array<{ risk: RiskKey; miles: number }> = []
  for (const cp of route.checkpoints) {
    const last = runs[runs.length - 1]
    if (last?.risk === cp.risk) last.miles += cp.miles
    else runs.push({ risk: cp.risk, miles: cp.miles })
  }
  return runs
}

/** The route as a line from origin to destination, coloured where the forecast is risky. */
function RiskLine({ route }: { route: RouteOption }) {
  return (
    <div className="risk-line" role="img" aria-label={`Risk along Route ${route.id}, worst: ${riskMeta(route.summary.max_risk).label}`}>
      {riskRuns(route).map((run, i) => (
        <span
          key={i}
          className={`risk-line__run risk-line__run--${run.risk}`}
          style={{ flexGrow: run.miles, '--run': riskMeta(run.risk).color } as CSSProperties}
        />
      ))}
    </div>
  )
}

export const RouteCard = memo(function RouteCard({ route, selected, decidedBy, onSelect }: Props) {
  const { summary } = route
  const miles = summary.miles_by_risk
  const stats = [
    { key: 'no_travel_miles', label: 'No Travel', value: miles.no_travel, text: formatMiles(miles.no_travel, 1) },
    { key: 'severe_miles', label: 'Severe', value: miles.severe, text: formatMiles(miles.severe, 1) },
    { key: 'high_miles', label: 'High', value: miles.high, text: formatMiles(miles.high, 1) },
    { key: 'average_risk', label: 'Avg risk', value: summary.average_risk, text: summary.average_risk.toFixed(2) },
  ]
  return (
    <button
      type="button"
      className={`route-card${selected ? ' is-selected' : ''}`}
      aria-pressed={selected}
      onClick={() => onSelect(route.id)}
    >
      <div className="route-card__top">
        <span className="route-card__id">{route.id}</span>
        <span className={`route-card__time${decidedBy === 'travel_time' ? ' is-decisive' : ''}`}>
          {formatDuration(route.duration_s)}
        </span>
        <span className="route-card__tags">
          {route.recommended && <span className="tag tag--recommended">Recommended</span>}
          {summary.no_travel && <span className="tag tag--danger">No Travel</span>}
        </span>
      </div>
      <p className="route-card__meta">
        #{route.rank} · {formatMiles(route.distance_mi)} · arrives {formatWeekday(route.arrival_at)}{' '}
        {formatClock(route.arrival_at)}
      </p>
      <RiskLine route={route} />
      <dl className="route-card__stats">
        {stats.map((stat) => (
          <div key={stat.key} className={stat.key === decidedBy ? 'is-decisive' : undefined}>
            <dt>{stat.label}</dt>
            <dd className={stat.value > 0 ? undefined : 'is-zero'}>{stat.text}</dd>
          </div>
        ))}
      </dl>
    </button>
  )
})
