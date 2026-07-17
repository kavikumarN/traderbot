import { useState, type FormEvent } from 'react'
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
import { useCreateRiskRuleMutation } from '../riskApi'
import type { RiskRuleType } from '../types'

const RULE_TYPES: RiskRuleType[] = [
  'MAX_POSITION_NOTIONAL',
  'MAX_DAILY_LOSS',
  'MAX_ORDER_RATE',
  'SYMBOL_WHITELIST',
  'MAX_DRAWDOWN',
  'MAX_LEVERAGE',
  'MAX_OPEN_TRADES',
  'MAX_PORTFOLIO_EXPOSURE',
  'RISK_PER_TRADE',
  'DRAWDOWN_DERISK',
]

interface CreateRiskRuleDialogProps {
  open: boolean
  onClose: () => void
}

export function CreateRiskRuleDialog({ open, onClose }: CreateRiskRuleDialogProps) {
  const [createRiskRule, { isLoading }] = useCreateRiskRuleMutation()

  const [ruleType, setRuleType] = useState<RiskRuleType>('MAX_DAILY_LOSS')
  const [threshold, setThreshold] = useState('')
  const [configText, setConfigText] = useState('{}')
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)

    let config: Record<string, unknown>
    try {
      config = JSON.parse(configText || '{}')
    } catch {
      setError('Config must be valid JSON.')
      return
    }

    try {
      await createRiskRule({
        rule_type: ruleType,
        threshold: threshold || null,
        is_active: true,
        config,
      }).unwrap()
      setThreshold('')
      setConfigText('{}')
      onClose()
    } catch (submitError) {
      setError(getApiErrorMessage(submitError))
    }
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>New Risk Rule</DialogTitle>
      <DialogContent>
        <Stack component="form" id="create-risk-rule-form" spacing={2} className="mt-1" onSubmit={handleSubmit}>
          {error ? <Alert severity="error">{error}</Alert> : null}

          <TextField select label="Rule Type" value={ruleType} onChange={(e) => setRuleType(e.target.value as RiskRuleType)} fullWidth>
            {RULE_TYPES.map((type) => (
              <MenuItem key={type} value={type}>
                {type.replace(/_/g, ' ')}
              </MenuItem>
            ))}
          </TextField>

          <TextField
            label="Threshold (optional)"
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
            helperText="A number — meaning depends on rule type (e.g. max USDT loss, max leverage multiple)"
            fullWidth
          />

          <TextField
            label="Config (JSON)"
            value={configText}
            onChange={(e) => setConfigText(e.target.value)}
            multiline
            minRows={3}
            helperText="Rule-specific — e.g. { &quot;symbols&quot;: [&quot;BTCUSDT&quot;] } for a symbol whitelist"
            fullWidth
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button type="submit" form="create-risk-rule-form" variant="contained" loading={isLoading}>
          Create
        </Button>
      </DialogActions>
    </Dialog>
  )
}
