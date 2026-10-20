import { Loader2, Route } from "lucide-react"

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
import type { SampleInterval } from "@/types/routing"

export interface TripFormValues {
  origin: string
  destination: string
  departureAt: string
  loadWeightLb: string
  sampleIntervalMiles: SampleInterval
}

interface TripFormProps {
  values: TripFormValues
  onChange: (values: TripFormValues) => void
  onSubmit: () => void
  loading: boolean
  error: string | null
}

const INTERVALS: SampleInterval[] = [10, 25, 50]

function toLocalInputValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function defaultTripFormValues(): TripFormValues {
  return {
    origin: "Chicago, IL",
    destination: "Detroit, MI",
    departureAt: toLocalInputValue(new Date()),
    loadWeightLb: "35000",
    sampleIntervalMiles: 25,
  }
}

export function TripForm({
  values,
  onChange,
  onSubmit,
  loading,
  error,
}: TripFormProps) {
  return (
    <Card className="border-border/80 bg-card/95 shadow-none backdrop-blur">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg">Plan a safer haul</CardTitle>
        <CardDescription>
          Compare three routes with weather risk sampled along the corridor.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="origin">Origin</Label>
          <Input
            id="origin"
            value={values.origin}
            onChange={(e) => onChange({ ...values, origin: e.target.value })}
            placeholder="City or address"
            disabled={loading}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="destination">Destination</Label>
          <Input
            id="destination"
            value={values.destination}
            onChange={(e) =>
              onChange({ ...values, destination: e.target.value })
            }
            placeholder="City or address"
            disabled={loading}
          />
        </div>
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
          />
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
          />
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

        {error ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-left text-sm text-destructive">
            {error}
          </div>
        ) : null}

        <Button
          className="w-full"
          size="lg"
          onClick={onSubmit}
          disabled={loading}
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
