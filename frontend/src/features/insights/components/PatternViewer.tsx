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

export function PatternViewer() {
  const navigate = useNavigate()
  const [symbol, setSymbol] = useState('BTCUSDT')
  const [intervals, setIntervals] = useState<string[]>(['15m', '1h', '1d'])
  const [analyze, { data, isLoading, error }] = useAnalyzePatternsMutation()

  function handleAnalyze() {
    analyze({ symbol, intervals })
  }

  const primaryInterval = data?.intervals[data.intervals.length - 1]

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
            title={`${data.symbol} — ${primaryInterval?.interval ?? ''}`}
            right={
              <Typography sx={{ fontFamily: terminalFont, fontSize: 10, color: terminal.textDim }}>
                {primaryInterval?.candle_count ?? 0} CANDLES
              </Typography>
            }
          >
            <CandlestickChart
              candles={primaryInterval?.candles ?? []}
              patterns={primaryInterval?.patterns ?? []}
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
              <PatternsTable intervals={data.intervals} />
            </TerminalPanel>
          </Box>
        </Box>
      ) : null}
    </Box>
  )
}
