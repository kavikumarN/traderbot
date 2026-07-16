import { Chip } from '@mui/material'
import type { StrategyStatus } from '../types'

const COLOR_BY_STATUS: Record<StrategyStatus, 'default' | 'success' | 'warning' | 'error' | 'info'> = {
  DRAFT: 'default',
  VALIDATED: 'info',
  BACKTESTING: 'info',
  PAPER_TRADING: 'warning',
  LIVE: 'success',
  PAUSED: 'warning',
  REJECTED: 'error',
  RETIRED: 'default',
}

export function StrategyStatusChip({ status }: { status: StrategyStatus }) {
  return <Chip label={status.replace('_', ' ')} color={COLOR_BY_STATUS[status]} size="small" variant="outlined" />
}
