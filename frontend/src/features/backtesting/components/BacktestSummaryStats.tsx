import { Box, Card, CardContent, Typography, useTheme } from '@mui/material'
import { formatCurrency, formatPercent, formatRatio, formatSharpe, isNonNegative } from '@/shared/lib/format'
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
  const m = backtest.metrics

  const headline: { label: string; value: string; color?: string }[] = [
    { label: 'Final Balance', value: backtest.final_balance ? formatCurrency(backtest.final_balance) : '—' },
    { label: 'Total Return', value: formatPercent(backtest.total_return_pct), color: returnColor },
    { label: 'CAGR', value: formatPercent(m.cagr_pct) },
    { label: 'Sharpe Ratio', value: formatSharpe(backtest.sharpe_ratio) },
    { label: 'Sortino Ratio', value: formatRatio(m.sortino_ratio) },
    { label: 'Calmar Ratio', value: formatRatio(m.calmar_ratio) },
    {
      label: 'Max Drawdown',
      value: formatPercent(backtest.max_drawdown_pct),
      color: theme.palette.error.main,
    },
    { label: 'Avg Drawdown', value: formatPercent(m.avg_drawdown_pct) },
    { label: 'Exposure', value: formatPercent(m.exposure_pct) },
  ]

  const tradeStats: { label: string; value: string; color?: string }[] = [
    { label: 'Win Rate', value: formatPercent(backtest.win_rate) },
    { label: 'Total Trades', value: String(backtest.total_trades ?? 0) },
    { label: 'Profit Factor', value: formatRatio(m.profit_factor) },
    { label: 'Expectancy', value: formatCurrency(m.expectancy) },
    { label: 'Avg Win', value: formatCurrency(m.avg_win), color: theme.palette.success.main },
    { label: 'Avg Loss', value: formatCurrency(m.avg_loss), color: theme.palette.error.main },
    { label: 'Largest Win', value: formatCurrency(m.largest_win), color: theme.palette.success.main },
    { label: 'Largest Loss', value: formatCurrency(m.largest_loss), color: theme.palette.error.main },
    { label: 'Max Consecutive Wins', value: String(m.max_consecutive_wins) },
    { label: 'Max Consecutive Losses', value: String(m.max_consecutive_losses) },
  ]

  return (
    <Box className="flex flex-col gap-4">
      <MetricGrid metrics={headline} />
      <MetricGrid metrics={tradeStats} />
    </Box>
  )
}

function MetricGrid({ metrics }: { metrics: { label: string; value: string; color?: string }[] }) {
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
