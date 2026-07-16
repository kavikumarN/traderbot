import { AuthLayout } from '@/components/layout/AuthLayout'
import { LoginForm } from '../components/LoginForm'

export default function LoginPage() {
  return (
    <AuthLayout title="Welcome back" subtitle="Sign in to your trading platform account">
      <LoginForm />
    </AuthLayout>
  )
}
