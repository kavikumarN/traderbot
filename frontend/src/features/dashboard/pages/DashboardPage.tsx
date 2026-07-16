import { Box, Card, CardContent, Chip, Stack, Typography } from '@mui/material'
import { useAuth } from '@/shared/hooks/useAuth'

const PLACEHOLDER_METRICS = [
  { label: 'Open positions', hint: 'Coming in Phase 3' },
  { label: 'Active strategies', hint: 'Coming in Phase 3' },
  { label: "Today's P&L", hint: 'Coming in Phase 3' },
]

export default function DashboardPage() {
  const { user } = useAuth()

  return (
    <Stack spacing={4}>
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Welcome{user ? `, ${user.first_name}` : ''}
        </Typography>
        <Typography variant="body1" color="textSecondary" className="mt-1">
          Your account and workspace are set up. Trading tools land in the next phase.
        </Typography>
      </Box>

      <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {PLACEHOLDER_METRICS.map((metric) => (
          <Card key={metric.label} variant="outlined">
            <CardContent>
              <Typography variant="overline" color="textSecondary">
                {metric.label}
              </Typography>
              <Typography variant="h4" sx={{ fontWeight: 700 }} className="mt-1">
                —
              </Typography>
              <Chip label={metric.hint} size="small" variant="outlined" className="mt-2" />
            </CardContent>
          </Card>
        ))}
      </Box>

      {user ? (
        <Card variant="outlined">
          <CardContent>
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }} className="mb-2">
              Account
            </Typography>
            <Stack spacing={1}>
              <AccountRow label="Email" value={user.email} />
              <AccountRow label="Roles" value={user.role_names.join(', ') || '—'} />
              <AccountRow label="Status" value={user.is_active ? 'Active' : 'Inactive'} />
            </Stack>
          </CardContent>
        </Card>
      ) : null}
    </Stack>
  )
}

function AccountRow({ label, value }: { label: string; value: string }) {
  return (
    <Box className="flex items-center justify-between border-b border-gray-100 py-2 last:border-0 dark:border-white/10">
      <Typography variant="body2" color="textSecondary">
        {label}
      </Typography>
      <Typography variant="body2" sx={{ fontWeight: 600 }}>
        {value}
      </Typography>
    </Box>
  )
}
