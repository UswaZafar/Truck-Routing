import type { Feature, FeatureCollection } from 'geojson'
import type { ExpressionSpecification, Map as MapLibreMap } from 'maplibre-gl'

import type { Checkpoint, RouteOption } from '../../api/types'
import { formatDateTime, formatDuration, formatMiles, formatTime } from '../../lib/format'
import { RISK_LEVELS, riskMeta } from '../../lib/risk'

export const STYLE_URL = 'https://tiles.openfreemap.org/styles/positron'
export const US_CENTER: [number, number] = [-98.5, 39.5]

export const SOURCE = { routes: 'routes', checkpoints: 'checkpoints' } as const
export const LAYER = {
  heatmap: 'heatmap', // custom WebGL layer, see heatmapGLLayer.ts
  routeCasing: 'route-casing',
  routeLine: 'route-line',
  checkpoints: 'checkpoints',
} as const

const INK = '#15171C'
const ROUTE_MUTED = '#8C919B'
const SELECTED = ['get', 'selected'] as ExpressionSpecification
const IS_LOW = ['==', ['get', 'risk'], 'low'] as ExpressionSpecification
const IS_NO_TRAVEL = ['==', ['get', 'risk'], 'no_travel'] as ExpressionSpecification
const RISK_COLOR = [
  'match',
  ['get', 'risk'],
  ...RISK_LEVELS.flatMap((level) => [level.key, level.color]),
  ROUTE_MUTED,
] as unknown as ExpressionSpecification

const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] }

/** The basemap's first label layer, so overlays can be inserted underneath place names. */
export const firstLabelLayerId = (map: MapLibreMap) => map.getStyle().layers.find((layer) => layer.type === 'symbol')?.id

// Warmer land and softer water than stock Positron, to sit with the panel's paper tone.
const BASEMAP_PAINT: Array<[layer: string, property: Parameters<MapLibreMap['setPaintProperty']>[1], value: string]> = [
  ['background', 'background-color', '#EFEDE7'],
  ['park', 'fill-color', '#E3E7DC'],
  ['landcover_wood', 'fill-color', '#DDE3D6'],
  ['landuse_residential', 'fill-color', '#E8E5DE'],
  ['building', 'fill-color', '#E5E2DB'],
  ['water', 'fill-color', '#C5D3DA'],
  ['waterway', 'line-color', '#BCCDD5'],
  ['boundary_3', 'line-color', '#B8B3A9'],
  ['boundary_2', 'line-color', '#A9A398'],
]

export function tuneBasemap(map: MapLibreMap) {
  for (const [layer, property, value] of BASEMAP_PAINT) {
    if (map.getLayer(layer)) map.setPaintProperty(layer, property, value)
  }
}

/** Adds route and checkpoint layers on top of the basemap (the heatmap is added per plan by HeatmapLayer). */
export function addTripLayers(map: MapLibreMap) {
  map.addSource(SOURCE.routes, { type: 'geojson', data: EMPTY })
  map.addLayer({
    id: LAYER.routeCasing,
    type: 'line',
    source: SOURCE.routes,
    layout: { 'line-join': 'round', 'line-cap': 'round' },
    paint: { 'line-color': '#FFFFFF', 'line-width': ['case', SELECTED, 10, 6.5] },
  })
  map.addLayer({
    id: LAYER.routeLine,
    type: 'line',
    source: SOURCE.routes,
    layout: { 'line-join': 'round', 'line-cap': 'round' },
    paint: {
      'line-color': ['case', SELECTED, INK, ROUTE_MUTED],
      'line-width': ['case', SELECTED, 5, 3.5],
    },
  })

  // Low checkpoints are hollow so the coloured (risky) ones stand out; No Travel gets a dark ring.
  map.addSource(SOURCE.checkpoints, { type: 'geojson', data: EMPTY })
  map.addLayer({
    id: LAYER.checkpoints,
    type: 'circle',
    source: SOURCE.checkpoints,
    layout: { 'circle-sort-key': ['case', SELECTED, ['case', IS_LOW, 1, 2], 0] },
    paint: {
      'circle-color': ['case', IS_LOW, '#FFFFFF', RISK_COLOR],
      'circle-radius': [
        'interpolate', ['linear'], ['zoom'],
        4, ['case', SELECTED, ['case', IS_LOW, 3.5, IS_NO_TRAVEL, 7, 5.5], 2.5],
        10, ['case', SELECTED, ['case', IS_LOW, 6, IS_NO_TRAVEL, 11, 9], 5],
      ],
      'circle-stroke-color': ['case', IS_NO_TRAVEL, INK, IS_LOW, ['case', SELECTED, INK, ROUTE_MUTED], '#FFFFFF'],
      'circle-stroke-width': ['case', SELECTED, ['case', IS_LOW, 2, 2.5], 1],
      'circle-opacity': ['case', SELECTED, 1, 0.6],
      'circle-stroke-opacity': ['case', SELECTED, 1, 0.6],
    },
  })
}

/** Route lines; the selected one is last so it draws on top. */
export function routesGeoJSON(routes: RouteOption[], selectedId: string | null): FeatureCollection {
  const ordered = [...routes].sort((a, b) => Number(a.id === selectedId) - Number(b.id === selectedId))
  return {
    type: 'FeatureCollection',
    features: ordered.map((route) => ({
      type: 'Feature',
      properties: { id: route.id, selected: route.id === selectedId },
      geometry: { type: 'LineString', coordinates: route.geometry },
    })),
  }
}

/** Checkpoints of every route; properties reference the plan for popups (route id + index). */
export function checkpointsGeoJSON(routes: RouteOption[], selectedId: string | null): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: routes.flatMap((route) =>
      route.checkpoints.map(
        (cp, index): Feature => ({
          type: 'Feature',
          properties: { route: route.id, index, risk: cp.risk, selected: route.id === selectedId },
          geometry: { type: 'Point', coordinates: [cp.lng, cp.lat] },
        }),
      ),
    ),
  }
}

export function boundsOf(routes: RouteOption[]): [[number, number], [number, number]] {
  let west = Infinity, south = Infinity, east = -Infinity, north = -Infinity
  for (const route of routes) {
    for (const [lng, lat] of route.geometry) {
      west = Math.min(west, lng)
      east = Math.max(east, lng)
      south = Math.min(south, lat)
      north = Math.max(north, lat)
    }
  }
  return [
    [west, south],
    [east, north],
  ]
}

/** Point a given fraction of the way along a route (by vertex count — fine for label placement). */
export function pointAlong(route: RouteOption, fraction: number): [number, number] {
  return route.geometry[Math.min(route.geometry.length - 1, Math.floor(route.geometry.length * fraction))]
}

const escape = (text: string) =>
  text.replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch]!)

export function checkpointPopupHTML(route: RouteOption, cp: Checkpoint): string {
  const risk = riskMeta(cp.risk)
  const cause = cp.conditions.length ? ` — ${cp.conditions.join(' + ')}` : ''
  return `
    <div class="popup">
      <p class="popup__title">Route ${escape(route.id)} · mile ${cp.mile.toFixed(0)}</p>
      <p>ETA <strong>${escape(formatDateTime(cp.eta))}</strong></p>
      <p><span class="risk-chip" style="background:${risk.tint};color:${risk.ink}">${escape(risk.label)}</span>${escape(cause)}${
        cp.load_adjusted ? ' <em>(raised by load rule)</em>' : ''
      }</p>
      <table>
        <tr><th>Wind</th><td>${cp.wind_mph.toFixed(1)} mph</td></tr>
        <tr><th>Rain</th><td>${cp.rain_in_hr.toFixed(2)} in/hr</td></tr>
        <tr><th>Snow</th><td>${cp.snow_in_hr.toFixed(2)} in/hr</td></tr>
      </table>
      ${cp.forecast_complete ? '' : '<p class="muted">Forecast incomplete at this time.</p>'}
    </div>`
}

export function routePopupHTML(route: RouteOption): string {
  const s = route.summary
  const rows = RISK_LEVELS.map(
    (level) => `<tr><th><span class="dot" style="background:${level.color}"></span>${escape(level.label)}</th><td>${formatMiles(s.miles_by_risk[level.key], 1)}</td></tr>`,
  ).join('')
  return `
    <div class="popup">
      <p class="popup__title">Route ${escape(route.id)} · #${route.rank}${route.recommended ? ' · Recommended' : ''}</p>
      <p>${formatMiles(route.distance_mi)} · ${formatDuration(route.duration_s)} · arrives ${escape(formatTime(route.arrival_at))}</p>
      <p>Average risk ${s.average_risk.toFixed(2)} / 4</p>
      <table>${rows}</table>
    </div>`
}
