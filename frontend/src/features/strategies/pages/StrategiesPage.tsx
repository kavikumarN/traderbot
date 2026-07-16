import { useEffect, useState } from 'react'
import { Alert, Box, Button, Stack, Typography } from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import { useLocation, useNavigate } from 'react-router-dom'
import { LoadingSpinner } from '@/components/feedback/LoadingSpinner'
import { getApiErrorMessage } from '@/shared/types/api'
import { CreateStrategyDialog, type CreateStrategyInitialValues } from '../components/CreateStrategyDialog'
import { SignalsTable } from '../components/SignalsTable'
import { StrategiesTable } from '../components/StrategiesTable'
import { useListStrategiesQuery } from '../strategiesApi'

const POLL_INTERVAL_MS = 30_000

interface AiSuggestionHandoff {
  symbol: string
  strategyType: string
  parameters: Record<string, unknown>
}

export default function StrategiesPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [initialValues, setInitialValues] = useState<CreateStrategyInitialValues | undefined>(undefined)
  // Bumped every time `initialValues` changes so `CreateStrategyDialog` is
  // given a fresh `key` — it seeds its form fields from `initialValues` only
  // in its own `useState` initializer, which React does not re-run just
  // because a prop changed on an already-mounted component.
  const [dialogInstance, setDialogInstance] = useState(0)

  const { data: strategies, isLoading, isError, error } = useListStrategiesQuery(undefined, {
    pollingInterval: POLL_INTERVAL_MS,
  })

  // Hand-off from the Insights Pattern Viewer's "Apply Suggestion" button
  // (see `features/insights/components/PatternViewer.tsx`) — open straight
  // into a pre-filled Register-a-Strategy dialog instead of making the user
  // re-enter what the AI Strategy Builder already worked out.
  useEffect(() => {
    const handoff = (location.state as { aiSuggestion?: AiSuggestionHandoff } | null)?.aiSuggestion
    if (handoff) {
      setInitialValues({ symbol: handoff.symbol, strategyType: handoff.strategyType, parameters: handoff.parameters })
      setDialogInstance((n) => n + 1)
      setDialogOpen(true)
      navigate(location.pathname, { replace: true, state: null })
    }
  }, [location.state, location.pathname, navigate])

  return (
    <Stack spacing={3}>
      <Box className="flex items-center justify-between">
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            Strategies
          </Typography>
          <Typography variant="body1" color="textSecondary" className="mt-1">
            Register strategies, control their lifecycle, and review the signals they generate.
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<AddRoundedIcon />}
          onClick={() => {
            setInitialValues(undefined)
            setDialogInstance((n) => n + 1)
            setDialogOpen(true)
          }}
        >
          New Strategy
        </Button>
      </Box>

      {isLoading ? <LoadingSpinner label="Loading strategies…" /> : null}
      {isError ? <Alert severity="error">{getApiErrorMessage(error)}</Alert> : null}
      {strategies ? (
        <StrategiesTable strategies={strategies} selectedId={selectedId} onSelect={setSelectedId} />
      ) : null}

      {selectedId ? (
        <Stack spacing={1.5}>
          <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
            Signals
          </Typography>
          <SignalsTable strategyId={selectedId} />
        </Stack>
      ) : null}

      <CreateStrategyDialog
        key={dialogInstance}
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        initialValues={initialValues}
        onCreated={(strategyId) => {
          setDialogOpen(false)
          setSelectedId(strategyId)
        }}
      />
    </Stack>
  )
}
