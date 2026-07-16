import type { ComponentType } from 'react'
import type { SvgIconProps } from '@mui/material'
import AccountBalanceWalletRoundedIcon from '@mui/icons-material/AccountBalanceWalletRounded'
import DashboardRoundedIcon from '@mui/icons-material/DashboardRounded'
import ReceiptLongRoundedIcon from '@mui/icons-material/ReceiptLongRounded'
import ScienceRoundedIcon from '@mui/icons-material/ScienceRounded'
import ShieldRoundedIcon from '@mui/icons-material/ShieldRounded'
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded'

export interface NavItem {
  label: string
  path?: string
  icon: ComponentType<SvgIconProps>
  /** No trading pages exist yet (Phase 2 is the foundation only) — these
   * are shown, disabled, so the sidebar reads as a real product shell
   * rather than empty, without linking anywhere that doesn't exist. */
  disabled?: boolean
}

export const navItems: NavItem[] = [
  { label: 'Dashboard', path: '/dashboard', icon: DashboardRoundedIcon },
  { label: 'Strategies', icon: TrendingUpRoundedIcon, disabled: true },
  { label: 'Orders', icon: ReceiptLongRoundedIcon, disabled: true },
  { label: 'Portfolio', path: '/portfolio', icon: AccountBalanceWalletRoundedIcon },
  { label: 'Backtesting', path: '/backtesting', icon: ScienceRoundedIcon },
  { label: 'Risk', icon: ShieldRoundedIcon, disabled: true },
]
