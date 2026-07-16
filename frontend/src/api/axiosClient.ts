import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { getStore } from '@/app/storeRegistry'
import {
  credentialsUpdated,
  loggedOut,
  selectAccessToken,
  selectRefreshToken,
} from '@/features/auth/authSlice'
import { mapTokenResponse } from '@/features/auth/mappers'
import type { TokenResponseDto } from '@/features/auth/types'
import { notifyError } from '@/notifications/notificationsSlice'
import { env } from '@/shared/lib/env'
import type { ApiError, ProblemDetail } from '@/shared/types/api'

/** Requests to these endpoints never carry a bearer token and never trigger
 * the refresh-on-401 pipeline (a 401 from /login *is* the answer). */
const AUTH_FREE_PATHS = ['/api/v1/auth/login', '/api/v1/auth/register', '/api/v1/auth/refresh']

interface RetryableRequestConfig extends InternalAxiosRequestConfig {
  _retry?: boolean
}

export const axiosClient = axios.create({
  baseURL: env.apiBaseUrl,
  timeout: 15_000,
})

function toApiError(error: AxiosError<ProblemDetail>): ApiError {
  if (!error.response) {
    return {
      status: error.code === 'ECONNABORTED' ? 'TIMEOUT' : 'NETWORK_ERROR',
      type: 'NetworkError',
      message: 'Network error — check your connection and try again.',
      traceId: null,
    }
  }
  const problem = error.response.data
  return {
    status: error.response.status,
    type: problem?.type ?? 'UnknownError',
    message: problem?.detail ?? error.message ?? 'Something went wrong.',
    traceId: problem?.trace_id ?? null,
  }
}

axiosClient.interceptors.request.use((config) => {
  const isAuthFree = AUTH_FREE_PATHS.some((path) => config.url?.includes(path))
  if (!isAuthFree) {
    const token = selectAccessToken(getStore().getState())
    if (token) {
      config.headers.set('Authorization', `Bearer ${token}`)
    }
  }
  return config
})

// --- 401 handling: a single in-flight refresh, everyone else queues -------

let isRefreshing = false
let pendingQueue: Array<{ resolve: (token: string) => void; reject: (error: unknown) => void }> = []

function flushQueue(error: unknown, token: string | null): void {
  for (const { resolve, reject } of pendingQueue) {
    if (error || !token) reject(error)
    else resolve(token)
  }
  pendingQueue = []
}

async function handleUnauthorized(
  originalRequest: RetryableRequestConfig,
  fallbackError: ApiError,
): Promise<unknown> {
  const refreshToken = selectRefreshToken(getStore().getState())
  if (!refreshToken) {
    getStore().dispatch(loggedOut())
    return Promise.reject(fallbackError)
  }

  if (isRefreshing) {
    const token = await new Promise<string>((resolve, reject) => {
      pendingQueue.push({ resolve, reject })
    })
    originalRequest._retry = true
    originalRequest.headers.set('Authorization', `Bearer ${token}`)
    return axiosClient(originalRequest)
  }

  originalRequest._retry = true
  isRefreshing = true
  try {
    const { data } = await axios.post<TokenResponseDto>(`${env.apiBaseUrl}/api/v1/auth/refresh`, {
      refresh_token: refreshToken,
    })
    const tokens = mapTokenResponse(data)
    getStore().dispatch(credentialsUpdated(tokens))
    flushQueue(null, tokens.accessToken)
    originalRequest.headers.set('Authorization', `Bearer ${tokens.accessToken}`)
    return axiosClient(originalRequest)
  } catch (refreshError) {
    flushQueue(refreshError, null)
    getStore().dispatch(loggedOut())
    getStore().dispatch(notifyError('Your session has expired. Please sign in again.'))
    return Promise.reject(fallbackError)
  } finally {
    isRefreshing = false
  }
}

axiosClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ProblemDetail>) => {
    const apiError = toApiError(error)
    const originalRequest = error.config as RetryableRequestConfig | undefined
    const isAuthFreeUrl = AUTH_FREE_PATHS.some((path) => originalRequest?.url?.includes(path))

    if (apiError.status === 401 && originalRequest && !originalRequest._retry && !isAuthFreeUrl) {
      return handleUnauthorized(originalRequest, apiError)
    }

    const isServerOrNetworkError =
      apiError.status === 'NETWORK_ERROR' ||
      apiError.status === 'TIMEOUT' ||
      (typeof apiError.status === 'number' && apiError.status >= 500)
    if (isServerOrNetworkError) {
      getStore().dispatch(notifyError(apiError.message))
    }

    return Promise.reject(apiError)
  },
)
