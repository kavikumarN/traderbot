import { Chip } from '@mui/material'

const COLOR_BY_STATUS: Record<string, 'default' | 'success' | 'warning' | 'error' | 'info'> = {
  PENDING_RISK: 'default',
  REJECTED: 'error',
  PENDING_SUBMIT: 'default',
  SUBMITTED: 'info',
  PARTIALLY_FILLED: 'warning',
  FILLED: 'success',
  CANCELLED: 'default',
  EXPIRED: 'warning',
  SETTLED: 'success',
}

export function OrderStatusChip({ status }: { status: string }) {
  return (
    <Chip label={status.replace('_', ' ')} color={COLOR_BY_STATUS[status] ?? 'default'} size="small" variant="outlined" />
  )
}
