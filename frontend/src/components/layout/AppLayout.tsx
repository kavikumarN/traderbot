import { useState } from 'react'
import { Box, Toolbar } from '@mui/material'
import { Outlet } from 'react-router-dom'
import { Header } from './Header'
import { Sidebar, SIDEBAR_WIDTH } from './Sidebar'

/** The authenticated app shell: sidebar + header + routed content. Mounted
 * once by the router around every protected route (see `app/router.tsx`),
 * so page components only ever render their own content. */
export function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <Box className="flex min-h-screen bg-gray-50 dark:bg-neutral-950">
      <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
      <Header onMenuClick={() => setMobileOpen((prev) => !prev)} />
      <Box
        component="main"
        className="flex-1 px-4 py-8 sm:px-6 lg:px-8"
        sx={{ width: { md: `calc(100% - ${SIDEBAR_WIDTH}px)` } }}
      >
        <Toolbar />
        <Outlet />
      </Box>
    </Box>
  )
}
