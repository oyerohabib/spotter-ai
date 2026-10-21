import type { FeatureCollection, Point } from "geojson"
import mapboxgl from "mapbox-gl"
import { useEffect, useRef } from "react"
import "mapbox-gl/dist/mapbox-gl.css"

import { prefersReducedMotion, buildRouteMapSummary } from "@/lib/a11y"
import { formatEta, RISK_COLORS } from "@/lib/risk"
import type { AnalyzeResponse, HeatmapPoint, RiskLabel } from "@/types/routing"

function fitDurationMs(): number {
  return prefersReducedMotion() ? 0 : 800
}

const ROUTE_COLORS = ["#1f4d3a", "#3d6e8c", "#8a6a3d"]

interface RouteMapProps {
  result: AnalyzeResponse | null
  selectedRouteId: string | null
  forecastHour: number
  showHeatmap: boolean
}

function token(): string {
  return import.meta.env.VITE_MAPBOX_ACCESS_TOKEN || ""
}

function boundsFromResult(result: AnalyzeResponse): mapboxgl.LngLatBounds {
  const bounds = new mapboxgl.LngLatBounds()
  bounds.extend([result.origin.lon, result.origin.lat])
  bounds.extend([result.destination.lon, result.destination.lat])
  for (const route of result.routes) {
    for (const coord of route.geometry.coordinates) {
      bounds.extend(coord as [number, number])
    }
  }
  return bounds
}

function heatmapGeoJSON(
  points: HeatmapPoint[],
  hour: number,
): FeatureCollection {
  return {
    type: "FeatureCollection",
    features: points.map((p) => {
      const sample =
        p.hourly.find((h) => h.hour_offset === hour) ??
        p.hourly[Math.min(hour, p.hourly.length - 1)]
      return {
        type: "Feature",
        properties: {
          intensity: sample?.intensity ?? 0,
          risk_score: sample?.risk_score ?? 0,
        },
        geometry: {
          type: "Point",
          coordinates: [p.lon, p.lat],
        },
      }
    }),
  }
}

function routesGeoJSON(
  result: AnalyzeResponse,
  selectedRouteId: string | null,
): FeatureCollection {
  return {
    type: "FeatureCollection",
    features: result.routes.map((route, index) => ({
      type: "Feature",
      properties: {
        id: route.id,
        selected: route.id === selectedRouteId,
        recommended: route.id === result.recommended_route_id,
        color: ROUTE_COLORS[index % ROUTE_COLORS.length],
      },
      geometry: route.geometry,
    })),
  }
}

function checkpointsGeoJSON(
  result: AnalyzeResponse,
  selectedRouteId: string | null,
): FeatureCollection {
  const route =
    result.routes.find((r) => r.id === selectedRouteId) ??
    result.routes.find((r) => r.id === result.recommended_route_id) ??
    result.routes[0]

  if (!route) {
    return { type: "FeatureCollection", features: [] }
  }

  return {
    type: "FeatureCollection",
    features: route.checkpoints.map((cp) => ({
      type: "Feature",
      properties: {
        risk: cp.risk ?? "Low",
        color: RISK_COLORS[(cp.risk ?? "Low") as RiskLabel],
        miles: cp.miles_from_origin,
        eta: cp.eta,
        wind: cp.weather?.wind_mph ?? 0,
        rain: cp.weather?.rain_in_hr ?? 0,
        snow: cp.weather?.snow_in_hr ?? 0,
      },
      geometry: {
        type: "Point",
        coordinates: [cp.lon, cp.lat],
      },
    })),
  }
}

export function RouteMap({
  result,
  selectedRouteId,
  forecastHour,
  showHeatmap,
}: RouteMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<mapboxgl.Map | null>(null)
  const popupRef = useRef<mapboxgl.Popup | null>(null)
  const resultRef = useRef(result)
  const selectedRef = useRef(selectedRouteId)

  resultRef.current = result
  selectedRef.current = selectedRouteId

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return
    const accessToken = token()
    if (!accessToken) return

    mapboxgl.accessToken = accessToken
    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: "mapbox://styles/mapbox/light-v11",
      center: [-87.65, 41.88],
      zoom: 5,
      attributionControl: true,
    })
    map.addControl(new mapboxgl.NavigationControl({ visualizePitch: false }), "top-right")
    popupRef.current = new mapboxgl.Popup({
      closeButton: false,
      closeOnClick: false,
      offset: 12,
      className: "spotter-popup",
    })

    map.on("load", () => {
      map.addSource("routes", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      })
      map.addSource("checkpoints", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      })
      map.addSource("heatmap", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      })

      map.addLayer({
        id: "heatmap-layer",
        type: "heatmap",
        source: "heatmap",
        maxzoom: 12,
        paint: {
          "heatmap-weight": ["interpolate", ["linear"], ["get", "intensity"], 0, 0, 1, 1],
          "heatmap-intensity": 1.1,
          "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 4, 18, 10, 40],
          "heatmap-opacity": 0.75,
          "heatmap-color": [
            "interpolate",
            ["linear"],
            ["heatmap-density"],
            0,
            "rgba(47,107,79,0)",
            0.2,
            "rgba(47,107,79,0.45)",
            0.4,
            "rgba(184,134,11,0.55)",
            0.65,
            "rgba(196,92,38,0.65)",
            0.85,
            "rgba(155,44,44,0.75)",
            1,
            "rgba(42,33,28,0.85)",
          ],
        },
      })

      map.addLayer({
        id: "routes-casing",
        type: "line",
        source: "routes",
        paint: {
          "line-color": "#ffffff",
          "line-width": [
            "case",
            ["boolean", ["get", "selected"], false],
            8,
            5,
          ],
          "line-opacity": 0.9,
        },
        layout: {
          "line-cap": "round",
          "line-join": "round",
        },
      })

      map.addLayer({
        id: "routes-line",
        type: "line",
        source: "routes",
        paint: {
          "line-color": ["get", "color"],
          "line-width": [
            "case",
            ["boolean", ["get", "selected"], false],
            5,
            3,
          ],
          "line-opacity": [
            "case",
            ["boolean", ["get", "selected"], false],
            1,
            0.55,
          ],
        },
        layout: {
          "line-cap": "round",
          "line-join": "round",
        },
      })

      map.addLayer({
        id: "checkpoints-circle",
        type: "circle",
        source: "checkpoints",
        paint: {
          "circle-radius": 6,
          "circle-color": ["get", "color"],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#fffaf3",
        },
      })

      map.on("mousemove", "checkpoints-circle", (e) => {
        if (!e.features?.length || !popupRef.current) return
        const f = e.features[0] as unknown as {
          properties?: Record<string, string | number>
          geometry: Point
        }
        const props = f.properties ?? {}
        map.getCanvas().style.cursor = "pointer"
        popupRef.current
          .setLngLat(f.geometry.coordinates as [number, number])
          .setHTML(
            `<div style="font:12px/1.4 DM Sans,sans-serif;color:#1a1f16">
              <strong>${props.risk ?? "Low"}</strong> · ${Number(props.miles).toFixed(1)} mi<br/>
              ETA ${formatEta(String(props.eta))}<br/>
              Wind ${Number(props.wind).toFixed(0)} mph · Rain ${Number(props.rain).toFixed(2)} in/hr · Snow ${Number(props.snow).toFixed(2)} in/hr
            </div>`,
          )
          .addTo(map)
      })
      map.on("mouseleave", "checkpoints-circle", () => {
        map.getCanvas().style.cursor = ""
        popupRef.current?.remove()
      })

      const current = resultRef.current
      if (current) {
        const routesSource = map.getSource("routes") as mapboxgl.GeoJSONSource
        const cpSource = map.getSource("checkpoints") as mapboxgl.GeoJSONSource
        routesSource.setData(routesGeoJSON(current, selectedRef.current))
        cpSource.setData(checkpointsGeoJSON(current, selectedRef.current))
        map.fitBounds(boundsFromResult(current), {
          padding: 64,
          duration: fitDurationMs(),
        })
      }
    })

    mapRef.current = map
    return () => {
      popupRef.current?.remove()
      map.remove()
      mapRef.current = null
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !result || !map.isStyleLoaded()) return

    const routesSource = map.getSource("routes") as mapboxgl.GeoJSONSource | undefined
    const cpSource = map.getSource("checkpoints") as mapboxgl.GeoJSONSource | undefined
    if (!routesSource || !cpSource) return

    routesSource.setData(routesGeoJSON(result, selectedRouteId))
    cpSource.setData(checkpointsGeoJSON(result, selectedRouteId))
    map.fitBounds(boundsFromResult(result), {
      padding: 64,
      duration: fitDurationMs(),
    })
  }, [result])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !result || !map.isStyleLoaded()) return
    const routesSource = map.getSource("routes") as mapboxgl.GeoJSONSource | undefined
    const cpSource = map.getSource("checkpoints") as mapboxgl.GeoJSONSource | undefined
    if (!routesSource || !cpSource) return
    routesSource.setData(routesGeoJSON(result, selectedRouteId))
    cpSource.setData(checkpointsGeoJSON(result, selectedRouteId))
  }, [selectedRouteId, result])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.isStyleLoaded()) return
    const source = map.getSource("heatmap") as mapboxgl.GeoJSONSource | undefined
    if (!source) return

    if (!result || !showHeatmap) {
      source.setData({ type: "FeatureCollection", features: [] })
      return
    }
    source.setData(heatmapGeoJSON(result.heatmap.points, forecastHour))
  }, [result, forecastHour, showHeatmap])

  const accessToken = token()

  const summary =
    result != null ? buildRouteMapSummary(result, selectedRouteId) : null

  if (!accessToken) {
    return (
      <div
        role="region"
        aria-label="Route map"
        className="flex h-full items-center justify-center bg-muted/40 p-6 text-center"
      >
        <p className="max-w-sm text-sm text-muted-foreground">
          Set <code className="font-mono text-foreground">VITE_MAPBOX_ACCESS_TOKEN</code>{" "}
          in your <code className="font-mono text-foreground">.env</code> to render the map.
        </p>
      </div>
    )
  }

  return (
    <div
      role="region"
      aria-label="Route map"
      className="relative h-full w-full"
    >
      {summary ? <p className="sr-only">{summary}</p> : null}
      <div ref={containerRef} className="h-full w-full" />
    </div>
  )
}
