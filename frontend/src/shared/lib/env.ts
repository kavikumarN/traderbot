/**
 * Fail fast on a missing/misconfigured environment instead of letting a
 * blank API base URL surface later as a confusing network error.
 */
function readApiBaseUrl(): string {
  const value = import.meta.env.VITE_API_BASE_URL
  if (!value) {
    throw new Error(
      'VITE_API_BASE_URL is not set. Copy .env.example to .env.local and set it.',
    )
  }
  return value.replace(/\/+$/, '')
}

export const env = {
  apiBaseUrl: readApiBaseUrl(),
} as const
