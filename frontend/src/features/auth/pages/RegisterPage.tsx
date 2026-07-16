import { AuthLayout } from '@/components/layout/AuthLayout'
import { RegisterForm } from '../components/RegisterForm'

export default function RegisterPage() {
  return (
    <AuthLayout title="Create your account" subtitle="Start building and monitoring trading strategies">
      <RegisterForm />
    </AuthLayout>
  )
}
