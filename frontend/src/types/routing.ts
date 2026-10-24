export type RiskLabel = "Low" | "Moderate" | "High" | "Severe" | "No Travel"

export type SampleInterval = 10 | 25 | 50

export interface Place {
  query: string
  name: string
  lon: number
  lat: number
}

export interface PlaceSuggestion {
  id: string
  name: string
  lon: number
  lat: number
}

export interface SelectedPlace {
  name: string
  lon: number
  lat: number
}

export interface CheckpointWeather {
  wind_mph: number
  rain_in_hr: number
  snow_in_hr: number
  temp_c: number
  observed_at?: string
}

export interface Checkpoint {
  index: number
  lon: number
  lat: number
  miles_from_origin: number
  eta: string
  weather?: CheckpointWeather
  risk?: RiskLabel
  risk_score?: number
  wind_risk?: RiskLabel
  rain_risk?: RiskLabel
  snow_risk?: RiskLabel
  weather_risk?: RiskLabel
}

export interface RouteSummary {
  severe_miles: number
  high_miles: number
  no_travel_miles: number
  average_risk: number
  max_risk: RiskLabel
  checkpoint_count: number
}

export interface RouteOption {
  id: string
  distance_miles: number
  duration_seconds: number
  duration_minutes: number
  geometry: {
    type: "LineString"
    coordinates: [number, number][]
  }
  checkpoints: Checkpoint[]
  summary: RouteSummary
}

export interface HeatmapHourSample {
  hour_offset: number
  time: string
  wind_mph: number
  rain_in_hr: number
  snow_in_hr: number
  risk_score: number
  intensity: number
}

export interface HeatmapPoint {
  lon: number
  lat: number
  miles_from_origin: number
  hourly: HeatmapHourSample[]
}

export interface AnalyzeResponse {
  origin: Place
  destination: Place
  departure_at: string
  load_weight_lb: number
  sample_interval_miles: SampleInterval
  routes: RouteOption[]
  recommended_route_id: string | null
  recommendation_reason: string
  heatmap: {
    hours: number
    points: HeatmapPoint[]
  }
}

export interface AnalyzeRequest {
  origin: string
  destination: string
  departure_at: string
  load_weight_lb: number
  sample_interval_miles: SampleInterval
  origin_lon?: number
  origin_lat?: number
  origin_name?: string
  destination_lon?: number
  destination_lat?: number
  destination_name?: string
}

/** Checkpoint before weather/risk scoring. */
export interface PlannedCheckpoint {
  index: number
  lon: number
  lat: number
  miles_from_origin: number
  eta: string
}

export interface PlannedRoute {
  id: string
  distance_miles: number
  duration_seconds: number
  duration_minutes: number
  geometry: {
    type: "LineString"
    coordinates: [number, number][]
  }
  checkpoints: PlannedCheckpoint[]
}

export interface PlanResponse {
  origin: Place
  destination: Place
  departure_at: string
  load_weight_lb: number
  sample_interval_miles: SampleInterval
  routes: PlannedRoute[]
  heatmap: {
    hours: number
    points: Array<{ lon: number; lat: number; miles_from_origin: number }>
  }
  /** Ordered lon/lat list for browser Open-Meteo fetch (checkpoints then heatmap). */
  weather_points: Array<{ lon: number; lat: number }>
}

export interface WeatherSeries {
  lon?: number
  lat?: number
  times: string[]
  wind_mph: number[]
  precip_in: number[]
  snowfall: number[]
  temp_c: number[]
}
