import { useState } from "react"

import {
  defaultTripFormValues,
  TripForm,
  type TripFormValues,
} from "@/components/TripForm"
import { RouteSummaryList } from "@/components/RouteSummaryList"
import { analyzeRoutes, ApiError } from "@/lib/api"
import type { AnalyzeResponse } from "@/types/routing"

export default function App() {
  const [form, setForm] = useState<TripFormValues>(defaultTripFormValues)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<AnalyzeResponse | null>(null)
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null)

  async function handleAnalyze() {
    setError(null)
    const load = Number(form.loadWeightLb)
    if (!form.origin.trim() || !form.destination.trim()) {
      setError("Origin and destination are required.")
      return
    }
    if (!Number.isFinite(load) || load < 0) {
      setError("Load weight must be a non-negative number.")
      return
    }
    if (!form.departureAt) {
      setError("Departure date/time is required.")
      return
    }

    setLoading(true)
    try {
      const departure = new Date(form.departureAt)
      const data = await analyzeRoutes({
        origin: form.origin.trim(),
        destination: form.destination.trim(),
        departure_at: departure.toISOString(),
        load_weight_lb: load,
        sample_interval_miles: form.sampleIntervalMiles,
      })
      setResult(data)
      setSelectedRouteId(data.recommended_route_id ?? data.routes[0]?.id ?? null)
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Something went wrong."
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative flex h-full min-h-svh overflow-hidden bg-background">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-70"
        style={{
          background:
            "radial-gradient(1200px 600px at 10% -10%, rgba(31,77,58,0.18), transparent 55%), radial-gradient(900px 500px at 90% 0%, rgba(196,92,38,0.12), transparent 50%), linear-gradient(180deg, #efe9dc 0%, #f3f1eb 40%, #e8e2d4 100%)",
        }}
      />

      <aside className="relative z-10 flex w-full max-w-md flex-col gap-3 overflow-y-auto border-r border-border/70 bg-background/40 p-4 backdrop-blur-md md:max-w-sm lg:max-w-md">
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
          onChange={setForm}
          onSubmit={handleAnalyze}
          loading={loading}
          error={error}
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
        <div className="flex flex-1 items-center justify-center p-6 text-center">
          <div className="max-w-md space-y-2">
            <p className="text-sm font-medium text-foreground">
              {result
                ? "Map view lands next — route data is ready."
                : "Enter a trip and analyze to unlock map routes and weather risk."}
            </p>
            {result ? (
              <p className="font-mono text-xs text-muted-foreground">
                {result.routes.length} routes · recommended{" "}
                {result.recommended_route_id ?? "n/a"}
              </p>
            ) : null}
          </div>
        </div>
      </main>
    </div>
  )
}
