import type { ReactNode } from 'react'
import { Box, Paper, Typography, useTheme } from '@mui/material'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { formatCurrency } from '@/shared/lib/format'
import type { BacktestFill } from '../types'

interface BacktestPnlHistogramProps {
  fills: BacktestFill[]
}

const BIN_COUNT = 12

export function BacktestPnlHistogram({ fills }: BacktestPnlHistogramProps) {
  const theme = useTheme()

  const pnls = fills.map((fill) => Number(fill.realized_pnl)).filter((pnl) => pnl !== 0)

  if (pnls.length === 0) {
    return (
      <Paper variant="outlined" sx={{ p: 3 }}>
        <Typography variant="body2" color="textSecondary">
          No closed trades to show a P&amp;L distribution for yet.
        </Typography>
      </Paper>
    )
  }

  const min = Math.min(...pnls)
  const max = Math.max(...pnls)
  // A single realized value (or a run of identical ones) has no spread to
  // bin — show it as one bar instead of dividing by a zero-width range.
  const binWidth = max > min ? (max - min) / BIN_COUNT : Math.max(Math.abs(max) || 1, 1)
  const binCount = max > min ? BIN_COUNT : 1

  const bins = Array.from({ length: binCount }, (_, i) => {
    const rangeStart = min + i * binWidth
    const rangeEnd = i === binCount - 1 ? max : rangeStart + binWidth
    return { rangeStart, rangeEnd, count: 0 }
  })

  for (const pnl of pnls) {
    const index = binWidth > 0 ? Math.min(binCount - 1, Math.floor((pnl - min) / binWidth)) : 0
    bins[index].count += 1
  }

  const data = bins.map((bin) => ({
    label: `${formatCurrency(bin.rangeStart)} to ${formatCurrency(bin.rangeEnd)}`,
    midpoint: (bin.rangeStart + bin.rangeEnd) / 2,
    count: bin.count,
  }))

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="subtitle1" sx={{ fontWeight: 600 }} className="mb-2">
        Trade P&amp;L Distribution
      </Typography>
      <Box sx={{ width: '100%', height: 220 }}>
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} vertical={false} />
            <XAxis dataKey="label" tick={false} axisLine={{ stroke: theme.palette.divider }} />
            <YAxis
              allowDecimals={false}
              tick={{ fontSize: 12, fill: theme.palette.text.secondary }}
              tickLine={false}
              axisLine={false}
              width={32}
            />
            <Tooltip
              labelFormatter={(label: ReactNode) => label}
              formatter={(value: unknown) => [`${value} trade${value === 1 ? '' : 's'}`, 'Trades']}
              contentStyle={{
                background: theme.palette.background.paper,
                border: `1px solid ${theme.palette.divider}`,
                borderRadius: theme.shape.borderRadius,
              }}
            />
            <Bar dataKey="count" radius={[2, 2, 0, 0]}>
              {data.map((bin) => (
                <Cell
                  key={bin.label}
                  fill={bin.midpoint >= 0 ? theme.palette.success.main : theme.palette.error.main}
                  fillOpacity={0.75}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Box>
    </Paper>
  )
}
