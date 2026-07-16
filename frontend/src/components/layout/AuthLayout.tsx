import type { ReactNode } from 'react'
import { Box, Paper, Stack, Typography } from '@mui/material'
import ShowChartRoundedIcon from '@mui/icons-material/ShowChartRounded'

interface AuthLayoutProps {
  title: string
  subtitle: string
  children: ReactNode
}

export function AuthLayout({ title, subtitle, children }: AuthLayoutProps) {
  return (
    <Box className="flex min-h-screen items-center justify-center bg-gray-50 px-4 py-10 dark:bg-neutral-950">
      <Box className="w-full max-w-sm">
        <Stack spacing={1} sx={{ alignItems: 'center' }} className="mb-8">
          <Box className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-600 text-white">
            <ShowChartRoundedIcon />
          </Box>
          <Typography variant="h5" component="h1" sx={{ fontWeight: 700 }}>
            {title}
          </Typography>
          <Typography variant="body2" color="textSecondary" className="text-center">
            {subtitle}
          </Typography>
        </Stack>
        <Paper elevation={0} variant="outlined" className="rounded-2xl p-6 sm:p-8">
          {children}
        </Paper>
      </Box>
    </Box>
  )
}
