import DownloadRoundedIcon from '@mui/icons-material/DownloadRounded'
import {
  Button,
  Chip,
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
import { formatCurrency, formatQuantity } from '@/shared/lib/format'
import type { BacktestFill } from '../types'

interface TradeLogTableProps {
  fills: BacktestFill[]
}

const CSV_COLUMNS = [
  'executed_at',
  'side',
  'price',
  'quantity',
  'commission',
  'realized_pnl',
  'cash_after',
  'position_after',
  'reason',
] as const

export function TradeLogTable({ fills }: TradeLogTableProps) {
  if (fills.length === 0) {
    return (
      <Typography variant="body2" color="textSecondary">
        No trades were generated for this backtest.
      </Typography>
    )
  }

  return (
    <Stack spacing={1.5}>
      <Stack direction="row" sx={{ justifyContent: 'flex-end' }}>
        <Button
          size="small"
          startIcon={<DownloadRoundedIcon />}
          onClick={() => downloadCsv(fills)}
          variant="outlined"
        >
          Export CSV
        </Button>
      </Stack>
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Executed At</TableCell>
              <TableCell>Side</TableCell>
              <TableCell align="right">Price</TableCell>
              <TableCell align="right">Quantity</TableCell>
              <TableCell align="right">Commission</TableCell>
              <TableCell align="right">Realized P&L</TableCell>
              <TableCell align="right">Position After</TableCell>
              <TableCell>Reason</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {fills.map((fill, index) => (
              <TableRow key={`${fill.executed_at}-${index}`}>
                <TableCell>{new Date(fill.executed_at).toLocaleString()}</TableCell>
                <TableCell>
                  <Chip
                    label={fill.side}
                    size="small"
                    color={fill.side === 'BUY' ? 'success' : 'error'}
                    variant="outlined"
                  />
                </TableCell>
                <TableCell align="right">{formatCurrency(fill.price)}</TableCell>
                <TableCell align="right">{formatQuantity(fill.quantity)}</TableCell>
                <TableCell align="right">{formatCurrency(fill.commission)}</TableCell>
                <TableCell align="right">{formatCurrency(fill.realized_pnl)}</TableCell>
                <TableCell align="right">{formatQuantity(fill.position_after)}</TableCell>
                <TableCell>{fill.reason}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>
  )
}

function downloadCsv(fills: BacktestFill[]): void {
  const header = CSV_COLUMNS.join(',')
  const rows = fills.map((fill) =>
    CSV_COLUMNS.map((column) => csvEscape(String(fill[column]))).join(','),
  )
  const csv = [header, ...rows].join('\n')

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `backtest-trade-log-${Date.now()}.csv`
  link.click()
  URL.revokeObjectURL(url)
}

function csvEscape(value: string): string {
  return /[",\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value
}
