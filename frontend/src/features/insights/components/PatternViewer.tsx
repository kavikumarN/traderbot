import { useState } from 'react'
import { Alert, Box, Typography } from '@mui/material'
import { useNavigate } from 'react-router-dom'
import { getApiErrorMessage } from '@/shared/types/api'
import { useAnalyzePatternsMutation } from '../insightsApi'
import { terminal, terminalFont } from '../terminal'
import { AnalyzeForm } from './AnalyzeForm'
import { CandlestickChart } from './CandlestickChart'
import { PatternsTable } from './PatternsTable'
import { SuggestionPanel } from './SuggestionPanel'
import { TerminalPanel } from './TerminalPanel'

// Ranks intervals from lowest to highest timeframe — used to pick the
// "primary" (highest-timeframe) chart regardless of the order the user
// happened to click intervals in.
const INTERVAL_RANK: Record<string, number> = { '5m': 0, '15m': 1, '1h': 2, '4h': 3, '1d': 4 }

export function PatternViewer() {
  const navigate = useNavigate()
  const [symbol, setSymbol] = useState('BTCUSDT')
  const [intervals, setIntervals] = useState<string[]>(['15m', '1h', '1d'])
  const [analyze, { data, isLoading, error }] = useAnalyzePatternsMutation()
  const [selectedInterval, setSelectedInterval] = useState<string | undefined>(undefined)

  function handleAnalyze() {
    setSelectedInterval(undefined)
    analyze({ symbol, intervals })
  }

  const primaryInterval = data
    ? [...data.intervals].sort((a, b) => (INTERVAL_RANK[a.interval] ?? 0) - (INTERVAL_RANK[b.interval] ?? 0)).at(-1)
    : undefined

  // Most detected patterns live on the lower-timeframe intervals (far more
  // candles → far more matches), but the chart used to always show the
  // highest-timeframe interval regardless — so most rows in "Detected
  // Patterns" had nothing to point at on the chart. `activeInterval` is
  // switchable (via the tabs below) and defaults to whichever interval the
  // user picked, falling back to `primaryInterval` after a fresh analysis.
  const activeInterval = data?.intervals.find((i) => i.interval === selectedInterval) ?? primaryInterval

  return (
    <Box sx={{ bgcolor: terminal.bg, p: 2, borderRadius: '2px' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <AnalyzeForm
          symbol={symbol}
          onSymbolChange={setSymbol}
          intervals={intervals}
          onIntervalsChange={setIntervals}
          onAnalyze={handleAnalyze}
          isLoading={isLoading}
        />
      </Box>

      {error ? (
        <Alert severity="error" sx={{ mb: 2, fontFamily: terminalFont }}>
          {getApiErrorMessage(error)}
        </Alert>
      ) : null}

      {!data && !isLoading ? (
        <Typography sx={{ fontFamily: terminalFont, fontSize: 12, color: terminal.textDim, py: 6, textAlign: 'center' }}>
          Pick a symbol and intervals, then ANALYZE to detect candlestick/chart patterns.
        </Typography>
      ) : null}

      {data ? (
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '2fr 1fr' }, gap: 2 }}>
          <TerminalPanel
            title={`${data.symbol} — ${activeInterval?.interval ?? ''}`}
            right={
              <Typography sx={{ fontFamily: terminalFont, fontSize: 10, color: terminal.textDim }}>
                {activeInterval?.candle_count ?? 0} CANDLES · {activeInterval?.patterns.length ?? 0} PATTERNS
              </Typography>
            }
          >
            <Box sx={{ display: 'flex', gap: 0.5, mb: 1.5 }}>
              {data.intervals.map((interval) => {
                const selected = interval.interval === activeInterval?.interval
                return (
                  <Box
                    key={interval.interval}
                    onClick={() => setSelectedInterval(interval.interval)}
                    sx={{
                      cursor: 'pointer',
                      px: 1,
                      py: 0.5,
                      fontFamily: terminalFont,
                      fontSize: 11,
                      border: `1px solid ${selected ? terminal.amber : terminal.border}`,
                      color: selected ? terminal.amber : terminal.textDim,
                      userSelect: 'none',
                    }}
                  >
                    {interval.interval} ({interval.patterns.length})
                  </Box>
                )
              })}
            </Box>
            <CandlestickChart
              candles={activeInterval?.candles ?? []}
              patterns={activeInterval?.patterns ?? []}
            />
          </TerminalPanel>

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {data.suggestion ? (
              <TerminalPanel title="AI Suggested Strategy">
                <SuggestionPanel
                  suggestion={data.suggestion}
                  onApply={() =>
                    navigate('/strategies', {
                      state: {
                        aiSuggestion: {
                          symbol: data.symbol,
                          strategyType: data.suggestion?.strategy_type,
                          parameters: data.suggestion?.parameters,
                        },
                      },
                    })
                  }
                />
              </TerminalPanel>
            ) : null}

            <TerminalPanel title="Detected Patterns">
              <PatternsTable
                intervals={data.intervals}
                activeInterval={activeInterval?.interval}
                onSelectInterval={setSelectedInterval}
              />
            </TerminalPanel>
          </Box>
        </Box>
      ) : null}
    </Box>
  )
}
