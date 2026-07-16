import { useState, type FormEvent } from 'react'
import { Alert, Box, Button, Card, CardContent, MenuItem, Stack, TextField, Typography } from '@mui/material'
import { formatQuantity } from '@/shared/lib/format'
import { getApiErrorMessage } from '@/shared/types/api'
import { useCalculatePositionSizeMutation } from '../riskApi'
import type { PositionSizeResponse } from '../types'

export function PositionSizeCalculator() {
  const [side, setSide] = useState<'BUY' | 'SELL'>('BUY')
  const [entryPrice, setEntryPrice] = useState('')
  const [stopLossPct, setStopLossPct] = useState('0.02')
  const [riskPerTradePct, setRiskPerTradePct] = useState('0.01')
  const [rewardRiskRatio, setRewardRiskRatio] = useState('2')
  const [result, setResult] = useState<PositionSizeResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [calculate, { isLoading }] = useCalculatePositionSizeMutation()

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setResult(null)
    try {
      const response = await calculate({
        side,
        entry_price: entryPrice,
        stop_loss_pct: stopLossPct || null,
        risk_per_trade_pct: riskPerTradePct || null,
        reward_risk_ratio: rewardRiskRatio || null,
      }).unwrap()
      setResult(response)
    } catch (submitError) {
      setError(getApiErrorMessage(submitError))
    }
  }

  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="subtitle1" sx={{ fontWeight: 600 }} className="mb-3">
          Position Size Calculator
        </Typography>
        <Box component="form" noValidate onSubmit={handleSubmit}>
          <Stack spacing={2}>
            {error ? <Alert severity="error">{error}</Alert> : null}

            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <TextField select label="Side" value={side} onChange={(e) => setSide(e.target.value as 'BUY' | 'SELL')} fullWidth>
                <MenuItem value="BUY">Buy</MenuItem>
                <MenuItem value="SELL">Sell</MenuItem>
              </TextField>
              <TextField
                label="Entry Price"
                value={entryPrice}
                onChange={(e) => setEntryPrice(e.target.value)}
                required
                fullWidth
              />
            </Stack>

            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <TextField
                label="Stop-Loss %"
                value={stopLossPct}
                onChange={(e) => setStopLossPct(e.target.value)}
                helperText="Fraction, e.g. 0.02 = 2%"
                fullWidth
              />
              <TextField
                label="Risk per Trade %"
                value={riskPerTradePct}
                onChange={(e) => setRiskPerTradePct(e.target.value)}
                helperText="Fraction of equity risked"
                fullWidth
              />
              <TextField
                label="Reward:Risk Ratio"
                value={rewardRiskRatio}
                onChange={(e) => setRewardRiskRatio(e.target.value)}
                fullWidth
              />
            </Stack>

            <Button type="submit" variant="contained" loading={isLoading}>
              Calculate
            </Button>

            {result ? (
              <Box className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <Stat label="Quantity" value={formatQuantity(result.quantity)} />
                <Stat label="Stop-Loss" value={formatQuantity(result.stop_loss_price)} />
                <Stat label="Take-Profit" value={formatQuantity(result.take_profit_price)} />
                <Stat label="Equity" value={formatQuantity(result.equity)} />
              </Box>
            ) : null}
          </Stack>
        </Box>
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
