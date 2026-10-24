import type {
  AnalyzeRequest,
  AnalyzeResponse,
  PlaceSuggestion,
  PlanResponse,
  WeatherSeries,
} from "@/types/routing"
import { fetchHourlyWeather, WeatherClientError } from "@/lib/openmeteo"

export class ApiError extends Error {
  status: number
  field?: string

  constructor(message: string, status: number, field?: string) {
    super(message)
    this.status = status
    this.field = field
  }
}

async function parseJson(res: Response): Promise<unknown> {
  try {
    return await res.json()
  } catch {
    return null
  }
}

function throwApiError(res: Response, data: unknown): never {
  const detail =
    data &&
    typeof data === "object" &&
    "detail" in data &&
    typeof (data as { detail: unknown }).detail === "string"
      ? (data as { detail: string }).detail
      : `Request failed (${res.status})`
  const field =
    data &&
    typeof data === "object" &&
    "field" in data &&
    typeof (data as { field: unknown }).field === "string"
      ? (data as { field: string }).field
      : undefined
  throw new ApiError(detail, res.status, field)
}

export async function suggestPlaces(query: string): Promise<PlaceSuggestion[]> {
  const params = new URLSearchParams({ q: query })
  const res = await fetch(`/api/places/suggest/?${params.toString()}`)
  const data = await parseJson(res)
  if (!res.ok) {
    throwApiError(res, data)
  }
  const results =
    data &&
    typeof data === "object" &&
    "results" in data &&
    Array.isArray((data as { results: unknown }).results)
      ? (data as { results: PlaceSuggestion[] }).results
      : []
  return results
}

async function planRoutes(payload: AnalyzeRequest): Promise<PlanResponse> {
  const res = await fetch("/api/routes/plan/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  const data = await parseJson(res)
  if (!res.ok) {
    throwApiError(res, data)
  }
  return data as PlanResponse
}

async function scoreRoutes(
  plan: PlanResponse,
  weatherSeries: WeatherSeries[],
): Promise<AnalyzeResponse> {
  const res = await fetch("/api/routes/score/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      plan,
      weather_series: weatherSeries,
    }),
  })
  const data = await parseJson(res)
  if (!res.ok) {
    throwApiError(res, data)
  }
  return data as AnalyzeResponse
}

/**
 * Plan routes on the server (Mapbox), fetch Open-Meteo in the browser,
 * then score risk on the server.
 */
export async function analyzeRoutes(
  payload: AnalyzeRequest,
): Promise<AnalyzeResponse> {
  const plan = await planRoutes(payload)
  let weatherSeries: WeatherSeries[]
  try {
    weatherSeries = await fetchHourlyWeather(plan.weather_points, 3)
  } catch (err) {
    if (err instanceof WeatherClientError) {
      throw new ApiError(err.message, 502)
    }
    throw err
  }
  return scoreRoutes(plan, weatherSeries)
}
