import type { ReactNode } from 'react'
import { Box, Typography } from '@mui/material'
import { terminal, terminalFont } from '../terminal'

interface TerminalPanelProps {
  title: string
  right?: ReactNode
  children: ReactNode
}

export function TerminalPanel({ title, right, children }: TerminalPanelProps) {
  return (
    <Box
      sx={{
        bgcolor: terminal.panel,
        border: `1px solid ${terminal.border}`,
        borderRadius: '2px',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 1.5,
          py: 0.75,
          borderBottom: `1px solid ${terminal.border}`,
          bgcolor: terminal.panelAlt,
        }}
      >
        <Typography
          sx={{
            fontFamily: terminalFont,
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: '0.08em',
            color: terminal.amber,
            textTransform: 'uppercase',
          }}
        >
          {title}
        </Typography>
        {right}
      </Box>
      <Box sx={{ p: 1.5 }}>{children}</Box>
    </Box>
  )
}
