import { useState } from 'react'
import {
  AppBar,
  Avatar,
  Box,
  Divider,
  IconButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Toolbar,
  Tooltip,
  Typography,
} from '@mui/material'
import DarkModeRoundedIcon from '@mui/icons-material/DarkModeRounded'
import LightModeRoundedIcon from '@mui/icons-material/LightModeRounded'
import LogoutRoundedIcon from '@mui/icons-material/LogoutRounded'
import MenuRoundedIcon from '@mui/icons-material/MenuRounded'
import { useLocation } from 'react-router-dom'
import { useLogoutMutation } from '@/features/auth/authApi'
import { useAuth } from '@/shared/hooks/useAuth'
import { useThemeMode } from '@/shared/hooks/useThemeMode'
import { navItems } from './navConfig'
import { SIDEBAR_WIDTH } from './Sidebar'

interface HeaderProps {
  onMenuClick: () => void
}

export function Header({ onMenuClick }: HeaderProps) {
  const { user } = useAuth()
  const { mode, toggle } = useThemeMode()
  const [logout] = useLogoutMutation()
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null)
  const location = useLocation()

  const activeLabel =
    navItems.find((item) => item.path && location.pathname.startsWith(item.path))?.label ?? 'Dashboard'

  const initials = user ? `${user.first_name[0] ?? ''}${user.last_name[0] ?? ''}`.toUpperCase() : ''

  const handleLogout = async (): Promise<void> => {
    setAnchorEl(null)
    await logout()
  }

  return (
    <AppBar
      position="fixed"
      color="inherit"
      elevation={0}
      className="border-b border-gray-200 dark:border-white/10"
      sx={{ width: { md: `calc(100% - ${SIDEBAR_WIDTH}px)` }, ml: { md: `${SIDEBAR_WIDTH}px` } }}
    >
      <Toolbar className="gap-2">
        <IconButton edge="start" onClick={onMenuClick} className="md:hidden" aria-label="Open navigation">
          <MenuRoundedIcon />
        </IconButton>

        <Typography variant="subtitle1" sx={{ fontWeight: 600 }} className="flex-1">
          {activeLabel}
        </Typography>

        <Tooltip title={mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}>
          <IconButton onClick={toggle} aria-label="Toggle dark mode">
            {mode === 'dark' ? <LightModeRoundedIcon /> : <DarkModeRoundedIcon />}
          </IconButton>
        </Tooltip>

        <Tooltip title="Account">
          <IconButton
            onClick={(event) => setAnchorEl(event.currentTarget)}
            aria-label="Account menu"
            size="small"
            className="ml-1"
          >
            <Avatar sx={{ width: 32, height: 32, fontSize: 14 }} className="bg-blue-600">
              {initials || '?'}
            </Avatar>
          </IconButton>
        </Tooltip>
        <Menu anchorEl={anchorEl} open={!!anchorEl} onClose={() => setAnchorEl(null)}>
          <Box className="px-4 py-2">
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              {user ? `${user.first_name} ${user.last_name}` : ''}
            </Typography>
            <Typography variant="caption" color="textSecondary">
              {user?.email}
            </Typography>
          </Box>
          <Divider />
          <MenuItem onClick={handleLogout}>
            <ListItemIcon>
              <LogoutRoundedIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>Sign out</ListItemText>
          </MenuItem>
        </Menu>
      </Toolbar>
    </AppBar>
  )
}
