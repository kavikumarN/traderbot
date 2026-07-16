import { Box, Card, CardContent, Typography, useTheme } from '@mui/material'
import { formatCurrency, formatPercent, isNonNegative } from '@/shared/lib/format'
import type { PortfolioSummary } from '../types'

interface SummaryCardsProps {
  summary: PortfolioSummary
}

export function SummaryCards({ summary }: SummaryCardsProps) {
  const theme = useTheme()
  const totalFees = Object.values(summary.fees_by_asset).reduce((sum, value) => sum + Number(value), 0)
  const pnlColor = isNonNegative(summary.total_pnl) ? theme.palette.success.main : theme.palette.error.main
  const roiColor =
    summary.roi_pct === null || isNonNegative(summary.roi_pct) ? theme.palette.success.main : theme.palette.error.main

  const metrics: { label: string; value: string; color?: string }[] = [
    { label: 'Equity', value: formatCurrency(summary.equity) },
    { label: 'Total P&L', value: formatCurrency(summary.total_pnl), color: pnlColor },
    { label: 'ROI', value: formatPercent(summary.roi_pct), color: roiColor },
    { label: 'Cash', value: formatCurrency(summary.cash) },
    { label: 'Positions Value', value: formatCurrency(summary.positions_value) },
    { label: 'Realized P&L', value: formatCurrency(summary.realized_pnl) },
    { label: 'Unrealized P&L', value: formatCurrency(summary.unrealized_pnl) },
    { label: 'Fees Paid', value: formatCurrency(totalFees) },
  ]

  return (
    <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
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
