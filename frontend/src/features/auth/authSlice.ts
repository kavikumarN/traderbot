import { createSlice, type PayloadAction } from '@reduxjs/toolkit'
import type { RootState } from '@/app/store'
import { clearStoredTokens, loadStoredTokens, saveStoredTokens } from './authStorage'
import type { AuthUser, TokenPair } from './types'

interface AuthState {
  accessToken: string | null
  accessTokenExpiresAt: string | null
  refreshToken: string | null
  refreshTokenExpiresAt: string | null
  user: AuthUser | null
  status: 'unauthenticated' | 'authenticated'
}

const storedTokens = loadStoredTokens()

const initialState: AuthState = {
  accessToken: storedTokens?.accessToken ?? null,
  accessTokenExpiresAt: storedTokens?.accessTokenExpiresAt ?? null,
  refreshToken: storedTokens?.refreshToken ?? null,
  refreshTokenExpiresAt: storedTokens?.refreshTokenExpiresAt ?? null,
  // A stored token pair means "was authenticated last session" — the user
  // profile is (re)fetched by <AuthBootstrap> on app start. If the refresh
  // token turns out to be dead, the Axios 401 pipeline logs us back out.
  user: null,
  status: storedTokens ? 'authenticated' : 'unauthenticated',
}

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    credentialsUpdated(state, action: PayloadAction<TokenPair>) {
      state.accessToken = action.payload.accessToken
      state.accessTokenExpiresAt = action.payload.accessTokenExpiresAt
      state.refreshToken = action.payload.refreshToken
      state.refreshTokenExpiresAt = action.payload.refreshTokenExpiresAt
      state.status = 'authenticated'
      saveStoredTokens(action.payload)
    },
    userLoaded(state, action: PayloadAction<AuthUser>) {
      state.user = action.payload
    },
    loggedOut(state) {
      state.accessToken = null
      state.accessTokenExpiresAt = null
      state.refreshToken = null
      state.refreshTokenExpiresAt = null
      state.user = null
      state.status = 'unauthenticated'
      clearStoredTokens()
    },
  },
})

export const { credentialsUpdated, userLoaded, loggedOut } = authSlice.actions
export default authSlice.reducer

export const selectAccessToken = (state: RootState) => state.auth.accessToken
export const selectRefreshToken = (state: RootState) => state.auth.refreshToken
export const selectAuthUser = (state: RootState) => state.auth.user
export const selectAuthStatus = (state: RootState) => state.auth.status
export const selectIsAuthenticated = (state: RootState) => state.auth.status === 'authenticated'
