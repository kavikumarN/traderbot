import { useEffect, useState, type FormEvent } from 'react'
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from '@mui/material'
import { AnalyzeForm } from '@/features/insights/components/AnalyzeForm'
import { PatternsTable } from '@/features/insights/components/PatternsTable'
import { SuggestionPanel } from '@/features/insights/components/SuggestionPanel'
import { useAnalyzePatternsMutation } from '@/features/insights/insightsApi'
import { terminal } from '@/features/insights/terminal'
import { getApiErrorMessage } from '@/shared/types/api'
import { useCreateStrategyMutation, useListStrategyTypesQuery } from '../strategiesApi'

export interface CreateStrategyInitialValues {
  symbol?: string
  strategyType?: string
  parameters?: Record<string, unknown>
}

interface CreateStrategyDialogProps {
  open: boolean
  onClose: () => void
  onCreated: (strategyId: string) => void
  initialValues?: CreateStrategyInitialValues
}

const TABS = ['manual', 'ai-builder'] as const
type TabKey = (typeof TABS)[number]

export function CreateStrategyDialog({ open, onClose, onCreated, initialValues }: CreateStrategyDialogProps) {
  const { data: strategyTypes } = useListStrategyTypesQuery()
  const [createStrategy, { isLoading }] = useCreateStrategyMutation()

  const [tab, setTab] = useState<TabKey>('manual')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [symbol, setSymbol] = useState(initialValues?.symbol ?? 'BTCUSDT')
  const [strategyType, setStrategyType] = useState(initialValues?.strategyType ?? '')
  const [parametersText, setParametersText] = useState(
    initialValues?.parameters ? JSON.stringify(initialValues.parameters, null, 2) : '{}'
  )
  const [error, setError] = useState<string | null>(null)

  const [aiIntervals, setAiIntervals] = useState<string[]>(['15m', '1h', '1d'])
  const [analyze, { data: analysis, isLoading: isAnalyzing, error: analyzeError }] = useAnalyzePatternsMutation()

  useEffect(() => {
    if (!strategyType && strategyTypes && strategyTypes.length > 0) {
      setStrategyType(strategyTypes[0].strategy_type)
    }
  }, [strategyType, strategyTypes])

  function applySuggestion() {
    if (!analysis?.suggestion) return
    setSymbol(analysis.symbol)
    setStrategyType(analysis.suggestion.strategy_type)
    setParametersText(JSON.stringify(analysis.suggestion.parameters, null, 2))
    setTab('manual')
  }

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
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>Register a Strategy</DialogTitle>
      <Tabs value={tab} onChange={(_e, value: TabKey) => setTab(value)} className="px-6">
        <Tab label="Manual" value="manual" />
        <Tab label="AI Strategy Builder" value="ai-builder" />
      </Tabs>
      <DialogContent>
        {tab === 'manual' ? (
          <Stack component="form" id="create-strategy-form" spacing={2} className="mt-1" onSubmit={handleSubmit}>
            {error ? <Alert severity="error">{error}</Alert> : null}

            <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} required fullWidth />
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
        ) : (
          <Stack spacing={2} className="mt-1">
            <Typography variant="body2" color="textSecondary">
              Analyze recent candlestick/chart patterns for a symbol and let the detector suggest a strategy type
              and starter parameters — review, then apply them to the Manual tab.
            </Typography>

            <AnalyzeForm
              symbol={symbol}
              onSymbolChange={setSymbol}
              intervals={aiIntervals}
              onIntervalsChange={setAiIntervals}
              onAnalyze={() => analyze({ symbol, intervals: aiIntervals })}
              isLoading={isAnalyzing}
            />

            {analyzeError ? <Alert severity="error">{getApiErrorMessage(analyzeError)}</Alert> : null}

            {analysis ? (
              <Box sx={{ bgcolor: terminal.bg, p: 2, borderRadius: '2px' }}>
                <Stack spacing={2}>
                  {analysis.suggestion ? (
                    <SuggestionPanel suggestion={analysis.suggestion} onApply={applySuggestion} />
                  ) : null}
                  <PatternsTable intervals={analysis.intervals} />
                </Stack>
              </Box>
            ) : null}
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        {tab === 'manual' ? (
          <Button type="submit" form="create-strategy-form" variant="contained" loading={isLoading}>
            Create
          </Button>
        ) : null}
      </DialogActions>
    </Dialog>
  )
}
