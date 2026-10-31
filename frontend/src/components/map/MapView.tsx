import 'maplibre-gl/dist/maplibre-gl.css'

import {
  type GeoJSONSource,
  Map as MapLibreMap,
  type MapLayerMouseEvent,
  Marker,
  NavigationControl,
  Popup,
  setWorkerUrl,
} from 'maplibre-gl'
// MapLibre locates its worker relative to its own module, which bundlers relocate; hand it the emitted URL.
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'

import type { TripPlan } from '../../api/types'
import { formatDuration, formatMiles } from '../../lib/format'
import { HeatmapLayer } from './HeatmapLayer'
import {
  LAYER,
  SOURCE,
  STYLE_URL,
  US_CENTER,
  addTripLayers,
  boundsOf,
  checkpointPopupHTML,
  checkpointsGeoJSON,
  pointAlong,
  routePopupHTML,
  routesGeoJSON,
  tuneBasemap,
} from './layers'
import { Legend } from './Legend'

interface Props {
  plan: TripPlan | undefined
  selectedId: string | null
  onSelectRoute: (id: string) => void
}

setWorkerUrl(workerUrl)

const LABEL_POSITIONS = [0.35, 0.5, 0.65]

/** Keeps routes clear of the floating forecast card (and of the panel's rounded edge on wide screens). */
const fitPadding = () =>
  window.matchMedia('(min-width: 900px)').matches
    ? { top: 90, bottom: 230, left: 80, right: 110 }
    : { top: 70, bottom: 250, left: 36, right: 36 }

function endpointMarker(kind: 'origin' | 'destination', label: string): Marker {
  const element = document.createElement('div')
  element.className = `map-marker map-marker--${kind}`
  element.title = `${kind === 'origin' ? 'Origin' : 'Destination'}: ${label}`
  return new Marker({ element })
}

/** MapLibre map driven imperatively from props; React only owns the overlays. Lazy-loaded (heavy). */
export default function MapView({ plan, selectedId, onSelectRoute }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [map, setMap] = useState<MapLibreMap | null>(null)
  const [mapError, setMapError] = useState(false)
  // Event handlers are registered once; refs give them the latest props.
  const planRef = useRef(plan)
  const onSelectRef = useRef(onSelectRoute)
  useLayoutEffect(() => {
    planRef.current = plan
    onSelectRef.current = onSelectRoute
  })

  useEffect(() => {
    const instance = new MapLibreMap({
      container: containerRef.current!,
      style: STYLE_URL,
      center: US_CENTER,
      zoom: 3.4,
      attributionControl: { compact: true },
    })
    instance.addControl(new NavigationControl({ showCompass: false }), 'top-right')
    instance.on('error', (event) => {
      if (!instance.isStyleLoaded()) setMapError(Boolean(event.error))
    })
    if (import.meta.env.DEV) Object.assign(window, { __map: instance }) // handle for browser tests
    instance.on('load', () => {
      tuneBasemap(instance)
      addTripLayers(instance)
      bindInteractions(instance)
      setMap(instance)
    })

    function bindInteractions(m: MapLibreMap) {
      const popup = new Popup({ closeButton: true, maxWidth: '280px' })
      m.on('click', LAYER.checkpoints, (event: MapLayerMouseEvent) => {
        const props = event.features?.[0]?.properties
        const route = planRef.current?.routes.find((r) => r.id === props?.route)
        const checkpoint = route?.checkpoints[Number(props?.index)]
        if (!route || !checkpoint) return
        popup.setLngLat([checkpoint.lng, checkpoint.lat]).setHTML(checkpointPopupHTML(route, checkpoint)).addTo(m)
      })
      m.on('click', LAYER.routeLine, (event: MapLayerMouseEvent) => {
        if (m.queryRenderedFeatures(event.point, { layers: [LAYER.checkpoints] }).length) return // checkpoint wins
        const route = planRef.current?.routes.find((r) => r.id === event.features?.[0]?.properties?.id)
        if (!route) return
        onSelectRef.current(route.id)
        popup.setLngLat(event.lngLat).setHTML(routePopupHTML(route)).addTo(m)
      })
      for (const layer of [LAYER.checkpoints, LAYER.routeLine]) {
        m.on('mouseenter', layer, () => (m.getCanvas().style.cursor = 'pointer'))
        m.on('mouseleave', layer, () => (m.getCanvas().style.cursor = ''))
      }
    }

    return () => instance.remove()
  }, [])

  // Route lines + checkpoints follow the plan and the selected route.
  useEffect(() => {
    if (!map) return
    const routes = plan?.routes ?? []
    map.getSource<GeoJSONSource>(SOURCE.routes)?.setData(routesGeoJSON(routes, selectedId))
    map.getSource<GeoJSONSource>(SOURCE.checkpoints)?.setData(checkpointsGeoJSON(routes, selectedId))
  }, [map, plan, selectedId])

  // Frame a new plan; origin/destination markers.
  useEffect(() => {
    if (!map || !plan) return
    map.fitBounds(boundsOf(plan.routes), { padding: fitPadding(), duration: 600 })
    const { origin, destination } = plan.input
    const markers = [
      endpointMarker('origin', origin.label).setLngLat([origin.lng, origin.lat]),
      endpointMarker('destination', destination.label).setLngLat([destination.lng, destination.lat]),
    ]
    markers.forEach((marker) => marker.addTo(map))
    return () => markers.forEach((marker) => marker.remove())
  }, [map, plan])

  // Route summary labels on the map (A/B/C, time, distance); click to select.
  useEffect(() => {
    if (!map || !plan) return
    const markers = plan.routes.map((route, i) => {
      const element = document.createElement('button')
      element.type = 'button'
      element.className = `map-pill${route.recommended ? ' is-recommended' : ''}`
      element.dataset.route = route.id
      const id = document.createElement('span')
      id.className = 'map-pill__id'
      id.textContent = route.id
      element.append(id, `${formatDuration(route.duration_s)} · ${formatMiles(route.distance_mi)}`)
      element.setAttribute('aria-label', `Select Route ${route.id}${route.recommended ? ' (recommended)' : ''}`)
      element.addEventListener('click', (event) => {
        event.stopPropagation()
        onSelectRef.current(route.id)
      })
      return new Marker({ element }).setLngLat(pointAlong(route, LABEL_POSITIONS[i % 3])).addTo(map)
    })
    return () => markers.forEach((marker) => marker.remove())
  }, [map, plan])

  useEffect(() => {
    document.querySelectorAll<HTMLElement>('.map-pill').forEach((pill) => {
      pill.classList.toggle('is-selected', pill.dataset.route === selectedId)
    })
  }, [plan, selectedId])

  return (
    <div className="map-wrap">
      <div ref={containerRef} className="map" role="region" aria-label="Route map" />
      {!map && !mapError && <div className="map-overlay">Loading map…</div>}
      {mapError && <div className="map-overlay map-overlay--error">The base map could not be loaded. Routes are still listed in the sidebar.</div>}
      {map && !plan && <div className="map-overlay map-overlay--hint">Plan a trip to see routes, checkpoints and the weather heatmap.</div>}
      <Legend />
      {map && plan && (
        <HeatmapLayer key={plan.id} map={map} planId={plan.id} selectedRoute={plan.routes.find((r) => r.id === selectedId)} />
      )}
    </div>
  )
}
