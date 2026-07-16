import { useEffect, useMemo, type ReactNode } from 'react'
import { CssBaseline, ThemeProvider } from '@mui/material'
import { useAppSelector } from '@/app/hooks'
import { buildTheme } from './muiTheme'
import { selectThemeMode } from './themeSlice'

/** Wraps the app in the MUI theme for the current mode and mirrors that
 * mode onto `<html class="dark">` so Tailwind's `dark:` variant (see
 * `index.css`'s `@custom-variant dark`) stays in lockstep with MUI. */
export function ThemeModeProvider({ children }: { children: ReactNode }) {
  const mode = useAppSelector(selectThemeMode)
  const theme = useMemo(() => buildTheme(mode), [mode])

  useEffect(() => {
    document.documentElement.classList.toggle('dark', mode === 'dark')
    document.documentElement.style.colorScheme = mode
  }, [mode])

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {children}
    </ThemeProvider>
  )
}
