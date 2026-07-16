/**
 * Mirrors the backend's RFC 7807 ("problem+json") error envelope
 * (see traderbot-backend `app/interface/api/errors.py`) so every layer of
 * the frontend agrees on one error shape.
 */
export interface ProblemDetail {
  type: string
  title: string
  status: number
  detail: string
  trace_id: string | null
}

/** The normalized shape every failed request resolves to, regardless of
 * whether it failed before reaching the server (network/timeout) or after
 * (a problem+json response). */
export interface ApiError {
  status: number | 'NETWORK_ERROR' | 'TIMEOUT' | 'UNKNOWN'
  type: string
  message: string
  traceId: string | null
}

const FALLBACK_MESSAGE = 'Something went wrong. Please try again.'

export function isApiError(value: unknown): value is ApiError {
  return (
    typeof value === 'object' &&
    value !== null &&
    'status' in value &&
    'message' in value
  )
}

/** Best-effort human-readable message extraction, for inline form/UI use
 * (RTK Query error objects and raw ApiError objects both work). */
export function getApiErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    return error.message || FALLBACK_MESSAGE
  }
  if (
    typeof error === 'object' &&
    error !== null &&
    'data' in error &&
    isApiError((error as { data: unknown }).data)
  ) {
    return getApiErrorMessage((error as { data: unknown }).data)
  }
  return FALLBACK_MESSAGE
}
