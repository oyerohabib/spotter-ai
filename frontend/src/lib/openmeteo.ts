import type { WeatherSeries } from "@/types/routing"

const FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
const CHUNK_SIZE = 15
const MAX_RETRIES = 4

export class WeatherClientError extends Error {}

function pointKey(lon: number, lat: number): string {
  return `${lon.toFixed(3)},${lat.toFixed(3)}`
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

type OpenMeteoEntry = {
  error?: boolean
  reason?: string
  hourly?: {
    time?: string[]
    wind_speed_10m?: Array<number | null>
    precipitation?: Array<number | null>
    snowfall?: Array<number | null>
    temperature_2m?: Array<number | null>
  }
}

function entryToSeries(
  lon: number,
  lat: number,
  entry: OpenMeteoEntry,
): WeatherSeries {
  if (entry.error) {
    throw new WeatherClientError(
      entry.reason || "Open-Meteo returned an error for this location.",
    )
  }
  const hourly = entry.hourly || {}
  return {
    lon,
    lat,
    times: hourly.time || [],
    wind_mph: (hourly.wind_speed_10m || []).map((v) => Number(v || 0)),
    precip_in: (hourly.precipitation || []).map((v) => Number(v || 0)),
    snowfall: (hourly.snowfall || []).map((v) => Number(v || 0)),
    temp_c: (hourly.temperature_2m || []).map((v) => Number(v || 0)),
  }
}

async function fetchChunk(
  points: Array<{ lon: number; lat: number }>,
  forecastDays: number,
): Promise<WeatherSeries[]> {
  const params = new URLSearchParams({
    latitude: points.map((p) => p.lat.toFixed(5)).join(","),
    longitude: points.map((p) => p.lon.toFixed(5)).join(","),
    hourly: "wind_speed_10m,precipitation,snowfall,temperature_2m",
    wind_speed_unit: "mph",
    precipitation_unit: "inch",
    timezone: "UTC",
    forecast_days: String(forecastDays),
  })

  let lastError: Error | null = null
  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    let res: Response
    try {
      res = await fetch(`${FORECAST_URL}?${params.toString()}`)
    } catch (err) {
      lastError = new WeatherClientError(
        err instanceof Error ? err.message : "Open-Meteo network error",
      )
      await sleep(Math.min(1500 * 2 ** attempt, 20000))
      continue
    }

    if (res.status === 429 || res.status === 503) {
      const retryAfter = Number(res.headers.get("Retry-After"))
      const delayMs = Number.isFinite(retryAfter)
        ? retryAfter * 1000
        : Math.min(1500 * 2 ** attempt, 20000)
      lastError = new WeatherClientError(
        "Weather provider rate limit hit. Please try again shortly.",
      )
      await sleep(delayMs)
      continue
    }

    if (!res.ok) {
      const body = (await res.text()).slice(0, 200)
      throw new WeatherClientError(
        `Open-Meteo failed (${res.status}): ${body || res.statusText}`,
      )
    }

    const payload: OpenMeteoEntry | OpenMeteoEntry[] = await res.json()
    if (!Array.isArray(payload) && payload.error) {
      throw new WeatherClientError(
        payload.reason || "Open-Meteo returned an error.",
      )
    }
    const entries = Array.isArray(payload) ? payload : [payload]
    if (entries.length !== points.length) {
      throw new WeatherClientError(
        `Open-Meteo returned ${entries.length} locations for ${points.length} points.`,
      )
    }
    return entries.map((entry, i) =>
      entryToSeries(points[i].lon, points[i].lat, entry),
    )
  }

  throw lastError || new WeatherClientError("Open-Meteo request failed.")
}

/**
 * Fetch hourly weather for many lon/lat points from the browser (visitor IP).
 * Dedupes near-identical coordinates and chunks multi-location requests.
 */
export async function fetchHourlyWeather(
  points: Array<{ lon: number; lat: number }>,
  forecastDays = 3,
): Promise<WeatherSeries[]> {
  if (points.length === 0) return []

  const keys: string[] = []
  const keyToUniqueIdx = new Map<string, number>()
  const pointUniqueIdxs: number[] = []
  const uniquePoints: Array<{ lon: number; lat: number }> = []

  for (const point of points) {
    const key = pointKey(point.lon, point.lat)
    let uIdx = keyToUniqueIdx.get(key)
    if (uIdx === undefined) {
      uIdx = uniquePoints.length
      keyToUniqueIdx.set(key, uIdx)
      keys.push(key)
      uniquePoints.push({
        lon: Number(point.lon.toFixed(3)),
        lat: Number(point.lat.toFixed(3)),
      })
    }
    pointUniqueIdxs.push(uIdx)
  }

  const uniqueSeries: WeatherSeries[] = new Array(uniquePoints.length)
  for (let start = 0; start < uniquePoints.length; start += CHUNK_SIZE) {
    const chunk = uniquePoints.slice(start, start + CHUNK_SIZE)
    const fetched = await fetchChunk(chunk, forecastDays)
    for (let i = 0; i < fetched.length; i++) {
      uniqueSeries[start + i] = fetched[i]
    }
  }

  return pointUniqueIdxs.map((uIdx) => {
    const series = uniqueSeries[uIdx]
    if (!series) {
      throw new WeatherClientError("Missing weather series after Open-Meteo fetch.")
    }
    return series
  })
}
