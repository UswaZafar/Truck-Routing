import type { Map as MapLibreMap } from 'maplibre-gl'
import { useEffect, useMemo, useRef, useState } from 'react'

import { useHeatmap } from '../../api/queries'
import type { RouteOption } from '../../api/types'
import { formatClock, formatWeekday } from '../../lib/format'
import { buildHeatmapFrames } from '../../lib/heatmapFrames'
import { ForecastSlider, type TripWindow } from './ForecastSlider'
import { HeatmapGLLayer } from './heatmapGLLayer'
import { LAYER, firstLabelLayerId } from './layers'

interface Props {
  map: MapLibreMap
  planId: string
  /** Its time on the road is marked on the forecast timeline. */
  selectedRoute?: RouteOption
}

const HOUR_MS = 60 * 60 * 1000
const PLAY_STEP_MS = 500

/**
 * Corridor heatmap + 0–48 h timeline. Frames are built once per heatmap; moving the slider re-renders only
 * this component and swaps a GPU texture (see HeatmapGLLayer) — no network, no re-tiling, no style update.
 */
export function HeatmapLayer({ map, planId, selectedRoute }: Props) {
  const heatmap = useHeatmap(planId)
  const [hour, setHour] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [visible, setVisible] = useState(true)
  const layerRef = useRef<HeatmapGLLayer | null>(null)

  const data = heatmap.data
  const hours = data?.hours ?? 49
  const frames = useMemo(() => (data ? buildHeatmapFrames(data) : null), [data])
  // Worst risk index (0–4) anywhere in the corridor, per hour: the bars above the slider.
  const hourlyWorst = useMemo(
    () => data?.values.map((row) => row.reduce<number>((worst, value) => Math.max(worst, value ?? 0), 0) / 10) ?? null,
    [data],
  )

  useEffect(() => {
    if (!frames || !data) return
    const layer = new HeatmapGLLayer(LAYER.heatmap, frames, data.grid.bounds, data.grid)
    map.addLayer(layer, firstLabelLayerId(map)) // under place labels, routes and checkpoints
    layerRef.current = layer
    return () => {
      layerRef.current = null
      if (map.getLayer(LAYER.heatmap)) map.removeLayer(LAYER.heatmap)
    }
  }, [map, frames, data])

  useEffect(() => {
    layerRef.current?.setFrame(hour)
  }, [hour, frames])

  useEffect(() => {
    if (map.getLayer(LAYER.heatmap)) map.setLayoutProperty(LAYER.heatmap, 'visibility', visible ? 'visible' : 'none')
  }, [map, visible, frames])

  useEffect(() => {
    if (!playing) return
    const timer = window.setInterval(() => setHour((h) => (h + 1) % hours), PLAY_STEP_MS)
    return () => window.clearInterval(timer)
  }, [playing, hours])

  let trip: TripWindow | null = null
  if (data && selectedRoute) {
    const start = Date.parse(data.start)
    const arrival = Date.parse(selectedRoute.arrival_at)
    const departure = arrival - selectedRoute.duration_s * 1000
    const span = (hours - 1) * HOUR_MS
    trip = {
      from: Math.max(0, (departure - start) / span),
      to: Math.min(1, (arrival - start) / span),
      label: `Route ${selectedRoute.id} on the road until ${formatWeekday(selectedRoute.arrival_at)} ${formatClock(selectedRoute.arrival_at)}`,
    }
  }

  return (
    <ForecastSlider
      start={data?.start}
      hours={hours}
      hour={hour}
      onChange={(next) => {
        setPlaying(false)
        setHour(next)
      }}
      playing={playing}
      onTogglePlay={() => setPlaying((p) => !p)}
      visible={visible}
      onToggleVisible={setVisible}
      hourlyWorst={hourlyWorst}
      trip={trip}
      status={heatmap.isError ? 'error' : frames ? 'ready' : 'loading'}
      error={heatmap.error?.message}
      onRetry={() => heatmap.refetch()}
    />
  )
}
