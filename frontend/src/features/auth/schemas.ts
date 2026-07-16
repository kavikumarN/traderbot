import { z } from 'zod'

export const loginSchema = z.object({
  email: z.email('Enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
})
export type LoginFormValues = z.infer<typeof loginSchema>

// Mirrors the backend's PlainPassword policy (10+ chars, a letter, a digit)
// so weak passwords are caught before the round trip, not after.
const passwordSchema = z
  .string()
  .min(10, 'Must be at least 10 characters')
  .regex(/[A-Za-z]/, 'Must contain at least one letter')
  .regex(/\d/, 'Must contain at least one digit')

export const registerSchema = z
  .object({
    firstName: z.string().trim().min(1, 'First name is required').max(100),
    lastName: z.string().trim().min(1, 'Last name is required').max(100),
    email: z.email('Enter a valid email address'),
    password: passwordSchema,
    confirmPassword: z.string().min(1, 'Please confirm your password'),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  })
export type RegisterFormValues = z.infer<typeof registerSchema>
