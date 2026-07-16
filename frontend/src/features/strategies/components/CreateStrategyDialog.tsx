import { useEffect, useState, type FormEvent } from 'react'
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  TextField,
} from '@mui/material'
import { getApiErrorMessage } from '@/shared/types/api'
import { useCreateStrategyMutation, useListStrategyTypesQuery } from '../strategiesApi'

interface CreateStrategyDialogProps {
  open: boolean
  onClose: () => void
  onCreated: (strategyId: string) => void
}

export function CreateStrategyDialog({ open, onClose, onCreated }: CreateStrategyDialogProps) {
  const { data: strategyTypes } = useListStrategyTypesQuery()
  const [createStrategy, { isLoading }] = useCreateStrategyMutation()

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [symbol, setSymbol] = useState('BTCUSDT')
  const [strategyType, setStrategyType] = useState('')
  const [parametersText, setParametersText] = useState('{}')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!strategyType && strategyTypes && strategyTypes.length > 0) {
      setStrategyType(strategyTypes[0].strategy_type)
    }
  }, [strategyType, strategyTypes])

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)

    let parameters: Record<string, unknown>
    try {
      parameters = JSON.parse(parametersText || '{}')
    } catch {
      setError('Parameters must be valid JSON.')
      return
    }

    try {
      const strategy = await createStrategy({
        name,
        description,
        symbol,
        strategy_type: strategyType,
        parameters,
      }).unwrap()
      onCreated(strategy.id)
      setName('')
      setDescription('')
      setParametersText('{}')
    } catch (submitError) {
      setError(getApiErrorMessage(submitError))
    }
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Register a Strategy</DialogTitle>
      <DialogContent>
        <Stack component="form" id="create-strategy-form" spacing={2} className="mt-1" onSubmit={handleSubmit}>
          {error ? <Alert severity="error">{error}</Alert> : null}

          <TextField
            label="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            fullWidth
          />
          <TextField
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            multiline
            minRows={2}
            fullWidth
          />
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <TextField
              label="Symbol"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              required
              fullWidth
            />
            <TextField
              select
              label="Strategy Type"
              value={strategyType}
              onChange={(e) => setStrategyType(e.target.value)}
              required
              fullWidth
            >
              {(strategyTypes ?? []).map((type) => (
                <MenuItem key={type.strategy_type} value={type.strategy_type}>
                  {type.strategy_type}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
          <TextField
            label="Parameters (JSON)"
            value={parametersText}
            onChange={(e) => setParametersText(e.target.value)}
            multiline
            minRows={3}
            helperText="Plugin-specific — e.g. { &quot;fast_period&quot;: 12, &quot;slow_period&quot;: 26, &quot;quantity&quot;: &quot;0.01&quot; }"
            fullWidth
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button type="submit" form="create-strategy-form" variant="contained" loading={isLoading}>
          Create
        </Button>
      </DialogActions>
    </Dialog>
  )
}
