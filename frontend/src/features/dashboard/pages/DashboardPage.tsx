import { Box, Card, CardContent, Stack, Typography } from '@mui/material'
import { useAuth } from '@/shared/hooks/useAuth'
import { useGetPerformanceQuery, useGetPortfolioSummaryQuery } from '@/features/portfolio/portfolioApi'
import { useListOpenOrdersQuery } from '@/features/orders/ordersApi'
import { useGetRiskStateQuery } from '@/features/risk/riskApi'
import { useListStrategiesQuery } from '@/features/strategies/strategiesApi'
import { TRADEABLE_STATUSES } from '@/features/strategies/types'
import { formatCurrency } from '@/shared/lib/format'

const POLL_INTERVAL_MS = 30_000

export default function DashboardPage() {
  const { user } = useAuth()

  const summaryQuery = useGetPortfolioSummaryQuery(undefined, { pollingInterval: POLL_INTERVAL_MS })
  const performanceQuery = useGetPerformanceQuery(undefined, { pollingInterval: POLL_INTERVAL_MS })
  const strategiesQuery = useListStrategiesQuery(undefined, { pollingInterval: POLL_INTERVAL_MS })
  const openOrdersQuery = useListOpenOrdersQuery(undefined, { pollingInterval: POLL_INTERVAL_MS })
  const riskStateQuery = useGetRiskStateQuery(undefined, { pollingInterval: POLL_INTERVAL_MS })

  const activeStrategyCount = strategiesQuery.data?.filter((s) => TRADEABLE_STATUSES.includes(s.status)).length

  const points = performanceQuery.data?.points ?? []
  const todaysPnl =
    points.length >= 2 ? Number(points[points.length - 1].equity) - Number(points[points.length - 2].equity) : null

  const metrics = [
    {
      label: 'Open positions',
      value: summaryQuery.data ? String(summaryQuery.data.open_position_count) : null,
      loading: summaryQuery.isLoading,
    },
    {
      label: 'Active strategies',
      value: activeStrategyCount !== undefined ? String(activeStrategyCount) : null,
      loading: strategiesQuery.isLoading,
    },
    {
      label: "Today's P&L",
      value: todaysPnl !== null ? formatCurrency(todaysPnl) : points.length === 1 ? formatCurrency(0) : null,
      loading: performanceQuery.isLoading,
      color: todaysPnl !== null && todaysPnl < 0 ? 'error.main' : todaysPnl !== null && todaysPnl > 0 ? 'success.main' : undefined,
    },
    {
      label: 'Open orders',
      value: openOrdersQuery.data ? String(openOrdersQuery.data.length) : null,
      loading: openOrdersQuery.isLoading,
    },
    {
      label: 'Risk status',
      value: riskStateQuery.data ? (riskStateQuery.data.is_trading_allowed ? 'Allowed' : 'Halted') : null,
      loading: riskStateQuery.isLoading,
      color: riskStateQuery.data && !riskStateQuery.data.is_trading_allowed ? 'error.main' : undefined,
    },
  ]

  return (
    <Stack spacing={4}>
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Welcome{user ? `, ${user.first_name}` : ''}
        </Typography>
        <Typography variant="body1" color="textSecondary" className="mt-1">
          A live snapshot of your portfolio, strategies, orders, and risk posture.
        </Typography>
      </Box>

      <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {metrics.map((metric) => (
          <Card key={metric.label} variant="outlined">
            <CardContent>
              <Typography variant="overline" color="textSecondary">
                {metric.label}
              </Typography>
              <Typography variant="h4" sx={{ fontWeight: 700, color: metric.color }} className="mt-1">
                {metric.value ?? (metric.loading ? '…' : '—')}
              </Typography>
            </CardContent>
          </Card>
        ))}
      </Box>

      {user ? (
        <Card variant="outlined">
          <CardContent>
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }} className="mb-2">
              Account
            </Typography>
            <Stack spacing={1}>
              <AccountRow label="Email" value={user.email} />
              <AccountRow label="Roles" value={user.role_names.join(', ') || '—'} />
              <AccountRow label="Status" value={user.is_active ? 'Active' : 'Inactive'} />
            </Stack>
          </CardContent>
        </Card>
      ) : null}
    </Stack>
  )
}

function AccountRow({ label, value }: { label: string; value: string }) {
  return (
    <Box className="flex items-center justify-between border-b border-gray-100 py-2 last:border-0 dark:border-white/10">
      <Typography variant="body2" color="textSecondary">
        {label}
      </Typography>
      <Typography variant="body2" sx={{ fontWeight: 600 }}>
        {value}
      </Typography>
    </Box>
  )
}
