import { Box, Paper, Typography, useTheme } from '@mui/material'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { formatCurrency } from '@/shared/lib/format'
import type { BacktestEquityPoint } from '../types'

interface BacktestEquityCurveChartProps {
  points: BacktestEquityPoint[]
}

export function BacktestEquityCurveChart({ points }: BacktestEquityCurveChartProps) {
  const theme = useTheme()

  if (points.length === 0) {
    return (
      <Paper variant="outlined" sx={{ p: 3 }}>
        <Typography variant="body2" color="textSecondary">
          Run a backtest to see its equity curve.
        </Typography>
      </Paper>
    )
  }

  const data = points.map((point) => ({
    time: new Date(point.time).toLocaleString(),
    equity: Number(point.equity),
  }))

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="subtitle1" sx={{ fontWeight: 600 }} className="mb-2">
        Equity Curve
      </Typography>
      <Box sx={{ width: '100%', height: 320 }}>
        <ResponsiveContainer>
          <AreaChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="backtestEquityFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={theme.palette.primary.main} stopOpacity={0.28} />
                <stop offset="100%" stopColor={theme.palette.primary.main} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} vertical={false} />
            <XAxis
              dataKey="time"
              tick={{ fontSize: 12, fill: theme.palette.text.secondary }}
              tickLine={false}
              axisLine={{ stroke: theme.palette.divider }}
              minTickGap={48}
            />
            <YAxis
              tick={{ fontSize: 12, fill: theme.palette.text.secondary }}
              tickLine={false}
              axisLine={false}
              width={72}
              tickFormatter={(value: number) => formatCurrency(value)}
            />
            <Tooltip
              formatter={(value: unknown) => formatCurrency(Number(value))}
              contentStyle={{
                background: theme.palette.background.paper,
                border: `1px solid ${theme.palette.divider}`,
                borderRadius: theme.shape.borderRadius,
              }}
            />
            <Area
              type="monotone"
              dataKey="equity"
              stroke={theme.palette.primary.main}
              strokeWidth={2}
              fill="url(#backtestEquityFill)"
              dot={false}
              activeDot={{ r: 4 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </Box>
    </Paper>
  )
}
