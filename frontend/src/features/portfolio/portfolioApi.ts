import { apiSlice } from '@/api/apiSlice'
import type { Performance, PortfolioSummary, Position, TradeHistory, Wallet } from './types'

export const portfolioApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    getPortfolioSummary: builder.query<PortfolioSummary, void>({
      query: () => ({ url: '/api/v1/portfolio/summary', method: 'GET' }),
    }),

    getWallets: builder.query<Wallet[], void>({
      query: () => ({ url: '/api/v1/portfolio/wallets', method: 'GET' }),
    }),

    getPositions: builder.query<Position[], void>({
      query: () => ({ url: '/api/v1/portfolio/positions', method: 'GET' }),
    }),

    getTradeHistory: builder.query<TradeHistory, { offset: number; limit: number }>({
      query: ({ offset, limit }) => ({
        url: '/api/v1/portfolio/trades',
        method: 'GET',
        params: { offset, limit },
      }),
    }),

    getPerformance: builder.query<Performance, void>({
      query: () => ({ url: '/api/v1/portfolio/performance', method: 'GET' }),
    }),
  }),
})

export const {
  useGetPortfolioSummaryQuery,
  useGetWalletsQuery,
  useGetPositionsQuery,
  useGetTradeHistoryQuery,
  useGetPerformanceQuery,
} = portfolioApi
