import { useState } from 'react'
import { Alert, Box, Chip, Typography } from '@mui/material'
import { getApiErrorMessage } from '@/shared/types/api'
import { useListNewsFeedsQuery, useListNewsQuery } from '../insightsApi'
import { impactColor, terminal, terminalFont } from '../terminal'
import { TerminalPanel } from './TerminalPanel'

const POLL_INTERVAL_MS = 60_000

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diffMs / 60_000)
  if (minutes < 1) return 'now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

export function NewsFeedPanel() {
  const [activeFeed, setActiveFeed] = useState<string | undefined>(undefined)

  const feedsQuery = useListNewsFeedsQuery()
  const newsQuery = useListNewsQuery({ feed: activeFeed }, { pollingInterval: POLL_INTERVAL_MS })

  const tabs = [{ id: undefined, name: 'ALL' }, ...(feedsQuery.data ?? []).map((f) => ({ id: f.id, name: f.name }))]

  return (
    <Box sx={{ bgcolor: terminal.bg, p: 2, borderRadius: '2px' }}>
      <Box sx={{ display: 'flex', gap: 0.5, mb: 2, flexWrap: 'wrap' }}>
        {tabs.map((tab) => {
          const selected = activeFeed === tab.id
          return (
            <Box
              key={tab.id ?? 'all'}
              onClick={() => setActiveFeed(tab.id)}
              sx={{
                cursor: 'pointer',
                px: 1.5,
                py: 0.5,
                fontFamily: terminalFont,
                fontSize: 11,
                fontWeight: selected ? 700 : 400,
                border: `1px solid ${selected ? terminal.amber : terminal.border}`,
                color: selected ? terminal.amber : terminal.textDim,
                textTransform: 'uppercase',
                userSelect: 'none',
              }}
            >
              {tab.name}
            </Box>
          )
        })}
      </Box>

      {newsQuery.isError ? (
        <Alert severity="error" sx={{ fontFamily: terminalFont }}>
          {getApiErrorMessage(newsQuery.error)}
        </Alert>
      ) : null}

      <TerminalPanel
        title={activeFeed ? tabs.find((t) => t.id === activeFeed)?.name ?? 'FEED' : 'ALL FEEDS'}
        right={
          <Typography sx={{ fontFamily: terminalFont, fontSize: 10, color: terminal.textDim }}>
            {newsQuery.isFetching ? 'REFRESHING…' : `${newsQuery.data?.length ?? 0} STORIES`}
          </Typography>
        }
      >
        <Box sx={{ display: 'flex', flexDirection: 'column', maxHeight: 620, overflowY: 'auto' }}>
          {(newsQuery.data ?? []).length === 0 && !newsQuery.isLoading ? (
            <Typography sx={{ fontFamily: terminalFont, fontSize: 12, color: terminal.textDim, py: 2 }}>
              No stories right now.
            </Typography>
          ) : null}

          {(newsQuery.data ?? []).map((article) => (
            <Box
              key={article.url}
              component="a"
              href={article.url}
              target="_blank"
              rel="noreferrer"
              sx={{
                display: 'block',
                textDecoration: 'none',
                borderBottom: `1px solid ${terminal.border}`,
                py: 1,
                px: 0.5,
                '&:hover': { bgcolor: terminal.panelAlt },
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.25 }}>
                <Box
                  sx={{
                    width: 6,
                    height: 6,
                    borderRadius: '50%',
                    bgcolor: impactColor(article.impact),
                    flexShrink: 0,
                  }}
                />
                <Typography sx={{ fontFamily: terminalFont, fontSize: 10, color: terminal.cyan }}>
                  {article.source_name}
                </Typography>
                <Typography sx={{ fontFamily: terminalFont, fontSize: 10, color: terminal.textDim }}>
                  {timeAgo(article.published_at)}
                </Typography>
                {article.symbols.map((symbol) => (
                  <Chip
                    key={symbol}
                    label={symbol}
                    size="small"
                    sx={{ height: 16, fontFamily: terminalFont, fontSize: 9, color: terminal.amber }}
                    variant="outlined"
                  />
                ))}
              </Box>
              <Typography sx={{ fontFamily: terminalFont, fontSize: 13, color: terminal.text, lineHeight: 1.4 }}>
                {article.title}
              </Typography>
            </Box>
          ))}
        </Box>
      </TerminalPanel>
    </Box>
  )
}
