// Shapes returned by the Django API (see backend/trips/services/planner.py and heatmap.py).

export type RiskKey = 'low' | 'moderate' | 'high' | 'severe' | 'no_travel'
export type Interval = 10 | 25 | 50

export interface Place {
  label: string
  lat: number
  lng: number
}

export interface TripRequest {
  /** A place picked from suggestions, or free text the server geocodes. */
  origin: Place | string
  destination: Place | string
  /** ISO 8601 with offset. */
  departure_at: string
  load_weight_lb: number
  interval_miles: Interval
}

export interface Checkpoint {
  mile: number
  lat: number
  lng: number
  eta: string
  wind_mph: number
  rain_in_hr: number
  snow_in_hr: number
  risk: RiskKey
  conditions: Array<'wind' | 'rain' | 'snow'>
  load_adjusted: boolean
  /** Route miles represented by this checkpoint. */
  miles: number
  forecast_complete: boolean
}

export interface RouteSummary {
  miles_by_risk: Record<RiskKey, number>
  average_risk: number
  max_risk: RiskKey
  no_travel: boolean
}

export interface RouteOption {
  id: string
  rank: number
  recommended: boolean
  source: 'osrm' | 'osrm-via'
  distance_mi: number
  duration_s: number
  arrival_at: string
  /** [lng, lat] pairs. */
  geometry: Array<[number, number]>
  summary: RouteSummary
  checkpoints: Checkpoint[]
}

export interface TripPlan {
  id: string
  created_at: string
  input: {
    origin: Place
    destination: Place
    departure_at: string
    load_weight_lb: number
    interval_miles: Interval
  }
  recommendation: {
    route_id: string
    ranking: string[]
    decided_by: string | null
    explanation: string
  }
  routes: RouteOption[]
  notes: string[]
}

export interface Heatmap {
  /** Hour 0 (the departure hour), ISO UTC. */
  start: string
  hours: number
  grid: {
    cols: number
    rows: number
    /** Image corners [lng, lat]: top-left, top-right, bottom-right, bottom-left. */
    bounds: Array<[number, number]>
  }
  /** Row-major pixel index (row 0 = north) of each corridor cell. */
  cells: number[]
  /** values[hour][cellIndex] = risk index × 10 (0–40), null when unavailable. */
  values: Array<Array<number | null>>
}
