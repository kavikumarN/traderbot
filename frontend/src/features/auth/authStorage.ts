import type { TokenPair } from './types'

/**
 * The backend hands refresh tokens back in the JSON response body rather
 * than an HttpOnly cookie (see Phase 1 `POST /auth/login`), so the SPA has
 * no choice but to hold onto them itself to survive a page reload.
 * localStorage is the pragmatic choice for a foundation phase; swapping the
 * backend to set an HttpOnly cookie for the refresh token is the natural
 * hardening step later and would let this module (and little else) go away.
 */
const STORAGE_KEY = 'traderbot.auth.tokens'

export function loadStoredTokens(): TokenPair | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    return JSON.parse(raw) as TokenPair
  } catch {
    return null
  }
}

export function saveStoredTokens(tokens: TokenPair): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(tokens))
}

export function clearStoredTokens(): void {
  localStorage.removeItem(STORAGE_KEY)
}
