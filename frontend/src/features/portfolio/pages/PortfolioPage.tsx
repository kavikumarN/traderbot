import { useState } from 'react'
import { Alert, Box, Stack, Tab, Tabs, Typography } from '@mui/material'
import { LoadingSpinner } from '@/components/feedback/LoadingSpinner'
import { getApiErrorMessage } from '@/shared/types/api'
import { EquityCurveChart } from '../components/EquityCurveChart'
import { MonthlyReturnsChart } from '../components/MonthlyReturnsChart'
import { PerformanceStats } from '../components/PerformanceStats'
import { PositionsTable } from '../components/PositionsTable'
import { SummaryCards } from '../components/SummaryCards'
import { TradeHistoryTable } from '../components/TradeHistoryTable'
import { WalletTable } from '../components/WalletTable'
import {
  useGetPerformanceQuery,
  useGetPortfolioSummaryQuery,
  useGetPositionsQuery,
  useGetWalletsQuery,
} from '../portfolioApi'

const POLL_INTERVAL_MS = 30_000

const TABS = ['overview', 'positions', 'history', 'performance'] as const
type TabKey = (typeof TABS)[number]

export default function PortfolioPage() {
  const [tab, setTab] = useState<TabKey>('overview')

  const summaryQuery = useGetPortfolioSummaryQuery(undefined, { pollingInterval: POLL_INTERVAL_MS })
  const positionsQuery = useGetPositionsQuery(undefined, { pollingInterval: POLL_INTERVAL_MS })
  const walletsQuery = useGetWalletsQuery()
  const performanceQuery = useGetPerformanceQuery()

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Portfolio
        </Typography>
        <Typography variant="body1" color="textSecondary" className="mt-1">
          Wallet balances, positions, trade history, and performance analytics.
        </Typography>
      </Box>

      <Tabs value={tab} onChange={(_event, value: TabKey) => setTab(value)}>
        <Tab label="Overview" value="overview" />
        <Tab label="Positions" value="positions" />
        <Tab label="Trade History" value="history" />
        <Tab label="Performance" value="performance" />
      </Tabs>

      {tab === 'overview' ? (
        <Stack spacing={3}>
          {summaryQuery.isLoading ? <LoadingSpinner label="Loading portfolio summary…" /> : null}
          {summaryQuery.isError ? <Alert severity="error">{getApiErrorMessage(summaryQuery.error)}</Alert> : null}
          {summaryQuery.data ? <SummaryCards summary={summaryQuery.data} /> : null}

          {walletsQuery.isLoading ? <LoadingSpinner label="Loading wallets…" /> : null}
          {walletsQuery.data ? <WalletTable wallets={walletsQuery.data} /> : null}

          {performanceQuery.data ? <EquityCurveChart points={performanceQuery.data.points} /> : null}
        </Stack>
      ) : null}

      {tab === 'positions' ? (
        <Stack spacing={3}>
          {positionsQuery.isLoading ? <LoadingSpinner label="Loading positions…" /> : null}
          {positionsQuery.isError ? <Alert severity="error">{getApiErrorMessage(positionsQuery.error)}</Alert> : null}
          {positionsQuery.data ? <PositionsTable positions={positionsQuery.data} /> : null}
        </Stack>
      ) : null}

      {tab === 'history' ? <TradeHistoryTable /> : null}

      {tab === 'performance' ? (
        <Stack spacing={3}>
          {performanceQuery.isLoading ? <LoadingSpinner label="Loading performance…" /> : null}
          {performanceQuery.isError ? (
            <Alert severity="error">{getApiErrorMessage(performanceQuery.error)}</Alert>
          ) : null}
          {performanceQuery.data ? (
            <>
              <PerformanceStats performance={performanceQuery.data} />
              <MonthlyReturnsChart monthlyReturns={performanceQuery.data.monthly_returns} />
            </>
          ) : null}
        </Stack>
      ) : null}
    </Stack>
  )
}
