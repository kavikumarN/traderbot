import { apiSlice } from '@/api/apiSlice'
import type { Backtest, RunBacktestRequest } from './types'

export const backtestingApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    runBacktest: builder.mutation<Backtest, { strategyId: string; body: RunBacktestRequest }>({
      query: ({ strategyId, body }) => ({
        url: `/api/v1/strategies/${strategyId}/backtests`,
        method: 'POST',
        data: body,
      }),
    }),
  }),
})

export const { useRunBacktestMutation } = backtestingApi
