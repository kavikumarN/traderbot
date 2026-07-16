import { apiSlice } from '@/api/apiSlice'
import { getStore } from '@/app/storeRegistry'
import { credentialsUpdated, loggedOut, selectRefreshToken, userLoaded } from './authSlice'
import { mapTokenResponse } from './mappers'
import type {
  AuthUser,
  LoginRequest,
  RegisterRequest,
  RegisterResponse,
  TokenResponseDto,
} from './types'

export const authApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    register: builder.mutation<RegisterResponse, RegisterRequest>({
      query: (body) => ({ url: '/api/v1/auth/register', method: 'POST', data: body }),
    }),

    login: builder.mutation<TokenResponseDto, LoginRequest>({
      query: (body) => ({ url: '/api/v1/auth/login', method: 'POST', data: body }),
      async onQueryStarted(_arg, { dispatch, queryFulfilled }) {
        const { data } = await queryFulfilled
        dispatch(credentialsUpdated(mapTokenResponse(data)))
        // Fire-and-forget: populates `auth.user` for the header/sidebar. If
        // it fails, the response interceptor's 401 handling already covers it.
        dispatch(authApi.endpoints.getMe.initiate(undefined, { forceRefetch: true }))
      },
    }),

    getMe: builder.query<AuthUser, void>({
      query: () => ({ url: '/api/v1/auth/me', method: 'GET' }),
      providesTags: ['CurrentUser'],
      async onQueryStarted(_arg, { dispatch, queryFulfilled }) {
        try {
          const { data } = await queryFulfilled
          dispatch(userLoaded(data))
        } catch {
          // A dead token here is already handled by the Axios response
          // interceptor's refresh/logout pipeline.
        }
      },
    }),

    logout: builder.mutation<void, void>({
      query: () => ({
        url: '/api/v1/auth/logout',
        method: 'POST',
        data: { refresh_token: selectRefreshToken(getStore().getState()) },
      }),
      async onQueryStarted(_arg, { dispatch, queryFulfilled }) {
        try {
          await queryFulfilled
        } finally {
          // Log out locally even if the server call itself failed (e.g. the
          // network dropped) — the user's intent to sign out still applies.
          dispatch(loggedOut())
          dispatch(apiSlice.util.resetApiState())
        }
      },
    }),
  }),
})

export const {
  useRegisterMutation,
  useLoginMutation,
  useGetMeQuery,
  useLazyGetMeQuery,
  useLogoutMutation,
} = authApi
