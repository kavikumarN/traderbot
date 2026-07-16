import { Box, Paper, Typography, useTheme } from '@mui/material'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { formatPercent } from '@/shared/lib/format'
import type { MonthlyReturn } from '../types'

interface MonthlyReturnsChartProps {
  monthlyReturns: MonthlyReturn[]
}

export function MonthlyReturnsChart({ monthlyReturns }: MonthlyReturnsChartProps) {
  const theme = useTheme()

  if (monthlyReturns.length === 0) {
    return (
      <Paper variant="outlined" sx={{ p: 3 }}>
        <Typography variant="body2" color="textSecondary">
          Not enough trade history yet to show monthly returns.
        </Typography>
      </Paper>
    )
  }

  const data = monthlyReturns.map((entry) => ({ month: entry.month, returnPct: Number(entry.return_pct) * 100 }))

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="subtitle1" sx={{ fontWeight: 600 }} className="mb-2">
        Monthly Returns
      </Typography>
      <Box sx={{ width: '100%', height: 280 }}>
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} vertical={false} />
            <XAxis
              dataKey="month"
              tick={{ fontSize: 12, fill: theme.palette.text.secondary }}
              tickLine={false}
              axisLine={{ stroke: theme.palette.divider }}
            />
            <YAxis
              tick={{ fontSize: 12, fill: theme.palette.text.secondary }}
              tickLine={false}
              axisLine={false}
              width={56}
              tickFormatter={(value: number) => `${value.toFixed(0)}%`}
            />
            <ReferenceLine y={0} stroke={theme.palette.divider} />
            <Tooltip
              formatter={(value: unknown) => formatPercent(Number(value) / 100)}
              contentStyle={{
                background: theme.palette.background.paper,
                border: `1px solid ${theme.palette.divider}`,
                borderRadius: theme.shape.borderRadius,
              }}
            />
            <Bar dataKey="returnPct" radius={[4, 4, 4, 4]} maxBarSize={40}>
              {data.map((entry) => (
                <Cell
                  key={entry.month}
                  fill={entry.returnPct >= 0 ? theme.palette.success.main : theme.palette.error.main}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Box>
    </Paper>
  )
}
