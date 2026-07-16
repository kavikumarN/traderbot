import { useState } from 'react'
import {
  Chip,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  Typography,
} from '@mui/material'
import { useGetTradeHistoryQuery } from '../portfolioApi'
import { formatCurrency, formatQuantity } from '@/shared/lib/format'

const PAGE_SIZE_OPTIONS = [10, 25, 50]

export function TradeHistoryTable() {
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(25)
  const { data, isLoading } = useGetTradeHistoryQuery({ offset: page * limit, limit })

  if (isLoading) {
    return (
      <Typography variant="body2" color="textSecondary">
        Loading trade history…
      </Typography>
    )
  }

  const trades = data?.items ?? []

  if (trades.length === 0 && page === 0) {
    return (
      <Typography variant="body2" color="textSecondary">
        No trades yet.
      </Typography>
    )
  }

  return (
    <Paper variant="outlined">
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Executed At</TableCell>
              <TableCell>Symbol</TableCell>
              <TableCell>Side</TableCell>
              <TableCell align="right">Price</TableCell>
              <TableCell align="right">Quantity</TableCell>
              <TableCell align="right">Quote Qty</TableCell>
              <TableCell align="right">Fee</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {trades.map((trade) => (
              <TableRow key={trade.id}>
                <TableCell>{new Date(trade.executed_at).toLocaleString()}</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>{trade.symbol}</TableCell>
                <TableCell>
                  <Chip
                    label={trade.side}
                    size="small"
                    color={trade.side === 'BUY' ? 'success' : 'error'}
                    variant="outlined"
                  />
                </TableCell>
                <TableCell align="right">{formatCurrency(trade.price)}</TableCell>
                <TableCell align="right">{formatQuantity(trade.quantity)}</TableCell>
                <TableCell align="right">{formatCurrency(trade.quote_quantity)}</TableCell>
                <TableCell align="right">
                  {formatQuantity(trade.commission)} {trade.commission_asset ?? ''}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      <TablePagination
        component="div"
        count={-1}
        page={page}
        onPageChange={(_event, newPage) => setPage(newPage)}
        rowsPerPage={limit}
        rowsPerPageOptions={PAGE_SIZE_OPTIONS}
        onRowsPerPageChange={(event) => {
          setLimit(Number(event.target.value))
          setPage(0)
        }}
        labelDisplayedRows={({ from, to }) => `${from}–${to}`}
        slotProps={{ actions: { nextButton: { disabled: trades.length < limit } } }}
      />
    </Paper>
  )
}
