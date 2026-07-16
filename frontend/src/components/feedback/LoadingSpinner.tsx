import { CircularProgress, Stack, Typography } from '@mui/material'

interface LoadingSpinnerProps {
  label?: string
  size?: number
}

export function LoadingSpinner({ label, size = 32 }: LoadingSpinnerProps) {
  return (
    <Stack
      spacing={1.5}
      sx={{ alignItems: 'center', justifyContent: 'center' }}
      className="py-8"
    >
      <CircularProgress size={size} />
      {label ? (
        <Typography variant="body2" color="textSecondary">
          {label}
        </Typography>
      ) : null}
    </Stack>
  )
}
