import type { BaseQueryFn } from '@reduxjs/toolkit/query'
import type { AxiosRequestConfig } from 'axios'
import { axiosClient } from './axiosClient'
import type { ApiError } from '@/shared/types/api'

export interface AxiosBaseQueryArgs {
  url: string
  method: AxiosRequestConfig['method']
  data?: AxiosRequestConfig['data']
  params?: AxiosRequestConfig['params']
  headers?: AxiosRequestConfig['headers']
}

/**
 * Adapts our Axios instance (and its interceptor-driven auth-refresh /
 * global-error pipeline) to RTK Query's `BaseQueryFn` contract, so every
 * `createApi` endpoint gets that behavior for free instead of each feature
 * reimplementing it with `fetchBaseQuery`.
 */
export const axiosBaseQuery =
  (): BaseQueryFn<AxiosBaseQueryArgs, unknown, ApiError> =>
  async ({ url, method, data, params, headers }) => {
    try {
      const response = await axiosClient({ url, method, data, params, headers })
      return { data: response.data }
    } catch (error) {
      // axiosClient's response interceptor already normalizes every
      // rejection to an ApiError before it gets here.
      return { error: error as ApiError }
    }
  }
