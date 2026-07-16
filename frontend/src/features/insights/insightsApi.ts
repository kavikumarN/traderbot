import { apiSlice } from '@/api/apiSlice'
import type { AnalyzePatternsRequest, NewsArticle, NewsFeed, PatternAnalysisResponse } from './types'

export const insightsApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    analyzePatterns: builder.mutation<PatternAnalysisResponse, AnalyzePatternsRequest>({
      query: (body) => ({ url: '/api/v1/strategies/ai-builder/analyze', method: 'POST', data: body }),
    }),

    listNewsFeeds: builder.query<NewsFeed[], void>({
      query: () => ({ url: '/api/v1/insights/news/feeds', method: 'GET' }),
    }),

    listNews: builder.query<NewsArticle[], { feed?: string; limit?: number }>({
      query: ({ feed, limit = 40 }) => ({
        url: '/api/v1/insights/news',
        method: 'GET',
        params: { feed, limit },
      }),
    }),
  }),
})

export const { useAnalyzePatternsMutation, useListNewsFeedsQuery, useListNewsQuery } = insightsApi
