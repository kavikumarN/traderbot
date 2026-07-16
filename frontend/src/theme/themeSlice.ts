import { createSlice, type PayloadAction } from '@reduxjs/toolkit'
import type { RootState } from '@/app/store'

export type ThemeMode = 'light' | 'dark'

const STORAGE_KEY = 'traderbot.theme.mode'

function getInitialMode(): ThemeMode {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'light' || stored === 'dark') return stored
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

interface ThemeState {
  mode: ThemeMode
}

const initialState: ThemeState = { mode: getInitialMode() }

const themeSlice = createSlice({
  name: 'theme',
  initialState,
  reducers: {
    modeToggled(state) {
      state.mode = state.mode === 'light' ? 'dark' : 'light'
      localStorage.setItem(STORAGE_KEY, state.mode)
    },
    modeSet(state, action: PayloadAction<ThemeMode>) {
      state.mode = action.payload
      localStorage.setItem(STORAGE_KEY, state.mode)
    },
  },
})

export const { modeToggled, modeSet } = themeSlice.actions
export default themeSlice.reducer

export const selectThemeMode = (state: RootState) => state.theme.mode
