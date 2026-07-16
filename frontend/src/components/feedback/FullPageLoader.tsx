import { Box } from '@mui/material'
import { LoadingSpinner } from './LoadingSpinner'

interface FullPageLoaderProps {
  label?: string
}

export function FullPageLoader({ label = 'Loading…' }: FullPageLoaderProps) {
  return (
    <Box className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-neutral-950">
      <LoadingSpinner label={label} size={40} />
    </Box>
  )
}
