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
import { useUpdateStrategyStatusMutation } from '../strategiesApi'
import type { Strategy, StrategyStatusAction } from '../types'
import { StrategyStatusChip } from './StrategyStatusChip'

const ACTIONS_BY_STATUS: Record<string, { action: StrategyStatusAction; label: string }[]> = {
  DRAFT: [{ action: 'start_paper_trading', label: 'Start Paper Trading' }],
  VALIDATED: [{ action: 'start_paper_trading', label: 'Start Paper Trading' }],
  BACKTESTING: [{ action: 'start_paper_trading', label: 'Start Paper Trading' }],
  PAPER_TRADING: [
    { action: 'promote_to_live', label: 'Promote to Live' },
    { action: 'pause', label: 'Pause' },
  ],
  LIVE: [{ action: 'pause', label: 'Pause' }],
  PAUSED: [{ action: 'start_paper_trading', label: 'Resume Paper Trading' }],
}

interface StrategiesTableProps {
  strategies: Strategy[]
  selectedId: string | null
  onSelect: (strategyId: string) => void
}

export function StrategiesTable({ strategies, selectedId, onSelect }: StrategiesTableProps) {
  const [updateStatus, { isLoading }] = useUpdateStrategyStatusMutation()

  if (strategies.length === 0) {
    return (
      <Paper variant="outlined" className="p-6">
        <Typography variant="body2" color="textSecondary">
          No strategies registered yet.
        </Typography>
      </Paper>
    )
  }

  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Name</TableCell>
            <TableCell>Symbol</TableCell>
            <TableCell>Type</TableCell>
            <TableCell>Status</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {strategies.map((strategy) => {
            const actions = ACTIONS_BY_STATUS[strategy.status] ?? []
            return (
              <TableRow
                key={strategy.id}
                hover
                selected={strategy.id === selectedId}
                onClick={() => onSelect(strategy.id)}
                sx={{ cursor: 'pointer' }}
              >
                <TableCell>{strategy.name}</TableCell>
                <TableCell>{strategy.symbol}</TableCell>
                <TableCell>{strategy.strategy_type}</TableCell>
                <TableCell>
                  <StrategyStatusChip status={strategy.status} />
                </TableCell>
                <TableCell align="right" onClick={(e) => e.stopPropagation()}>
                  <Stack direction="row" spacing={1} sx={{ justifyContent: 'flex-end' }}>
                    {actions.map(({ action, label }) => (
                      <Button
                        key={action}
                        size="small"
                        variant="outlined"
                        disabled={isLoading}
                        onClick={() => updateStatus({ strategyId: strategy.id, body: { action } })}
                      >
                        {label}
                      </Button>
                    ))}
                    {strategy.status !== 'RETIRED' ? (
                      <Button
                        size="small"
                        color="error"
                        disabled={isLoading}
                        onClick={() => updateStatus({ strategyId: strategy.id, body: { action: 'retire' } })}
                      >
                        Retire
                      </Button>
                    ) : null}
                  </Stack>
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </TableContainer>
  )
}
