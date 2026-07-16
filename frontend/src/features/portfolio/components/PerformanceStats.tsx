import { Box, Card, CardContent, Typography, useTheme } from '@mui/material'
import { formatCurrency, formatPercent, formatSharpe } from '@/shared/lib/format'
import type { Performance } from '../types'

interface PerformanceStatsProps {
  performance: Performance
}

export function PerformanceStats({ performance }: PerformanceStatsProps) {
  const theme = useTheme()

  const metrics = [
    { label: 'Sharpe Ratio', value: formatSharpe(performance.sharpe_ratio) },
    {
      label: 'Max Drawdown',
      value: formatPercent(performance.max_drawdown_pct),
      color: theme.palette.error.main,
    },
    {
      label: 'Current Drawdown',
      value: formatPercent(performance.current_drawdown_pct),
      color: theme.palette.error.main,
    },
    { label: 'Starting Equity', value: formatCurrency(performance.starting_equity) },
    { label: 'Current Equity', value: formatCurrency(performance.current_equity) },
  ]

  return (
    <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
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
