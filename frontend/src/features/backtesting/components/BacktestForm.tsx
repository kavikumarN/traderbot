import { useState, type FormEvent } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { getApiErrorMessage } from '@/shared/types/api'
import { useCreateStrategyMutation } from '@/features/strategies/strategiesApi'
import { useRunBacktestMutation } from '../backtestingApi'
import type { Backtest, StrategyType } from '../types'

const INTERVAL_OPTIONS = ['1m', '5m', '15m', '1h', '4h', '1d'] as const

function defaultDateTimeLocal(hoursAgo: number): string {
  const date = new Date(Date.now() - hoursAgo * 60 * 60 * 1000)
  date.setSeconds(0, 0)
  return date.toISOString().slice(0, 16)
}

interface BacktestFormProps {
  onResult: (backtest: Backtest) => void
}

export function BacktestForm({ onResult }: BacktestFormProps) {
  const [symbol, setSymbol] = useState('BTCUSDT')
  const [strategyType, setStrategyType] = useState<StrategyType>('EMA_CROSSOVER')
  const [interval, setInterval] = useState('1h')
  const [periodStart, setPeriodStart] = useState(defaultDateTimeLocal(24 * 14))
  const [periodEnd, setPeriodEnd] = useState(defaultDateTimeLocal(0))
  const [initialBalance, setInitialBalance] = useState('10000')
  const [commissionRate, setCommissionRate] = useState('0.001')
  const [quantity, setQuantity] = useState('0.01')
  const [fastPeriod, setFastPeriod] = useState('12')
  const [slowPeriod, setSlowPeriod] = useState('26')
  const [signalPeriod, setSignalPeriod] = useState('9')
  const [rsiPeriod, setRsiPeriod] = useState('14')
  const [oversold, setOversold] = useState('30')
  const [overbought, setOverbought] = useState('70')

  const [createStrategy, { isLoading: isCreatingStrategy }] = useCreateStrategyMutation()
  const [runBacktest, { isLoading: isRunning }] = useRunBacktestMutation()
  const [formError, setFormError] = useState<string | null>(null)

  const isSubmitting = isCreatingStrategy || isRunning

  function parametersForStrategyType(): Record<string, unknown> {
    switch (strategyType) {
      case 'EMA_CROSSOVER':
        return { fast_period: Number(fastPeriod), slow_period: Number(slowPeriod), quantity }
      case 'RSI':
        return {
          period: Number(rsiPeriod),
          oversold: Number(oversold),
          overbought: Number(overbought),
          quantity,
        }
      case 'MACD':
        return {
          fast_period: Number(fastPeriod),
          slow_period: Number(slowPeriod),
          signal_period: Number(signalPeriod),
          quantity,
        }
      default:
        return { quantity }
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setFormError(null)
    try {
      const strategy = await createStrategy({
        name: `${symbol} ${strategyType} backtest`,
        description: '',
        symbol,
        strategy_type: strategyType,
        parameters: parametersForStrategyType(),
      }).unwrap()

      const backtest = await runBacktest({
        strategyId: strategy.id,
        body: {
          period_start: new Date(periodStart).toISOString(),
          period_end: new Date(periodEnd).toISOString(),
          interval,
          initial_balance: initialBalance,
          commission_rate: commissionRate,
        },
      }).unwrap()

      onResult(backtest)
    } catch (error) {
      setFormError(getApiErrorMessage(error))
    }
  }

  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="subtitle1" sx={{ fontWeight: 600 }} className="mb-3">
          Run a Backtest
        </Typography>
        <Box component="form" noValidate onSubmit={handleSubmit}>
          <Stack spacing={2}>
            {formError ? <Alert severity="error">{formError}</Alert> : null}

            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <TextField
                label="Symbol"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                fullWidth
              />
              <TextField
                select
                label="Strategy"
                value={strategyType}
                onChange={(e) => setStrategyType(e.target.value as StrategyType)}
                fullWidth
              >
                <MenuItem value="EMA_CROSSOVER">EMA Crossover</MenuItem>
                <MenuItem value="RSI">RSI</MenuItem>
                <MenuItem value="MACD">MACD</MenuItem>
              </TextField>
              <TextField
                select
                label="Candle Interval"
                value={interval}
                onChange={(e) => setInterval(e.target.value)}
                fullWidth
              >
                {INTERVAL_OPTIONS.map((option) => (
                  <MenuItem key={option} value={option}>
                    {option}
                  </MenuItem>
                ))}
              </TextField>
            </Stack>

            {strategyType === 'EMA_CROSSOVER' ? (
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                <TextField
                  label="Fast Period"
                  type="number"
                  value={fastPeriod}
                  onChange={(e) => setFastPeriod(e.target.value)}
                  fullWidth
                />
                <TextField
                  label="Slow Period"
                  type="number"
                  value={slowPeriod}
                  onChange={(e) => setSlowPeriod(e.target.value)}
                  fullWidth
                />
              </Stack>
            ) : null}

            {strategyType === 'MACD' ? (
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                <TextField
                  label="Fast Period"
                  type="number"
                  value={fastPeriod}
                  onChange={(e) => setFastPeriod(e.target.value)}
                  fullWidth
                />
                <TextField
                  label="Slow Period"
                  type="number"
                  value={slowPeriod}
                  onChange={(e) => setSlowPeriod(e.target.value)}
                  fullWidth
                />
                <TextField
                  label="Signal Period"
                  type="number"
                  value={signalPeriod}
                  onChange={(e) => setSignalPeriod(e.target.value)}
                  fullWidth
                />
              </Stack>
            ) : null}

            {strategyType === 'RSI' ? (
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                <TextField
                  label="Period"
                  type="number"
                  value={rsiPeriod}
                  onChange={(e) => setRsiPeriod(e.target.value)}
                  fullWidth
                />
                <TextField
                  label="Oversold"
                  type="number"
                  value={oversold}
                  onChange={(e) => setOversold(e.target.value)}
                  fullWidth
                />
                <TextField
                  label="Overbought"
                  type="number"
                  value={overbought}
                  onChange={(e) => setOverbought(e.target.value)}
                  fullWidth
                />
              </Stack>
            ) : null}

            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <TextField
                label="Period Start"
                type="datetime-local"
                value={periodStart}
                onChange={(e) => setPeriodStart(e.target.value)}
                fullWidth
                slotProps={{ inputLabel: { shrink: true } }}
              />
              <TextField
                label="Period End"
                type="datetime-local"
                value={periodEnd}
                onChange={(e) => setPeriodEnd(e.target.value)}
                fullWidth
                slotProps={{ inputLabel: { shrink: true } }}
              />
            </Stack>

            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <TextField
                label="Quantity per Trade"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                fullWidth
              />
              <TextField
                label="Initial Balance"
                value={initialBalance}
                onChange={(e) => setInitialBalance(e.target.value)}
                fullWidth
              />
              <TextField
                label="Commission Rate"
                value={commissionRate}
                onChange={(e) => setCommissionRate(e.target.value)}
                fullWidth
              />
            </Stack>

            <Button type="submit" variant="contained" size="large" loading={isSubmitting}>
              Run Backtest
            </Button>
          </Stack>
        </Box>
      </CardContent>
    </Card>
  )
}
