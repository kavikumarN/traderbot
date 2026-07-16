import { createApi } from '@reduxjs/toolkit/query/react'
import { axiosBaseQuery } from './baseQuery'

/**
 * Single root RTK Query API. Features inject their own endpoints via
 * `apiSlice.injectEndpoints(...)` (see `features/auth/authApi.ts`) instead
 * of each defining their own `createApi` — one cache, one middleware, one
 * set of tag types to reason about.
 */
export const apiSlice = createApi({
  reducerPath: 'api',
  baseQuery: axiosBaseQuery(),
  tagTypes: ['CurrentUser'],
  endpoints: () => ({}),
})
