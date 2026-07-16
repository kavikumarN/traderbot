import { useState } from 'react'
import { Box, Stack, Typography } from '@mui/material'
import { BacktestEquityCurveChart } from '../components/BacktestEquityCurveChart'
import { BacktestForm } from '../components/BacktestForm'
import { BacktestSummaryStats } from '../components/BacktestSummaryStats'
import { TradeLogTable } from '../components/TradeLogTable'
import type { Backtest } from '../types'

export default function BacktestingPage() {
  const [result, setResult] = useState<Backtest | null>(null)

  return (
    <Stack spacing={4}>
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Backtesting
        </Typography>
        <Typography variant="body1" color="textSecondary" className="mt-1">
          Replay historical candles through an EMA, RSI, or MACD strategy and see the simulated trade log, PnL,
          equity curve, win rate, drawdown, and Sharpe ratio.
        </Typography>
      </Box>

      <BacktestForm onResult={setResult} />

      {result ? (
        <Stack spacing={3}>
          <BacktestSummaryStats backtest={result} />
          <BacktestEquityCurveChart points={result.equity_curve} />
          <Box>
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }} className="mb-2">
              Trade Log
            </Typography>
            <TradeLogTable fills={result.trade_log} />
          </Box>
        </Stack>
      ) : null}
    </Stack>
  )
}
