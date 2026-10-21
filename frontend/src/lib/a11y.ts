import { formatDuration, formatEta } from "@/lib/risk"
import type { AnalyzeResponse } from "@/types/routing"

export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches
}

export function buildRouteMapSummary(
  result: AnalyzeResponse,
  selectedRouteId: string | null,
): string {
  const route =
    result.routes.find((r) => r.id === selectedRouteId) ??
    result.routes.find((r) => r.id === result.recommended_route_id) ??
    result.routes[0]

  if (!route) {
    return "No route selected."
  }

  const routeIndex = result.routes.findIndex((r) => r.id === route.id) + 1
  const recommended =
    route.id === result.recommended_route_id ? " This is the recommended route." : ""

  const checkpointBits = route.checkpoints.slice(0, 5).map((cp) => {
    const risk = cp.risk ?? "Low"
    return `${cp.miles_from_origin.toFixed(0)} miles, ${risk} risk, ETA ${formatEta(cp.eta)}`
  })

  const more =
    route.checkpoints.length > 5
      ? ` Plus ${route.checkpoints.length - 5} more checkpoints.`
      : ""

  return [
    `Map showing route ${routeIndex} from ${result.origin.name} to ${result.destination.name}.`,
    `${route.distance_miles.toFixed(1)} miles, ${formatDuration(route.duration_minutes)}.`,
    `Maximum risk ${route.summary.max_risk}.`,
    recommended,
    checkpointBits.length
      ? `Checkpoints: ${checkpointBits.join("; ")}.${more}`
      : "",
  ]
    .filter(Boolean)
    .join(" ")
}
