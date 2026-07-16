import { Box, Card, CardContent, Typography, useTheme } from '@mui/material'
import { formatCurrency, formatPercent, formatSharpe, isNonNegative } from '@/shared/lib/format'
import type { Backtest } from '../types'

interface BacktestSummaryStatsProps {
  backtest: Backtest
}

export function BacktestSummaryStats({ backtest }: BacktestSummaryStatsProps) {
  const theme = useTheme()
  const returnColor =
    backtest.total_return_pct === null || isNonNegative(backtest.total_return_pct)
      ? theme.palette.success.main
      : theme.palette.error.main

  const metrics: { label: string; value: string; color?: string }[] = [
    { label: 'Final Balance', value: backtest.final_balance ? formatCurrency(backtest.final_balance) : '—' },
    { label: 'Total Return', value: formatPercent(backtest.total_return_pct), color: returnColor },
    { label: 'Sharpe Ratio', value: formatSharpe(backtest.sharpe_ratio) },
    {
      label: 'Max Drawdown',
      value: formatPercent(backtest.max_drawdown_pct),
      color: theme.palette.error.main,
    },
    { label: 'Win Rate', value: formatPercent(backtest.win_rate) },
    { label: 'Total Trades', value: String(backtest.total_trades ?? 0) },
  ]

  return (
    <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {metrics.map((metric) => (
        <Card key={metric.label} variant="outlined">
          <CardContent>
            <Typography variant="overline" color="textSecondary">
              {metric.label}
            </Typography>
            <Typography variant="h5" sx={{ fontWeight: 700, color: metric.color }} className="mt-1">
              {metric.value}
            </Typography>
          </CardContent>
        </Card>
      ))}
    </Box>
  )
}
