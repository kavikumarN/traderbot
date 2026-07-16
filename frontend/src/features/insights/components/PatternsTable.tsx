import { Box, Chip, Typography } from '@mui/material'
import { signalColor, terminal, terminalFont } from '../terminal'
import type { IntervalAnalysis } from '../types'

export function PatternsTable({ intervals }: { intervals: IntervalAnalysis[] }) {
  const rows = intervals.flatMap((interval) =>
    interval.patterns.map((pattern) => ({ interval: interval.interval, pattern }))
  )

  if (rows.length === 0) {
    return (
      <Typography sx={{ fontFamily: terminalFont, fontSize: 12, color: terminal.textDim }}>
        No patterns detected in the current window.
      </Typography>
    )
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, maxHeight: 360, overflowY: 'auto' }}>
      {rows.map(({ interval, pattern }, i) => (
        <Box
          key={`${interval}-${pattern.name}-${pattern.at}-${i}`}
          sx={{
            display: 'grid',
            gridTemplateColumns: '52px 1fr 90px 60px',
            alignItems: 'center',
            gap: 1,
            px: 1,
            py: 0.5,
            borderBottom: `1px solid ${terminal.border}`,
          }}
        >
          <Chip
            label={interval}
            size="small"
            sx={{
              height: 18,
              fontFamily: terminalFont,
              fontSize: 10,
              color: terminal.cyan,
              borderColor: terminal.cyan,
              bgcolor: 'transparent',
            }}
            variant="outlined"
          />
          <Box>
            <Typography sx={{ fontFamily: terminalFont, fontSize: 12, color: terminal.text }}>
              {pattern.name}
            </Typography>
            <Typography sx={{ fontFamily: terminalFont, fontSize: 10, color: terminal.textDim }}>
              {pattern.description}
            </Typography>
          </Box>
          <Typography
            sx={{ fontFamily: terminalFont, fontSize: 11, fontWeight: 700, color: signalColor(pattern.signal) }}
          >
            {pattern.signal}
          </Typography>
          <Typography sx={{ fontFamily: terminalFont, fontSize: 11, color: terminal.textDim, textAlign: 'right' }}>
            {(Number(pattern.confidence) * 100).toFixed(0)}%
          </Typography>
        </Box>
      ))}
    </Box>
  )
}
