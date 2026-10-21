import { useState } from "react"

import { ForecastSlider } from "@/components/ForecastSlider"
import { RouteMap } from "@/components/RouteMap"
import { RouteSummaryList } from "@/components/RouteSummaryList"
import {
  defaultTripFormValues,
  TripForm,
  type TripFieldErrors,
  type TripFormValues,
} from "@/components/TripForm"
import { analyzeRoutes, ApiError } from "@/lib/api"
import type { AnalyzeResponse, SelectedPlace } from "@/types/routing"

function almostSamePlace(a: SelectedPlace, b: SelectedPlace): boolean {
  return Math.abs(a.lon - b.lon) < 1e-5 && Math.abs(a.lat - b.lat) < 1e-5
}

export default function App() {
  const [form, setForm] = useState<TripFormValues>(defaultTripFormValues)
  const [selectedOrigin, setSelectedOrigin] = useState<SelectedPlace | null>(
    null,
  )
  const [selectedDestination, setSelectedDestination] =
    useState<SelectedPlace | null>(null)
  const [fieldErrors, setFieldErrors] = useState<TripFieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<AnalyzeResponse | null>(null)
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null)
  const [forecastHour, setForecastHour] = useState(0)

  function validate(): TripFieldErrors {
    const errors: TripFieldErrors = {}
    if (!selectedOrigin) {
      errors.origin = form.origin.trim()
        ? "Select a place from the list"
        : "Origin is required"
    }
    if (!selectedDestination) {
      errors.destination = form.destination.trim()
        ? "Select a place from the list"
        : "Destination is required"
    }
    if (
      selectedOrigin &&
      selectedDestination &&
      almostSamePlace(selectedOrigin, selectedDestination)
    ) {
      errors.destination = "Origin and destination must be different places"
    }
    if (!form.departureAt) {
      errors.departureAt = "Departure date/time is required"
    } else {
      const departure = new Date(form.departureAt)
      if (Number.isNaN(departure.getTime())) {
        errors.departureAt = "Enter a valid departure date and time"
      }
    }
    const load = Number(form.loadWeightLb)
    if (form.loadWeightLb.trim() === "" || !Number.isFinite(load)) {
      errors.loadWeightLb = "Load weight must be a number"
    } else if (load < 0) {
      errors.loadWeightLb = "Load weight must be zero or greater"
    }
    return errors
  }

  async function handleAnalyze() {
    setFormError(null)
    const errors = validate()
    setFieldErrors(errors)
    if (Object.keys(errors).length > 0) return
    if (!selectedOrigin || !selectedDestination) return

    setLoading(true)
    try {
      const departure = new Date(form.departureAt)
      const data = await analyzeRoutes({
        origin: selectedOrigin.name,
        destination: selectedDestination.name,
        origin_name: selectedOrigin.name,
        destination_name: selectedDestination.name,
        origin_lon: selectedOrigin.lon,
        origin_lat: selectedOrigin.lat,
        destination_lon: selectedDestination.lon,
        destination_lat: selectedDestination.lat,
        departure_at: departure.toISOString(),
        load_weight_lb: Number(form.loadWeightLb),
        sample_interval_miles: form.sampleIntervalMiles,
      })
      setResult(data)
      setSelectedRouteId(data.recommended_route_id ?? data.routes[0]?.id ?? null)
      setForecastHour(0)
      setFieldErrors({})
    } catch (err) {
      if (err instanceof ApiError && err.field) {
        const fieldMap: Record<string, keyof TripFieldErrors> = {
          origin: "origin",
          destination: "destination",
          departure_at: "departureAt",
          load_weight_lb: "loadWeightLb",
        }
        const key = fieldMap[err.field]
        if (key) {
          setFieldErrors({ [key]: err.message })
          setFormError(null)
          const el = document.getElementById(
            key === "departureAt" ? "departure" : key === "loadWeightLb" ? "load" : key,
          )
          el?.focus()
          return
        }
      }
      const message =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Something went wrong."
      setFormError(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative flex h-full min-h-svh flex-col overflow-hidden bg-background md:flex-row">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-70"
        style={{
          background:
            "radial-gradient(1200px 600px at 10% -10%, rgba(31,77,58,0.18), transparent 55%), radial-gradient(900px 500px at 90% 0%, rgba(196,92,38,0.12), transparent 50%), linear-gradient(180deg, #efe9dc 0%, #f3f1eb 40%, #e8e2d4 100%)",
        }}
      />

      <aside className="relative z-10 flex max-h-[48vh] w-full flex-col gap-3 overflow-y-auto border-b border-border/70 bg-background/40 p-4 backdrop-blur-md md:max-h-none md:max-w-sm md:border-b-0 md:border-r lg:max-w-md">
        <header className="px-1 pb-1 pt-2">
          <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-muted-foreground">
            Spotter
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-foreground">
            Weather-Aware Truck Routing
          </h1>
        </header>

        <TripForm
          values={form}
          selectedOrigin={selectedOrigin}
          selectedDestination={selectedDestination}
          fieldErrors={fieldErrors}
          formError={formError}
          onChange={(next) => {
            setForm(next)
            setFieldErrors({})
            setFormError(null)
          }}
          onSelectOrigin={(place) => {
            setSelectedOrigin(place)
            setFieldErrors((prev) => ({ ...prev, origin: undefined }))
          }}
          onSelectDestination={(place) => {
            setSelectedDestination(place)
            setFieldErrors((prev) => ({ ...prev, destination: undefined }))
          }}
          onClearOrigin={() => setSelectedOrigin(null)}
          onClearDestination={() => setSelectedDestination(null)}
          onSubmit={handleAnalyze}
          loading={loading}
        />

        {result ? (
          <RouteSummaryList
            routes={result.routes}
            recommendedRouteId={result.recommended_route_id}
            reason={result.recommendation_reason}
            selectedRouteId={selectedRouteId}
            onSelect={setSelectedRouteId}
          />
        ) : null}
      </aside>

      <main className="relative z-10 flex min-w-0 flex-1 flex-col">
        <div className="relative min-h-[50vh] flex-1 overflow-hidden border-l border-border/40 md:min-h-0">
          <RouteMap
            result={result}
            selectedRouteId={selectedRouteId}
            forecastHour={forecastHour}
            showHeatmap={Boolean(result)}
          />
          {!result ? (
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-background/20 p-6 text-center backdrop-blur-[1px]">
              <p className="max-w-md rounded-xl border border-border/70 bg-card/90 px-4 py-3 text-sm text-muted-foreground shadow-sm">
                Select origin and destination from the suggestions, then analyze
                to plot routes and weather risk.
              </p>
            </div>
          ) : (
            <div className="absolute inset-x-0 bottom-0 z-20 p-3 md:p-4">
              <ForecastSlider
                hour={forecastHour}
                onChange={setForecastHour}
                className="mx-auto max-w-xl"
              />
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
