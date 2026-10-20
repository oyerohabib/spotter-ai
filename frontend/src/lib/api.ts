import type { AnalyzeRequest, AnalyzeResponse } from "@/types/routing"

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export async function analyzeRoutes(
  payload: AnalyzeRequest,
): Promise<AnalyzeResponse> {
  const res = await fetch("/api/routes/analyze/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })

  let data: unknown = null
  try {
    data = await res.json()
  } catch {
    data = null
  }

  if (!res.ok) {
    const detail =
      data &&
      typeof data === "object" &&
      "detail" in data &&
      typeof (data as { detail: unknown }).detail === "string"
        ? (data as { detail: string }).detail
        : `Request failed (${res.status})`
    throw new ApiError(detail, res.status)
  }

  return data as AnalyzeResponse
}
