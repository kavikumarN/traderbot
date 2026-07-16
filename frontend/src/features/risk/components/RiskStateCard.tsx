import { useState } from 'react'
import { Alert, Box, Button, Card, CardContent, Chip, Stack, TextField, Typography } from '@mui/material'
import { formatCurrency } from '@/shared/lib/format'
import { getApiErrorMessage } from '@/shared/types/api'
import { useResetCircuitBreakerMutation, useSetEmergencyStopMutation } from '../riskApi'
import type { RiskState } from '../types'

export function RiskStateCard({ state }: { state: RiskState }) {
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)

  const [setEmergencyStop, { isLoading: isTogglingStop }] = useSetEmergencyStopMutation()
  const [resetCircuitBreaker, { isLoading: isResetting }] = useResetCircuitBreakerMutation()

  async function handleToggleStop() {
    setError(null)
    try {
      await setEmergencyStop({ active: !state.emergency_stop, reason: state.emergency_stop ? null : reason }).unwrap()
      setReason('')
    } catch (submitError) {
      setError(getApiErrorMessage(submitError))
    }
  }

  async function handleReset() {
    setError(null)
    try {
      await resetCircuitBreaker().unwrap()
    } catch (submitError) {
      setError(getApiErrorMessage(submitError))
    }
  }

  return (
    <Card variant="outlined">
      <CardContent>
        <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }} className="mb-3">
          <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
            Risk Dashboard
          </Typography>
          <Chip
            label={state.is_trading_allowed ? 'Trading Allowed' : 'Trading Halted'}
            color={state.is_trading_allowed ? 'success' : 'error'}
          />
        </Stack>

        {error ? (
          <Alert severity="error" className="mb-3">
            {error}
          </Alert>
        ) : null}

        <Box className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Stat label="Circuit Breaker" value={state.circuit_breaker} />
          <Stat label="Consecutive Losses" value={String(state.consecutive_losses)} />
          <Stat label="Daily Loss" value={formatCurrency(state.daily_loss)} />
          <Stat label="Equity Peak" value={formatCurrency(state.equity_peak)} />
        </Box>

        {state.circuit_breaker === 'OPEN' ? (
          <Alert severity="warning" className="mt-3">
            Circuit breaker tripped{state.circuit_breaker_reason ? `: ${state.circuit_breaker_reason}` : ''}
            {state.circuit_breaker_resume_at
              ? ` — resumes at ${new Date(state.circuit_breaker_resume_at).toLocaleString()}`
              : ''}
          </Alert>
        ) : null}

        {state.emergency_stop ? (
          <Alert severity="error" className="mt-3">
            Emergency stop active{state.emergency_stop_reason ? `: ${state.emergency_stop_reason}` : ''}
          </Alert>
        ) : null}

        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} className="mt-4" sx={{ alignItems: { sm: 'center' } }}>
          {!state.emergency_stop ? (
            <TextField
              label="Reason (optional)"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              size="small"
              fullWidth
            />
          ) : null}
          <Button
            variant="outlined"
            color={state.emergency_stop ? 'success' : 'error'}
            disabled={isTogglingStop}
            onClick={handleToggleStop}
          >
            {state.emergency_stop ? 'Resume Trading' : 'Emergency Stop'}
          </Button>
          {state.circuit_breaker === 'OPEN' ? (
            <Button variant="outlined" disabled={isResetting} onClick={handleReset}>
              Reset Circuit Breaker
            </Button>
          ) : null}
        </Stack>
      </CardContent>
    </Card>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Box>
      <Typography variant="overline" color="textSecondary">
        {label}
      </Typography>
      <Typography variant="h6" sx={{ fontWeight: 700 }}>
        {value}
      </Typography>
    </Box>
  )
}
