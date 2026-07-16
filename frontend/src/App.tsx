import { AppRouter } from '@/app/router'
import { FullPageLoader } from '@/components/feedback/FullPageLoader'
import { useGetMeQuery } from '@/features/auth/authApi'
import { useAuth } from '@/shared/hooks/useAuth'

function App() {
  const { isAuthenticated, user } = useAuth()
  // A stored token pair means "was signed in last session" but the profile
  // hasn't been fetched yet — hold the routed UI back one tick so
  // ProtectedRoute doesn't render a flash of "unauthenticated" first.
  const { isLoading } = useGetMeQuery(undefined, { skip: !isAuthenticated || !!user })

  if (isAuthenticated && !user && isLoading) {
    return <FullPageLoader label="Loading your workspace…" />
  }

  return <AppRouter />
}

export default App
