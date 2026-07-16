import { apiSlice } from '@/api/apiSlice'
import type { Backtest, CreateStrategyRequest, RunBacktestRequest, StrategyResponse } from './types'

export const backtestingApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    // Minimal — just enough to satisfy the `backtests.strategy_id` FK a
    // backtest run needs. Full Strategies management (list/pause/monitor)
    // is a separate, not-yet-built frontend feature.
    createStrategy: builder.mutation<StrategyResponse, CreateStrategyRequest>({
      query: (body) => ({ url: '/api/v1/strategies', method: 'POST', data: body }),
    }),

    runBacktest: builder.mutation<Backtest, { strategyId: string; body: RunBacktestRequest }>({
      query: ({ strategyId, body }) => ({
        url: `/api/v1/strategies/${strategyId}/backtests`,
        method: 'POST',
        data: body,
      }),
    }),
  }),
})

export const { useCreateStrategyMutation, useRunBacktestMutation } = backtestingApi
