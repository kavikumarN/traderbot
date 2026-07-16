import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '@/shared/hooks/useAuth'

interface GuestRouteProps {
  children: ReactNode
}

/** Keeps signed-in users off /login and /register — landing there while
 * already authenticated just bounces straight to the dashboard. */
export function GuestRoute({ children }: GuestRouteProps) {
  const { isAuthenticated } = useAuth()

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }

  return children
}
