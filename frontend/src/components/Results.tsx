import type { UseQueryResult } from '@tanstack/react-query'

import { ApiError } from '../api/client'
import type { TripPlan } from '../api/types'
import { CheckpointList } from './CheckpointList'
import { RouteCard } from './RouteCard'
import { StatusMessage } from './StatusMessage'

interface Props {
  plan: UseQueryResult<TripPlan>
  hasRequest: boolean
  selectedId: string | null
  onSelect: (id: string) => void
}

const RANKING = ['Fewest No Travel miles', 'Fewest Severe miles', 'Fewest High miles', 'Lowest average risk', 'Shortest travel time']

/** "Shortest travel time: … (tied on X, Y)" → the deciding sentence and the tie note. */
export function splitExplanation(text: string): [string, string | null] {
  const match = /^(.*?)\s*\(tied on (.+)\)$/.exec(text)
  return match ? [match[1], `Tied on ${match[2]}`] : [text, null]
}

export function Results({ plan, hasRequest, selectedId, onSelect }: Props) {
  if (!hasRequest) {
    return (
      <section className="guide" aria-labelledby="guide-title">
        <h2 id="guide-title" className="section-title">
          How the safest route is picked
        </h2>
        <ol className="guide__list">
          {RANKING.map((rule) => (
            <li key={rule}>{rule}</li>
          ))}
        </ol>
        <p className="guide__note">
          Weather is checked at each checkpoint for the time your truck gets there. Heavier loads lower the wind
          limits: over 30,000 lb, 45–54 mph is No Travel; over 40,000 lb, 35–44 mph is Severe.
        </p>
      </section>
    )
  }
  if (plan.isPending) {
    return (
      <div className="results">
        <StatusMessage kind="loading" title="Planning routes…">
          Finding three routes and checking the forecast at every checkpoint's arrival time.
        </StatusMessage>
        <div className="skeleton-list" aria-hidden="true">
          <span className="skeleton-card" />
          <span className="skeleton-card" />
          <span className="skeleton-card" />
        </div>
      </div>
    )
  }
  if (plan.isError) {
    const error = plan.error
    // Field problems are shown on the form itself; only temporary failures (network, upstream) are worth retrying.
    if (error instanceof ApiError && Object.keys(error.fieldErrors).length > 0) return null
    const retryable = !(error instanceof ApiError) || error.status === 0 || error.status === 429 || error.status >= 500
    return (
      <StatusMessage kind="error" title="Could not plan this trip" onRetry={retryable ? () => plan.refetch() : undefined}>
        {error.message}
      </StatusMessage>
    )
  }

  const data = plan.data
  const selected = data.routes.find((route) => route.id === selectedId) ?? data.routes[0]
  const ordered = [...data.routes].sort((a, b) => a.rank - b.rank)
  const [reason, tie] = splitExplanation(data.recommendation.explanation)

  return (
    <div className="results">
      <section className="verdict" aria-labelledby="verdict-title" aria-live="polite">
        <p className="verdict__label">Recommended</p>
        <h2 id="verdict-title" className="verdict__title">
          Take Route {data.recommendation.route_id}
        </h2>
        <p className="verdict__reason">{reason}</p>
        {tie && <p className="verdict__tie">{tie}</p>}
        {data.notes.map((note) => (
          <p key={note} className="note">
            {note}
          </p>
        ))}
      </section>

      <section className="routes" aria-labelledby="routes-title">
        <div className="section-head">
          <h2 id="routes-title" className="section-title">
            Routes
          </h2>
          <span className="section-hint">safest first</span>
        </div>
        <div className="route-list">
          {ordered.map((route) => (
            <RouteCard
              key={route.id}
              route={route}
              selected={route.id === selected.id}
              decidedBy={data.recommendation.decided_by}
              onSelect={onSelect}
            />
          ))}
        </div>
      </section>

      <CheckpointList route={selected} />
    </div>
  )
}
