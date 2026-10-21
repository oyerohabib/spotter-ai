import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { formatDuration, RISK_COLORS } from "@/lib/risk"
import { cn } from "@/lib/utils"
import type { RouteOption } from "@/types/routing"

interface RouteSummaryListProps {
  routes: RouteOption[]
  recommendedRouteId: string | null
  reason: string
  selectedRouteId: string | null
  onSelect: (routeId: string) => void
}

export function RouteSummaryList({
  routes,
  recommendedRouteId,
  reason,
  selectedRouteId,
  onSelect,
}: RouteSummaryListProps) {
  if (!routes.length) return null

  return (
    <Card className="border-border/80 bg-card/95 shadow-none">
      <CardHeader className="pb-2">
        <CardTitle className="text-base" id="route-options-title">
          Route options
        </CardTitle>
        {recommendedRouteId ? (
          <p
            id="route-options-reason"
            className="text-xs leading-relaxed text-muted-foreground"
          >
            {reason}
          </p>
        ) : null}
      </CardHeader>
      <CardContent>
        <ul
          role="list"
          aria-labelledby="route-options-title"
          aria-describedby={recommendedRouteId ? "route-options-reason" : undefined}
          className="space-y-2"
        >
          {routes.map((route, index) => {
            const isRecommended = route.id === recommendedRouteId
            const isSelected = route.id === selectedRouteId
            const maxRisk = route.summary.max_risk
            const label = [
              `Route ${index + 1}`,
              isRecommended ? "recommended" : null,
              `${route.distance_miles.toFixed(1)} miles`,
              formatDuration(route.duration_minutes),
              `max risk ${maxRisk}`,
              isSelected ? "currently selected" : null,
            ]
              .filter(Boolean)
              .join(", ")

            return (
              <li key={route.id}>
                <button
                  type="button"
                  aria-pressed={isSelected}
                  aria-label={label}
                  onClick={() => onSelect(route.id)}
                  className={cn(
                    "w-full rounded-lg border px-3 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    isSelected
                      ? "border-primary bg-primary/5"
                      : "border-border bg-card hover:bg-muted/60",
                  )}
                >
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-medium" aria-hidden>
                        Route {index + 1}
                      </span>
                      {isRecommended ? (
                        <Badge variant="accent">Recommended</Badge>
                      ) : null}
                    </div>
                    <span
                      className="rounded-full px-2 py-0.5 text-[11px] font-medium text-white"
                      style={{ backgroundColor: RISK_COLORS[maxRisk] }}
                      aria-hidden
                    >
                      {maxRisk}
                    </span>
                  </div>
                  <div
                    className="grid grid-cols-2 gap-x-3 gap-y-1 font-mono text-[11px] text-muted-foreground"
                    aria-hidden
                  >
                    <span>{route.distance_miles.toFixed(1)} mi</span>
                    <span>{formatDuration(route.duration_minutes)}</span>
                    <span>Severe {route.summary.severe_miles.toFixed(1)} mi</span>
                    <span>High {route.summary.high_miles.toFixed(1)} mi</span>
                    <span className="col-span-2">
                      Avg risk {route.summary.average_risk.toFixed(2)} ·{" "}
                      {route.checkpoints.length} checkpoints
                    </span>
                  </div>
                </button>
              </li>
            )
          })}
        </ul>
      </CardContent>
    </Card>
  )
}
