import { apiSlice } from '@/api/apiSlice'
import type {
  CreateStrategyRequest,
  Signal,
  Strategy,
  StrategyType,
  UpdateStrategyStatusRequest,
} from './types'

export const strategiesApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    listStrategies: builder.query<Strategy[], void>({
      query: () => ({ url: '/api/v1/strategies', method: 'GET' }),
      providesTags: (result) =>
        result
          ? [...result.map((s) => ({ type: 'Strategy' as const, id: s.id })), { type: 'Strategy' as const, id: 'LIST' }]
          : [{ type: 'Strategy' as const, id: 'LIST' }],
    }),

    listStrategyTypes: builder.query<StrategyType[], void>({
      query: () => ({ url: '/api/v1/strategies/types', method: 'GET' }),
    }),

    getStrategy: builder.query<Strategy, string>({
      query: (strategyId) => ({ url: `/api/v1/strategies/${strategyId}`, method: 'GET' }),
      providesTags: (_result, _error, strategyId) => [{ type: 'Strategy', id: strategyId }],
    }),

    createStrategy: builder.mutation<Strategy, CreateStrategyRequest>({
      query: (body) => ({ url: '/api/v1/strategies', method: 'POST', data: body }),
      invalidatesTags: [{ type: 'Strategy', id: 'LIST' }],
    }),

    updateStrategyStatus: builder.mutation<Strategy, { strategyId: string; body: UpdateStrategyStatusRequest }>({
      query: ({ strategyId, body }) => ({
        url: `/api/v1/strategies/${strategyId}/status`,
        method: 'POST',
        data: body,
      }),
      invalidatesTags: (_result, _error, { strategyId }) => [
        { type: 'Strategy', id: strategyId },
        { type: 'Strategy', id: 'LIST' },
      ],
    }),

    listSignals: builder.query<Signal[], { strategyId: string; offset?: number; limit?: number }>({
      query: ({ strategyId, offset = 0, limit = 100 }) => ({
        url: `/api/v1/strategies/${strategyId}/signals`,
        method: 'GET',
        params: { offset, limit },
      }),
    }),
  }),
})

export const {
  useListStrategiesQuery,
  useListStrategyTypesQuery,
  useGetStrategyQuery,
  useCreateStrategyMutation,
  useUpdateStrategyStatusMutation,
  useListSignalsQuery,
} = strategiesApi
