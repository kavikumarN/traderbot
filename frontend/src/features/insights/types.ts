/** Mirrors the backend's `schemas/pattern_analysis.py` and `schemas/news.py`
 * response models 1:1 (snake_case, Decimals serialized as strings), same
 * convention as `features/portfolio/types.ts`. */

export type PatternSignal = 'BULLISH' | 'BEARISH' | 'NEUTRAL'
export type PatternBucket = 'TREND' | 'REVERSAL' | 'RANGE' | 'BREAKOUT'

export interface Candle {
  symbol: string
  interval: string
  open_time: string
  close_time: string
  open: string
  high: string
  low: string
  close: string
  volume: string
  quote_volume: string
  trade_count: number
  is_closed: boolean
}

export interface PatternMatch {
  name: string
  signal: PatternSignal
  bucket: PatternBucket
  at: string
  confidence: string
  description: string
}

export interface IntervalAnalysis {
  interval: string
  candle_count: number
  patterns: PatternMatch[]
  candles: Candle[]
}

export interface StrategySuggestion {
  strategy_type: string
  parameters: Record<string, unknown>
  bucket: PatternBucket
  confidence: string
  rationale: string
}

export interface PatternAnalysisResponse {
  symbol: string
  intervals: IntervalAnalysis[]
  suggestion: StrategySuggestion | null
}

export interface AnalyzePatternsRequest {
  symbol: string
  intervals: string[]
}

export type NewsImpact = 'LOW' | 'MEDIUM' | 'HIGH'

export interface NewsFeed {
  id: string
  name: string
}

export interface NewsArticle {
  title: string
  url: string
  source_id: string
  source_name: string
  summary: string
  published_at: string
  impact: NewsImpact
  tags: string[]
  symbols: string[]
}
