import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Box, Button, Stack, Typography } from '@mui/material'

interface ErrorBoundaryProps {
  children: ReactNode
}

interface ErrorBoundaryState {
  error: Error | null
}

/** Catches render-time errors anywhere below it so one broken component
 * can't blank the entire app. Must be a class component — React only
 * supports `componentDidCatch` / `getDerivedStateFromError` that way. */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // A production deployment would forward this to an error-tracking service.
    console.error('Unhandled render error:', error, info.componentStack)
  }

  private handleReload = (): void => {
    window.location.reload()
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <Box className="flex min-h-screen items-center justify-center bg-gray-50 px-4 dark:bg-neutral-950">
          <Stack spacing={2} sx={{ alignItems: 'center' }} className="max-w-sm text-center">
            <Typography variant="h5" sx={{ fontWeight: 700 }}>
              Something went wrong
            </Typography>
            <Typography variant="body2" color="textSecondary">
              An unexpected error occurred. Try reloading the page — if it keeps happening, contact
              support.
            </Typography>
            <Button variant="contained" onClick={this.handleReload}>
              Reload page
            </Button>
          </Stack>
        </Box>
      )
    }
    return this.props.children
  }
}
