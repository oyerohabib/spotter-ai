import type {
  AnalyzeRequest,
  AnalyzeResponse,
  PlaceSuggestion,
} from "@/types/routing"

export class ApiError extends Error {
  status: number
  field?: string

  constructor(message: string, status: number, field?: string) {
    super(message)
    this.status = status
    this.field = field
  }
}

async function parseJson(res: Response): Promise<unknown> {
  try {
    return await res.json()
  } catch {
    return null
  }
}

function throwApiError(res: Response, data: unknown): never {
  const detail =
    data &&
    typeof data === "object" &&
    "detail" in data &&
    typeof (data as { detail: unknown }).detail === "string"
      ? (data as { detail: string }).detail
      : `Request failed (${res.status})`
  const field =
    data &&
    typeof data === "object" &&
    "field" in data &&
    typeof (data as { field: unknown }).field === "string"
      ? (data as { field: string }).field
      : undefined
  throw new ApiError(detail, res.status, field)
}

export async function suggestPlaces(query: string): Promise<PlaceSuggestion[]> {
  const params = new URLSearchParams({ q: query })
  const res = await fetch(`/api/places/suggest/?${params.toString()}`)
  const data = await parseJson(res)
  if (!res.ok) {
    throwApiError(res, data)
  }
  const results =
    data &&
    typeof data === "object" &&
    "results" in data &&
    Array.isArray((data as { results: unknown }).results)
      ? (data as { results: PlaceSuggestion[] }).results
      : []
  return results
}

export async function analyzeRoutes(
  payload: AnalyzeRequest,
): Promise<AnalyzeResponse> {
  const res = await fetch("/api/routes/analyze/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })

  const data = await parseJson(res)
  if (!res.ok) {
    throwApiError(res, data)
  }

  return data as AnalyzeResponse
}
