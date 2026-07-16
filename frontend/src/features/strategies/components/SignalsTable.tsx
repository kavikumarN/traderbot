import { Chip, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from '@mui/material'
import { formatQuantity } from '@/shared/lib/format'
import { useListSignalsQuery } from '../strategiesApi'

const STATUS_COLOR: Record<string, 'default' | 'success' | 'warning' | 'error'> = {
  PENDING: 'default',
  APPROVED: 'success',
  REJECTED: 'error',
  EXPIRED: 'warning',
  CONSUMED: 'success',
}

export function SignalsTable({ strategyId }: { strategyId: string }) {
  const { data: signals, isLoading } = useListSignalsQuery({ strategyId })

  if (isLoading) {
    return null
  }

  if (!signals || signals.length === 0) {
    return (
      <Paper variant="outlined" className="p-6">
        <Typography variant="body2" color="textSecondary">
          No signals generated yet for this strategy.
        </Typography>
      </Paper>
    )
  }

  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Generated</TableCell>
            <TableCell>Symbol</TableCell>
            <TableCell>Side</TableCell>
            <TableCell align="right">Quantity</TableCell>
            <TableCell align="right">Target Price</TableCell>
            <TableCell>Status</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {signals.map((signal) => (
            <TableRow key={signal.id}>
              <TableCell>{new Date(signal.generated_at).toLocaleString()}</TableCell>
              <TableCell>{signal.symbol}</TableCell>
              <TableCell>{signal.side}</TableCell>
              <TableCell align="right">{formatQuantity(signal.quantity)}</TableCell>
              <TableCell align="right">{signal.target_price ? formatQuantity(signal.target_price) : '—'}</TableCell>
              <TableCell>
                <Chip label={signal.status} size="small" color={STATUS_COLOR[signal.status] ?? 'default'} variant="outlined" />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  )
}
