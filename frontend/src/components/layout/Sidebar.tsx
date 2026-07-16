import {
  Box,
  Divider,
  Drawer,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Tooltip,
  Typography,
} from '@mui/material'
import ShowChartRoundedIcon from '@mui/icons-material/ShowChartRounded'
import { NavLink } from 'react-router-dom'
import { navItems } from './navConfig'

export const SIDEBAR_WIDTH = 260

interface SidebarProps {
  mobileOpen: boolean
  onClose: () => void
}

export function Sidebar({ mobileOpen, onClose }: SidebarProps) {
  const content = (
    <Box className="flex h-full flex-col">
      <Toolbar className="gap-2 px-4">
        <Box className="flex h-8 w-8 items-center justify-center rounded-xl bg-blue-600 text-white">
          <ShowChartRoundedIcon fontSize="small" />
        </Box>
        <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
          TraderBot
        </Typography>
      </Toolbar>
      <Divider />
      <List className="flex-1 px-2 py-3">
        {navItems.map((item) => {
          const Icon = item.icon

          if (item.disabled || !item.path) {
            return (
              <Tooltip key={item.label} title="Coming soon" placement="right">
                <span>
                  <ListItemButton disabled className="rounded-lg">
                    <ListItemIcon>
                      <Icon fontSize="small" />
                    </ListItemIcon>
                    <ListItemText primary={item.label} />
                  </ListItemButton>
                </span>
              </Tooltip>
            )
          }

          return (
            <ListItemButton
              key={item.label}
              component={NavLink}
              to={item.path}
              onClick={onClose}
              className="rounded-lg"
              sx={{ '&.active': { bgcolor: 'action.selected', fontWeight: 600 } }}
            >
              <ListItemIcon>
                <Icon fontSize="small" />
              </ListItemIcon>
              <ListItemText primary={item.label} />
            </ListItemButton>
          )
        })}
      </List>
    </Box>
  )

  return (
    <Box component="nav" sx={{ width: { md: SIDEBAR_WIDTH }, flexShrink: { md: 0 } }}>
      <Drawer
        variant="temporary"
        open={mobileOpen}
        onClose={onClose}
        ModalProps={{ keepMounted: true }}
        sx={{
          display: { xs: 'block', md: 'none' },
          '& .MuiDrawer-paper': { width: SIDEBAR_WIDTH, boxSizing: 'border-box' },
        }}
      >
        {content}
      </Drawer>
      <Drawer
        variant="permanent"
        open
        sx={{
          display: { xs: 'none', md: 'block' },
          '& .MuiDrawer-paper': {
            width: SIDEBAR_WIDTH,
            boxSizing: 'border-box',
            borderRight: '1px solid',
            borderColor: 'divider',
          },
        }}
      >
        {content}
      </Drawer>
    </Box>
  )
}
