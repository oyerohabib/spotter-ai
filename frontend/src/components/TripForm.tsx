import { Loader2, Route } from "lucide-react"

import { PlaceAutocomplete } from "@/components/PlaceAutocomplete"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"
import type { SampleInterval, SelectedPlace } from "@/types/routing"

export interface TripFormValues {
  origin: string
  destination: string
  departureAt: string
  loadWeightLb: string
  sampleIntervalMiles: SampleInterval
}

export type TripFieldErrors = Partial<
  Record<"origin" | "destination" | "departureAt" | "loadWeightLb", string>
>

interface TripFormProps {
  values: TripFormValues
  selectedOrigin: SelectedPlace | null
  selectedDestination: SelectedPlace | null
  fieldErrors: TripFieldErrors
  formError: string | null
  onChange: (values: TripFormValues) => void
  onSelectOrigin: (place: SelectedPlace) => void
  onSelectDestination: (place: SelectedPlace) => void
  onClearOrigin: () => void
  onClearDestination: () => void
  onSubmit: () => void
  loading: boolean
}

const INTERVALS: SampleInterval[] = [10, 25, 50]

function toLocalInputValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function defaultTripFormValues(): TripFormValues {
  return {
    origin: "",
    destination: "",
    departureAt: toLocalInputValue(new Date()),
    loadWeightLb: "35000",
    sampleIntervalMiles: 25,
  }
}

export function TripForm({
  values,
  selectedOrigin,
  selectedDestination,
  fieldErrors,
  formError,
  onChange,
  onSelectOrigin,
  onSelectDestination,
  onClearOrigin,
  onClearDestination,
  onSubmit,
  loading,
}: TripFormProps) {
  const canSubmit =
    !loading &&
    Boolean(selectedOrigin) &&
    Boolean(selectedDestination) &&
    Boolean(values.departureAt) &&
    values.loadWeightLb.trim() !== ""

  return (
    <Card className="border-border/80 bg-card/95 shadow-none backdrop-blur">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg">Plan a safer haul</CardTitle>
        <CardDescription>
          Search and select origin and destination, then compare weather-aware
          routes.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <PlaceAutocomplete
          id="origin"
          label="Origin"
          value={values.origin}
          selected={selectedOrigin}
          error={fieldErrors.origin}
          helperText={
            values.origin.trim() && !selectedOrigin
              ? "Select a place from the list"
              : null
          }
          disabled={loading}
          onQueryChange={(origin) => onChange({ ...values, origin })}
          onSelect={onSelectOrigin}
          onClearSelection={onClearOrigin}
        />

        <PlaceAutocomplete
          id="destination"
          label="Destination"
          value={values.destination}
          selected={selectedDestination}
          error={fieldErrors.destination}
          helperText={
            values.destination.trim() && !selectedDestination
              ? "Select a place from the list"
              : null
          }
          disabled={loading}
          onQueryChange={(destination) => onChange({ ...values, destination })}
          onSelect={onSelectDestination}
          onClearSelection={onClearDestination}
        />

        <div className="space-y-2">
          <Label htmlFor="departure">Departure</Label>
          <Input
            id="departure"
            type="datetime-local"
            value={values.departureAt}
            onChange={(e) =>
              onChange({ ...values, departureAt: e.target.value })
            }
            disabled={loading}
            aria-invalid={Boolean(fieldErrors.departureAt)}
            className={cn(
              fieldErrors.departureAt &&
                "border-destructive focus-visible:ring-destructive",
            )}
          />
          {fieldErrors.departureAt ? (
            <p className="text-xs text-destructive">{fieldErrors.departureAt}</p>
          ) : null}
        </div>

        <div className="space-y-2">
          <Label htmlFor="load">Load weight (lb)</Label>
          <Input
            id="load"
            type="number"
            min={0}
            step={500}
            value={values.loadWeightLb}
            onChange={(e) =>
              onChange({ ...values, loadWeightLb: e.target.value })
            }
            disabled={loading}
            aria-invalid={Boolean(fieldErrors.loadWeightLb)}
            className={cn(
              fieldErrors.loadWeightLb &&
                "border-destructive focus-visible:ring-destructive",
            )}
          />
          {fieldErrors.loadWeightLb ? (
            <p className="text-xs text-destructive">{fieldErrors.loadWeightLb}</p>
          ) : null}
        </div>

        <div className="space-y-2">
          <Label>Weather sample interval</Label>
          <div className="grid grid-cols-3 gap-2">
            {INTERVALS.map((interval) => {
              const active = values.sampleIntervalMiles === interval
              return (
                <button
                  key={interval}
                  type="button"
                  disabled={loading}
                  onClick={() =>
                    onChange({ ...values, sampleIntervalMiles: interval })
                  }
                  className={`h-10 rounded-md border text-sm font-medium transition-colors ${
                    active
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-card text-foreground hover:bg-muted"
                  }`}
                >
                  {interval} mi
                </button>
              )
            })}
          </div>
        </div>

        {formError ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-left text-sm text-destructive">
            {formError}
          </div>
        ) : null}

        <Button
          className="w-full"
          size="lg"
          onClick={onSubmit}
          disabled={!canSubmit}
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Analyzing routes…
            </>
          ) : (
            <>
              <Route className="h-4 w-4" />
              Analyze routes
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  )
}
