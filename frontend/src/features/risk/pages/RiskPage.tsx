import { useState } from 'react'
import { Alert, Box, Button, Stack, Tab, Tabs, Typography } from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import { LoadingSpinner } from '@/components/feedback/LoadingSpinner'
import { getApiErrorMessage } from '@/shared/types/api'
import { CreateRiskRuleDialog } from '../components/CreateRiskRuleDialog'
import { PositionSizeCalculator } from '../components/PositionSizeCalculator'
import { RiskRulesTable } from '../components/RiskRulesTable'
import { RiskStateCard } from '../components/RiskStateCard'
import { useGetRiskStateQuery, useListRiskRulesQuery } from '../riskApi'

const POLL_INTERVAL_MS = 15_000
const TABS = ['overview', 'rules'] as const
type TabKey = (typeof TABS)[number]

export default function RiskPage() {
  const [tab, setTab] = useState<TabKey>('overview')
  const [dialogOpen, setDialogOpen] = useState(false)

  const stateQuery = useGetRiskStateQuery(undefined, { pollingInterval: POLL_INTERVAL_MS })
  const rulesQuery = useListRiskRulesQuery()

  return (
    <Stack spacing={3}>
      <Box className="flex items-center justify-between">
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            Risk
          </Typography>
          <Typography variant="body1" color="textSecondary" className="mt-1">
            Circuit breaker, emergency stop, risk rules, and position sizing.
          </Typography>
        </Box>
        {tab === 'rules' ? (
          <Button variant="contained" startIcon={<AddRoundedIcon />} onClick={() => setDialogOpen(true)}>
            New Rule
          </Button>
        ) : null}
      </Box>

      <Tabs value={tab} onChange={(_event, value: TabKey) => setTab(value)}>
        <Tab label="Overview" value="overview" />
        <Tab label="Rules" value="rules" />
      </Tabs>

      {tab === 'overview' ? (
        <Stack spacing={3}>
          {stateQuery.isLoading ? <LoadingSpinner label="Loading risk state…" /> : null}
          {stateQuery.isError ? <Alert severity="error">{getApiErrorMessage(stateQuery.error)}</Alert> : null}
          {stateQuery.data ? <RiskStateCard state={stateQuery.data} /> : null}

          <PositionSizeCalculator />
        </Stack>
      ) : null}

      {tab === 'rules' ? (
        <Stack spacing={3}>
          {rulesQuery.isLoading ? <LoadingSpinner label="Loading risk rules…" /> : null}
          {rulesQuery.isError ? <Alert severity="error">{getApiErrorMessage(rulesQuery.error)}</Alert> : null}
          {rulesQuery.data ? <RiskRulesTable rules={rulesQuery.data} /> : null}
        </Stack>
      ) : null}

      <CreateRiskRuleDialog open={dialogOpen} onClose={() => setDialogOpen(false)} />
    </Stack>
  )
}
