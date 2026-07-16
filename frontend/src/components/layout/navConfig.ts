import type { ComponentType } from 'react'
import type { SvgIconProps } from '@mui/material'
import AccountBalanceWalletRoundedIcon from '@mui/icons-material/AccountBalanceWalletRounded'
import DashboardRoundedIcon from '@mui/icons-material/DashboardRounded'
import InsightsRoundedIcon from '@mui/icons-material/InsightsRounded'
import ReceiptLongRoundedIcon from '@mui/icons-material/ReceiptLongRounded'
import ScienceRoundedIcon from '@mui/icons-material/ScienceRounded'
import ShieldRoundedIcon from '@mui/icons-material/ShieldRounded'
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded'

export interface NavItem {
  label: string
  path?: string
  icon: ComponentType<SvgIconProps>
  /** Set when a page genuinely doesn't exist yet — shown, disabled, so the
   * sidebar reads as a real product shell rather than empty, without
   * linking anywhere that doesn't exist. */
  disabled?: boolean
}

export const navItems: NavItem[] = [
  { label: 'Dashboard', path: '/dashboard', icon: DashboardRoundedIcon },
  { label: 'Strategies', path: '/strategies', icon: TrendingUpRoundedIcon },
  { label: 'Orders', path: '/orders', icon: ReceiptLongRoundedIcon },
  { label: 'Portfolio', path: '/portfolio', icon: AccountBalanceWalletRoundedIcon },
  { label: 'Backtesting', path: '/backtesting', icon: ScienceRoundedIcon },
  { label: 'Risk', path: '/risk', icon: ShieldRoundedIcon },
  { label: 'Insights', path: '/insights', icon: InsightsRoundedIcon },
]
