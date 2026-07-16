import {
  Button,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import { formatQuantity } from '@/shared/lib/format'
import { useCancelOrderMutation, useSyncOrderMutation } from '../ordersApi'
import type { Order } from '../types'
import { OrderStatusChip } from './OrderStatusChip'

const OPEN_STATUSES = new Set(['PENDING_RISK', 'PENDING_SUBMIT', 'SUBMITTED', 'PARTIALLY_FILLED'])

interface OrdersTableProps {
  orders: Order[]
  showActions?: boolean
  emptyLabel?: string
}

export function OrdersTable({ orders, showActions = false, emptyLabel = 'No orders yet.' }: OrdersTableProps) {
  const [cancelOrder, { isLoading: isCancelling }] = useCancelOrderMutation()
  const [syncOrder, { isLoading: isSyncing }] = useSyncOrderMutation()

  if (orders.length === 0) {
    return (
      <Paper variant="outlined" className="p-6">
        <Typography variant="body2" color="textSecondary">
          {emptyLabel}
        </Typography>
      </Paper>
    )
  }

  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Created</TableCell>
            <TableCell>Symbol</TableCell>
            <TableCell>Side</TableCell>
            <TableCell>Type</TableCell>
            <TableCell align="right">Quantity</TableCell>
            <TableCell align="right">Filled</TableCell>
            <TableCell align="right">Price</TableCell>
            <TableCell>Status</TableCell>
            {showActions ? <TableCell align="right">Actions</TableCell> : null}
          </TableRow>
        </TableHead>
        <TableBody>
          {orders.map((order) => (
            <TableRow key={order.id}>
              <TableCell>{new Date(order.created_at).toLocaleString()}</TableCell>
              <TableCell>{order.symbol}</TableCell>
              <TableCell>{order.side}</TableCell>
              <TableCell>{order.type}</TableCell>
              <TableCell align="right">{formatQuantity(order.quantity)}</TableCell>
              <TableCell align="right">{formatQuantity(order.executed_quantity)}</TableCell>
              <TableCell align="right">{order.price ? formatQuantity(order.price) : '—'}</TableCell>
              <TableCell>
                <OrderStatusChip status={order.status} />
              </TableCell>
              {showActions ? (
                <TableCell align="right">
                  <Stack direction="row" spacing={1} sx={{ justifyContent: 'flex-end' }}>
                    <Button size="small" variant="outlined" disabled={isSyncing} onClick={() => syncOrder(order.id)}>
                      Sync
                    </Button>
                    {OPEN_STATUSES.has(order.status) ? (
                      <Button
                        size="small"
                        color="error"
                        variant="outlined"
                        disabled={isCancelling}
                        onClick={() => cancelOrder(order.id)}
                      >
                        Cancel
                      </Button>
                    ) : null}
                  </Stack>
                </TableCell>
              ) : null}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  )
}
