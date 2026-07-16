import {
  Button,
  Chip,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import { useDeleteRiskRuleMutation, useUpdateRiskRuleMutation } from '../riskApi'
import type { RiskRule } from '../types'

export function RiskRulesTable({ rules }: { rules: RiskRule[] }) {
  const [updateRiskRule, { isLoading: isUpdating }] = useUpdateRiskRuleMutation()
  const [deleteRiskRule, { isLoading: isDeleting }] = useDeleteRiskRuleMutation()

  if (rules.length === 0) {
    return (
      <Paper variant="outlined" className="p-6">
        <Typography variant="body2" color="textSecondary">
          No risk rules configured yet.
        </Typography>
      </Paper>
    )
  }

  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Rule Type</TableCell>
            <TableCell>Scope</TableCell>
            <TableCell align="right">Threshold</TableCell>
            <TableCell>Status</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rules.map((rule) => (
            <TableRow key={rule.id}>
              <TableCell>{rule.rule_type.replace(/_/g, ' ')}</TableCell>
              <TableCell>{rule.strategy_id ? `Strategy ${rule.strategy_id.slice(0, 8)}` : 'Account-wide'}</TableCell>
              <TableCell align="right">{rule.threshold ?? '—'}</TableCell>
              <TableCell>
                <Chip
                  label={rule.is_active ? 'Active' : 'Inactive'}
                  color={rule.is_active ? 'success' : 'default'}
                  size="small"
                  variant="outlined"
                />
              </TableCell>
              <TableCell align="right">
                <Stack direction="row" spacing={1} sx={{ justifyContent: 'flex-end' }}>
                  <Button
                    size="small"
                    variant="outlined"
                    disabled={isUpdating}
                    onClick={() => updateRiskRule({ ruleId: rule.id, body: { is_active: !rule.is_active } })}
                  >
                    {rule.is_active ? 'Deactivate' : 'Activate'}
                  </Button>
                  <Button
                    size="small"
                    color="error"
                    variant="outlined"
                    disabled={isDeleting}
                    onClick={() => deleteRiskRule(rule.id)}
                  >
                    Delete
                  </Button>
                </Stack>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  )
}
