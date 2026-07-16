import { Link as RouterLink } from 'react-router-dom'
import { Box, Button, Stack, Typography } from '@mui/material'

export default function NotFoundPage() {
  return (
    <Box className="flex min-h-screen items-center justify-center bg-gray-50 px-4 dark:bg-neutral-950">
      <Stack spacing={2} sx={{ alignItems: 'center' }} className="text-center">
        <Typography variant="h2" sx={{ fontWeight: 800 }} color="textSecondary">
          404
        </Typography>
        <Typography variant="h6">Page not found</Typography>
        <Typography variant="body2" color="textSecondary" className="max-w-xs">
          The page you&apos;re looking for doesn&apos;t exist or has moved.
        </Typography>
        <Button component={RouterLink} to="/dashboard" variant="contained">
          Back to dashboard
        </Button>
      </Stack>
    </Box>
  )
}
