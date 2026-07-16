import { useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Link as RouterLink, useLocation, useNavigate } from 'react-router-dom'
import { Alert, Box, Button, Link, Stack, TextField } from '@mui/material'
import { useLoginMutation } from '../authApi'
import { loginSchema, type LoginFormValues } from '../schemas'
import { getApiErrorMessage } from '@/shared/types/api'

interface LocationState {
  from?: string
}

export function LoginForm() {
  const navigate = useNavigate()
  const location = useLocation()
  const [login, { isLoading }] = useLoginMutation()
  const [formError, setFormError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  })

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null)
    try {
      await login(values).unwrap()
      const redirectTo = (location.state as LocationState | null)?.from ?? '/dashboard'
      navigate(redirectTo, { replace: true })
    } catch (error) {
      setFormError(getApiErrorMessage(error))
    }
  })

  return (
    <Box component="form" noValidate onSubmit={onSubmit}>
      <Stack spacing={2.5}>
        {formError ? <Alert severity="error">{formError}</Alert> : null}

        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          fullWidth
          error={!!errors.email}
          helperText={errors.email?.message}
          {...register('email')}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          fullWidth
          error={!!errors.password}
          helperText={errors.password?.message}
          {...register('password')}
        />
        <Button type="submit" variant="contained" size="large" fullWidth loading={isLoading}>
          Sign in
        </Button>
        <Box className="text-center text-sm text-gray-600 dark:text-gray-400">
          Don&apos;t have an account?{' '}
          <Link component={RouterLink} to="/register">
            Create one
          </Link>
        </Box>
      </Stack>
    </Box>
  )
}
