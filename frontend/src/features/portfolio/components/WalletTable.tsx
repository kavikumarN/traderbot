import {
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import { formatQuantity } from '@/shared/lib/format'
import type { Wallet } from '../types'

interface WalletTableProps {
  wallets: Wallet[]
}

export function WalletTable({ wallets }: WalletTableProps) {
  if (wallets.length === 0) {
    return (
      <Typography variant="body2" color="textSecondary">
        No wallet balances yet.
      </Typography>
    )
  }

  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Asset</TableCell>
            <TableCell align="right">Free</TableCell>
            <TableCell align="right">Locked</TableCell>
            <TableCell align="right">Total</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {wallets.map((wallet) => (
            <TableRow key={wallet.id}>
              <TableCell sx={{ fontWeight: 600 }}>{wallet.asset}</TableCell>
              <TableCell align="right">{formatQuantity(wallet.free)}</TableCell>
              <TableCell align="right">{formatQuantity(wallet.locked)}</TableCell>
              <TableCell align="right">{formatQuantity(wallet.total)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  )
}
