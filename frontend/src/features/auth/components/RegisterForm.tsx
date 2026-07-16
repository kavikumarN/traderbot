import { useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import { Alert, Box, Button, Link, Stack, TextField } from '@mui/material'
import { useLoginMutation, useRegisterMutation } from '../authApi'
import { registerSchema, type RegisterFormValues } from '../schemas'
import { useAppDispatch } from '@/app/hooks'
import { notifySuccess } from '@/notifications/notificationsSlice'
import { getApiErrorMessage } from '@/shared/types/api'

export function RegisterForm() {
  const navigate = useNavigate()
  const dispatch = useAppDispatch()
  const [registerUser, { isLoading: isRegistering }] = useRegisterMutation()
  const [login, { isLoading: isLoggingIn }] = useLoginMutation()
  const [formError, setFormError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { firstName: '', lastName: '', email: '', password: '', confirmPassword: '' },
  })

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null)
    try {
      await registerUser({
        email: values.email,
        password: values.password,
        first_name: values.firstName,
        last_name: values.lastName,
      }).unwrap()
      // Registration returns only the new id/email, no tokens — sign the
      // user straight in so they land on the dashboard already authenticated.
      await login({ email: values.email, password: values.password }).unwrap()
      dispatch(notifySuccess('Welcome! Your account has been created.'))
      navigate('/dashboard', { replace: true })
    } catch (error) {
      setFormError(getApiErrorMessage(error))
    }
  })

  const isLoading = isRegistering || isLoggingIn

  return (
    <Box component="form" noValidate onSubmit={onSubmit}>
      <Stack spacing={2.5}>
        {formError ? <Alert severity="error">{formError}</Alert> : null}

        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
          <TextField
            label="First name"
            fullWidth
            error={!!errors.firstName}
            helperText={errors.firstName?.message}
            {...register('firstName')}
          />
          <TextField
            label="Last name"
            fullWidth
            error={!!errors.lastName}
            helperText={errors.lastName?.message}
            {...register('lastName')}
          />
        </Stack>
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
          autoComplete="new-password"
          fullWidth
          error={!!errors.password}
          helperText={errors.password?.message ?? 'At least 10 characters, with a letter and a digit'}
          {...register('password')}
        />
        <TextField
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          fullWidth
          error={!!errors.confirmPassword}
          helperText={errors.confirmPassword?.message}
          {...register('confirmPassword')}
        />
        <Button type="submit" variant="contained" size="large" fullWidth loading={isLoading}>
          Create account
        </Button>
        <Box className="text-center text-sm text-gray-600 dark:text-gray-400">
          Already have an account?{' '}
          <Link component={RouterLink} to="/login">
            Sign in
          </Link>
        </Box>
      </Stack>
    </Box>
  )
}
