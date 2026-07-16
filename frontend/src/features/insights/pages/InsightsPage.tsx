import { useState } from 'react'
import { Box, Typography } from '@mui/material'
import { NewsFeedPanel } from '../components/NewsFeedPanel'
import { PatternViewer } from '../components/PatternViewer'
import { terminal, terminalFont } from '../terminal'

const TABS = ['pattern-viewer', 'news'] as const
type TabKey = (typeof TABS)[number]

const TAB_LABELS: Record<TabKey, string> = {
  'pattern-viewer': 'Pattern Viewer',
  news: 'News',
}

export default function InsightsPage() {
  const [tab, setTab] = useState<TabKey>('pattern-viewer')

  return (
    <Box
      sx={{
        bgcolor: terminal.bg,
        p: 2,
        borderRadius: '2px',
        border: `1px solid ${terminal.border}`,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', mb: 2 }}>
        <Typography
          sx={{
            fontFamily: terminalFont,
            fontSize: 18,
            fontWeight: 700,
            color: terminal.text,
            letterSpacing: '0.05em',
          }}
        >
          INSIGHTS TERMINAL
        </Typography>
        <Typography sx={{ fontFamily: terminalFont, fontSize: 11, color: terminal.textDim }}>
          {new Date().toUTCString()}
        </Typography>
      </Box>

      <Box sx={{ display: 'flex', gap: 0.5, mb: 2, borderBottom: `1px solid ${terminal.border}` }}>
        {TABS.map((key) => (
          <Box
            key={key}
            onClick={() => setTab(key)}
            sx={{
              cursor: 'pointer',
              px: 2,
              py: 1,
              fontFamily: terminalFont,
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              color: tab === key ? terminal.amber : terminal.textDim,
              borderBottom: tab === key ? `2px solid ${terminal.amber}` : '2px solid transparent',
            }}
          >
            {TAB_LABELS[key]}
          </Box>
        ))}
      </Box>

      {tab === 'pattern-viewer' ? <PatternViewer /> : null}
      {tab === 'news' ? <NewsFeedPanel /> : null}
    </Box>
  )
}
