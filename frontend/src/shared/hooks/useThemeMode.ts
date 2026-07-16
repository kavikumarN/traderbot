import { useAppDispatch, useAppSelector } from '@/app/hooks'
import { modeToggled, selectThemeMode } from '@/theme/themeSlice'

export function useThemeMode() {
  const dispatch = useAppDispatch()
  const mode = useAppSelector(selectThemeMode)
  const toggle = () => dispatch(modeToggled())
  return { mode, toggle }
}
