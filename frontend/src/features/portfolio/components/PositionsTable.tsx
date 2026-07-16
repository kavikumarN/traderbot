import {
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  useTheme,
} from '@mui/material'
import { formatCurrency, formatPercent, formatQuantity, isNonNegative } from '@/shared/lib/format'
import type { Position } from '../types'

interface PositionsTableProps {
  positions: Position[]
}

export function PositionsTable({ positions }: PositionsTableProps) {
  const theme = useTheme()

  if (positions.length === 0) {
    return (
      <Typography variant="body2" color="textSecondary">
        No open positions.
      </Typography>
    )
  }

  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Symbol</TableCell>
            <TableCell align="right">Quantity</TableCell>
            <TableCell align="right">Avg Entry</TableCell>
            <TableCell align="right">Current Price</TableCell>
            <TableCell align="right">Market Value</TableCell>
            <TableCell align="right">Unrealized P&L</TableCell>
            <TableCell align="right">Realized P&L</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {positions.map((position) => (
            <TableRow key={position.id}>
              <TableCell sx={{ fontWeight: 600 }}>{position.symbol}</TableCell>
              <TableCell align="right">{formatQuantity(position.quantity)}</TableCell>
              <TableCell align="right">{formatCurrency(position.avg_entry_price)}</TableCell>
              <TableCell align="right">{formatCurrency(position.current_price)}</TableCell>
              <TableCell align="right">{formatCurrency(position.market_value)}</TableCell>
              <TableCell
                align="right"
                sx={{
                  color: isNonNegative(position.unrealized_pnl) ? theme.palette.success.main : theme.palette.error.main,
                }}
              >
                {formatCurrency(position.unrealized_pnl)} ({formatPercent(position.unrealized_pnl_pct)})
              </TableCell>
              <TableCell align="right">{formatCurrency(position.realized_pnl)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  )
}
