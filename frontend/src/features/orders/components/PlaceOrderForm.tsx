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
import { usePlaceLimitOrderMutation, usePlaceMarketOrderMutation, usePlaceStopOrderMutation } from '../ordersApi'
import type { OrderSide } from '../types'

type OrderKind = 'market' | 'limit' | 'stop'

export function PlaceOrderForm() {
  const [symbol, setSymbol] = useState('BTCUSDT')
  const [side, setSide] = useState<OrderSide>('BUY')
  const [orderKind, setOrderKind] = useState<OrderKind>('market')
  const [quantity, setQuantity] = useState('0.01')
  const [price, setPrice] = useState('')
  const [stopPrice, setStopPrice] = useState('')
  const [limitPrice, setLimitPrice] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const [placeMarketOrder, { isLoading: isPlacingMarket }] = usePlaceMarketOrderMutation()
  const [placeLimitOrder, { isLoading: isPlacingLimit }] = usePlaceLimitOrderMutation()
  const [placeStopOrder, { isLoading: isPlacingStop }] = usePlaceStopOrderMutation()

  const isSubmitting = isPlacingMarket || isPlacingLimit || isPlacingStop

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSuccess(null)

    try {
      let order
      if (orderKind === 'market') {
        order = await placeMarketOrder({ symbol, side, quantity }).unwrap()
      } else if (orderKind === 'limit') {
        order = await placeLimitOrder({ symbol, side, quantity, price }).unwrap()
      } else {
        order = await placeStopOrder({
          symbol,
          side,
          quantity,
          stop_price: stopPrice,
          limit_price: limitPrice || null,
        }).unwrap()
      }
      setSuccess(`Order ${order.id.slice(0, 8)} placed — status ${order.status}.`)
    } catch (submitError) {
      setError(getApiErrorMessage(submitError))
    }
  }

  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="subtitle1" sx={{ fontWeight: 600 }} className="mb-3">
          Place an Order
        </Typography>
        <Box component="form" noValidate onSubmit={handleSubmit}>
          <Stack spacing={2}>
            {error ? <Alert severity="error">{error}</Alert> : null}
            {success ? <Alert severity="success">{success}</Alert> : null}

            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <TextField
                label="Symbol"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                fullWidth
              />
              <TextField select label="Side" value={side} onChange={(e) => setSide(e.target.value as OrderSide)} fullWidth>
                <MenuItem value="BUY">Buy</MenuItem>
                <MenuItem value="SELL">Sell</MenuItem>
              </TextField>
              <TextField
                select
                label="Order Type"
                value={orderKind}
                onChange={(e) => setOrderKind(e.target.value as OrderKind)}
                fullWidth
              >
                <MenuItem value="market">Market</MenuItem>
                <MenuItem value="limit">Limit</MenuItem>
                <MenuItem value="stop">Stop</MenuItem>
              </TextField>
            </Stack>

            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <TextField label="Quantity" value={quantity} onChange={(e) => setQuantity(e.target.value)} fullWidth />

              {orderKind === 'limit' ? (
                <TextField label="Limit Price" value={price} onChange={(e) => setPrice(e.target.value)} fullWidth />
              ) : null}

              {orderKind === 'stop' ? (
                <>
                  <TextField
                    label="Stop Price"
                    value={stopPrice}
                    onChange={(e) => setStopPrice(e.target.value)}
                    fullWidth
                  />
                  <TextField
                    label="Limit Price (optional)"
                    value={limitPrice}
                    onChange={(e) => setLimitPrice(e.target.value)}
                    fullWidth
                  />
                </>
              ) : null}
            </Stack>

            <Button type="submit" variant="contained" size="large" loading={isSubmitting}>
              Place {side === 'BUY' ? 'Buy' : 'Sell'} Order
            </Button>
          </Stack>
        </Box>
      </CardContent>
    </Card>
  )
}
