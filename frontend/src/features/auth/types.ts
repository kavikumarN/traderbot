export interface AuthUser {
  id: string
  email: string
  first_name: string
  last_name: string
  is_active: boolean
  is_verified: boolean
  role_names: string[]
  created_at: string
  updated_at: string
}

/** Camel-cased, frontend-shaped token pair — see `mapTokenResponse` in `authApi.ts`
 * for the translation from the backend's snake_case `TokenResponseDto`. */
export interface TokenPair {
  accessToken: string
  accessTokenExpiresAt: string
  refreshToken: string
  refreshTokenExpiresAt: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  first_name: string
  last_name: string
}

export interface RegisterResponse {
  id: string
  email: string
}

/** Raw shape returned by POST /auth/login, /auth/refresh (backend
 * `TokenResponse` schema — snake_case, on the wire only). */
export interface TokenResponseDto {
  access_token: string
  token_type: string
  access_token_expires_at: string
  refresh_token: string
  refresh_token_expires_at: string
}
