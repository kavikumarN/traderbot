import { useState } from 'react'
import { Alert, Box, Button, Stack, Typography } from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import { LoadingSpinner } from '@/components/feedback/LoadingSpinner'
import { getApiErrorMessage } from '@/shared/types/api'
import { CreateStrategyDialog } from '../components/CreateStrategyDialog'
import { SignalsTable } from '../components/SignalsTable'
import { StrategiesTable } from '../components/StrategiesTable'
import { useListStrategiesQuery } from '../strategiesApi'

const POLL_INTERVAL_MS = 30_000

export default function StrategiesPage() {
  const [dialogOpen, setDialogOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { data: strategies, isLoading, isError, error } = useListStrategiesQuery(undefined, {
    pollingInterval: POLL_INTERVAL_MS,
  })

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
        <Button variant="contained" startIcon={<AddRoundedIcon />} onClick={() => setDialogOpen(true)}>
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
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onCreated={(strategyId) => {
          setDialogOpen(false)
          setSelectedId(strategyId)
        }}
      />
    </Stack>
  )
}
