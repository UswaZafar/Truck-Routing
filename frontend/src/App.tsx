import { lazy, Suspense, useCallback, useState } from 'react'

import { ApiError } from './api/client'
import { useTripPlan } from './api/queries'
import type { TripRequest } from './api/types'
import { BrandMark } from './components/icons'
import { Results } from './components/Results'
import { TripForm } from './components/TripForm'
import { TripSummary } from './components/TripSummary'
import { timeZoneName } from './lib/format'

// maplibre-gl is the largest dependency; load it in its own chunk while the form renders.
const MapView = lazy(() => import('./components/map/MapView'))

const placeLabel = (place: TripRequest['origin']) => (typeof place === 'string' ? place : place.label)

export default function App() {
  const [request, setRequest] = useState<TripRequest | null>(null)
  const [editing, setEditing] = useState(true)
  const plan = useTripPlan(request)
  // Selection is remembered per plan; a new plan starts on its recommended route.
  const [selection, setSelection] = useState<{ planId: string; routeId: string } | null>(null)

  const data = plan.data
  const selectedId = data ? (selection?.planId === data.id ? selection.routeId : data.recommendation.route_id) : null
  const selected = data?.routes.find((route) => route.id === selectedId)
  const planId = data?.id
  const selectRoute = useCallback((routeId: string) => {
    if (planId) setSelection({ planId, routeId })
  }, [planId])

  const submit = useCallback((next: TripRequest) => {
    setRequest(next)
    setEditing(false)
    // On phones the map sits above the panel: bring it back into view to watch the routes arrive.
    if (window.matchMedia('(max-width: 899px)').matches) window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  // The form reopens by itself when the server rejects a field (e.g. a place it cannot find).
  const hasFieldErrors = plan.error instanceof ApiError && Object.keys(plan.error.fieldErrors).length > 0
  const showForm = request === null || editing || hasFieldErrors

  return (
    <div className="app">
      <main className="app__map" aria-label="Map">
        <Suspense fallback={<div className="map-wrap"><div className="map-overlay">Loading map…</div></div>}>
          <MapView plan={data} selectedId={selectedId} onSelectRoute={selectRoute} />
        </Suspense>
      </main>

      <aside className="panel" aria-label="Trip planner">
        <header className="brand">
          <BrandMark />
          <h1 className="brand__name">Weather-Aware Truck Routing</h1>
          <span className="brand__tz" title="ETAs and forecast times are shown in your time zone">
            {timeZoneName()}
          </span>
        </header>

        {!showForm && request && (
          <TripSummary
            origin={data?.input.origin.label ?? placeLabel(request.origin)}
            destination={data?.input.destination.label ?? placeLabel(request.destination)}
            departureAt={request.departure_at}
            arrivalAt={selected?.arrival_at}
            loadLb={request.load_weight_lb}
            intervalMiles={request.interval_miles}
            busy={plan.isFetching}
            onEdit={() => setEditing(true)}
          />
        )}
        <TripForm
          hidden={!showForm}
          onSubmit={submit}
          submitting={plan.isFetching}
          serverError={plan.error}
          onCancel={request && !hasFieldErrors ? () => setEditing(false) : undefined}
        />

        <Results plan={plan} hasRequest={request !== null} selectedId={selectedId} onSelect={selectRoute} />
      </aside>
    </div>
  )
}
