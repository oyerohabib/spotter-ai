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
        <CardTitle className="text-base">Route options</CardTitle>
        {recommendedRouteId ? (
          <p className="text-xs leading-relaxed text-muted-foreground">{reason}</p>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-2">
        {routes.map((route, index) => {
          const isRecommended = route.id === recommendedRouteId
          const isSelected = route.id === selectedRouteId
          const maxRisk = route.summary.max_risk
          return (
            <button
              key={route.id}
              type="button"
              onClick={() => onSelect(route.id)}
              className={cn(
                "w-full rounded-lg border px-3 py-3 text-left transition-colors",
                isSelected
                  ? "border-primary bg-primary/5"
                  : "border-border bg-card hover:bg-muted/60",
              )}
            >
              <div className="mb-2 flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="font-medium">Route {index + 1}</span>
                  {isRecommended ? <Badge variant="accent">Recommended</Badge> : null}
                </div>
                <span
                  className="rounded-full px-2 py-0.5 text-[11px] font-medium text-white"
                  style={{ backgroundColor: RISK_COLORS[maxRisk] }}
                >
                  {maxRisk}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-x-3 gap-y-1 font-mono text-[11px] text-muted-foreground">
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
          )
        })}
      </CardContent>
    </Card>
  )
}
