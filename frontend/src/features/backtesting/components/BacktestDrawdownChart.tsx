import { Box, Paper, Typography, useTheme } from '@mui/material'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { BacktestEquityPoint } from '../types'

interface BacktestDrawdownChartProps {
  points: BacktestEquityPoint[]
}

const percentFormatter = new Intl.NumberFormat('en-US', {
  style: 'percent',
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})

export function BacktestDrawdownChart({ points }: BacktestDrawdownChartProps) {
  const theme = useTheme()

  if (points.length === 0) {
    return (
      <Paper variant="outlined" sx={{ p: 3 }}>
        <Typography variant="body2" color="textSecondary">
          Run a backtest to see its drawdown.
        </Typography>
      </Paper>
    )
  }

  // Peak-to-current drawdown at every equity point, expressed as a negative
  // fraction so the chart reads the conventional way — a flat line at 0
  // means the equity curve is at a fresh high, dips below 0 the deeper
  // underwater it is.
  let peak = Number(points[0].equity)
  const data = points.map((point) => {
    const equity = Number(point.equity)
    peak = Math.max(peak, equity)
    return {
      time: new Date(point.time).toLocaleString(),
      drawdown: peak > 0 ? -(peak - equity) / peak : 0,
    }
  })

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="subtitle1" sx={{ fontWeight: 600 }} className="mb-2">
        Drawdown
      </Typography>
      <Box sx={{ width: '100%', height: 220 }}>
        <ResponsiveContainer>
          <AreaChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="backtestDrawdownFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={theme.palette.error.main} stopOpacity={0.05} />
                <stop offset="100%" stopColor={theme.palette.error.main} stopOpacity={0.35} />
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
              domain={['auto', 0]}
              tick={{ fontSize: 12, fill: theme.palette.text.secondary }}
              tickLine={false}
              axisLine={false}
              width={64}
              tickFormatter={(value: number) => percentFormatter.format(value)}
            />
            <Tooltip
              formatter={(value: unknown) => percentFormatter.format(Number(value))}
              contentStyle={{
                background: theme.palette.background.paper,
                border: `1px solid ${theme.palette.divider}`,
                borderRadius: theme.shape.borderRadius,
              }}
            />
            <Area
              type="monotone"
              dataKey="drawdown"
              stroke={theme.palette.error.main}
              strokeWidth={2}
              fill="url(#backtestDrawdownFill)"
              dot={false}
              activeDot={{ r: 4 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </Box>
    </Paper>
  )
}
