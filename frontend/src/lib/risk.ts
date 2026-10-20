import type { RiskLabel } from "@/types/routing"

export const RISK_COLORS: Record<RiskLabel, string> = {
  Low: "#2f6b4f",
  Moderate: "#b8860b",
  High: "#c45c26",
  Severe: "#9b2c2c",
  "No Travel": "#2a211c",
}

export function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = Math.round(minutes % 60)
  if (h <= 0) return `${m}m`
  return `${h}h ${m}m`
}

export function formatEta(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  })
}
