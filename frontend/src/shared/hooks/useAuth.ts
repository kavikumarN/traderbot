import { useAppSelector } from '@/app/hooks'
import { selectAuthStatus, selectAuthUser, selectIsAuthenticated } from '@/features/auth/authSlice'

export function useAuth() {
  const user = useAppSelector(selectAuthUser)
  const status = useAppSelector(selectAuthStatus)
  const isAuthenticated = useAppSelector(selectIsAuthenticated)
  return { user, status, isAuthenticated }
}
