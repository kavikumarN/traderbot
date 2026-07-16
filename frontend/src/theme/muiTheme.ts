import { createTheme, type Theme } from '@mui/material/styles'
import type { ThemeMode } from './themeSlice'

/** Signal blue + ticker amber — same accent pair as the platform's
 * architecture spec (Phase 0), carried through into the product UI. */
const brand = {
  blue: '#1852C4',
  blueDark: '#5B8DEF',
  amber: '#B45309',
  amberDark: '#F0B429',
}

const fontFamily = [
  '-apple-system',
  'BlinkMacSystemFont',
  '"Segoe UI"',
  'Roboto',
  'Helvetica',
  'Arial',
  'sans-serif',
].join(',')

export function buildTheme(mode: ThemeMode): Theme {
  const isDark = mode === 'dark'

  return createTheme({
    palette: {
      mode,
      primary: { main: isDark ? brand.blueDark : brand.blue },
      secondary: { main: isDark ? brand.amberDark : brand.amber },
      background: isDark
        ? { default: '#0B0F16', paper: '#12161F' }
        : { default: '#F5F6F8', paper: '#FFFFFF' },
    },
    shape: { borderRadius: 10 },
    typography: {
      fontFamily,
      button: { textTransform: 'none', fontWeight: 600 },
    },
    components: {
      MuiButton: {
        styleOverrides: {
          root: { borderRadius: 10 },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: { backgroundImage: 'none' },
        },
      },
      MuiAppBar: {
        styleOverrides: {
          root: { backgroundImage: 'none' },
        },
      },
    },
  })
}
