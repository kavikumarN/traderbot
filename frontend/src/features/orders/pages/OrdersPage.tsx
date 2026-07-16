import { useState } from 'react'
import { Alert, Box, Stack, Tab, Tabs, Typography } from '@mui/material'
import { LoadingSpinner } from '@/components/feedback/LoadingSpinner'
import { getApiErrorMessage } from '@/shared/types/api'
import { OrdersTable } from '../components/OrdersTable'
import { PlaceOrderForm } from '../components/PlaceOrderForm'
import { useListOpenOrdersQuery, useListOrderHistoryQuery } from '../ordersApi'

const POLL_INTERVAL_MS = 15_000
const TABS = ['place', 'open', 'history'] as const
type TabKey = (typeof TABS)[number]

export default function OrdersPage() {
  const [tab, setTab] = useState<TabKey>('open')

  const openOrdersQuery = useListOpenOrdersQuery(undefined, { pollingInterval: POLL_INTERVAL_MS })
  const historyQuery = useListOrderHistoryQuery({ offset: 0, limit: 50 })

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Orders
        </Typography>
        <Typography variant="body1" color="textSecondary" className="mt-1">
          Place orders and track their status through the exchange.
        </Typography>
      </Box>

      <Tabs value={tab} onChange={(_event, value: TabKey) => setTab(value)}>
        <Tab label="Place Order" value="place" />
        <Tab label="Open Orders" value="open" />
        <Tab label="History" value="history" />
      </Tabs>

      {tab === 'place' ? <PlaceOrderForm /> : null}

      {tab === 'open' ? (
        <Stack spacing={3}>
          {openOrdersQuery.isLoading ? <LoadingSpinner label="Loading open orders…" /> : null}
          {openOrdersQuery.isError ? (
            <Alert severity="error">{getApiErrorMessage(openOrdersQuery.error)}</Alert>
          ) : null}
          {openOrdersQuery.data ? (
            <OrdersTable orders={openOrdersQuery.data} showActions emptyLabel="No open orders." />
          ) : null}
        </Stack>
      ) : null}

      {tab === 'history' ? (
        <Stack spacing={3}>
          {historyQuery.isLoading ? <LoadingSpinner label="Loading order history…" /> : null}
          {historyQuery.isError ? <Alert severity="error">{getApiErrorMessage(historyQuery.error)}</Alert> : null}
          {historyQuery.data ? (
            <OrdersTable orders={historyQuery.data.items} emptyLabel="No orders placed yet." />
          ) : null}
        </Stack>
      ) : null}
    </Stack>
  )
}
