import { Box, Button, Typography } from '@mui/material'
import { signalColor, terminal, terminalFont } from '../terminal'
import type { StrategySuggestion } from '../types'

const BUCKET_SIGNAL: Record<string, string> = {
  TREND: 'BULLISH',
  REVERSAL: 'NEUTRAL',
  RANGE: 'NEUTRAL',
  BREAKOUT: 'BULLISH',
}

interface SuggestionPanelProps {
  suggestion: StrategySuggestion
  onApply?: () => void
}

export function SuggestionPanel({ suggestion, onApply }: SuggestionPanelProps) {
  const confidencePct = (Number(suggestion.confidence) * 100).toFixed(0)

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      <Box sx={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <Typography
          sx={{
            fontFamily: terminalFont,
            fontSize: 20,
            fontWeight: 700,
            color: signalColor(BUCKET_SIGNAL[suggestion.bucket] ?? 'NEUTRAL'),
            letterSpacing: '0.03em',
          }}
        >
          {suggestion.strategy_type.replace(/_/g, ' ')}
        </Typography>
        <Typography sx={{ fontFamily: terminalFont, fontSize: 12, color: terminal.amber }}>
          {confidencePct}% CONF
        </Typography>
      </Box>

      <Typography sx={{ fontFamily: terminalFont, fontSize: 11, color: terminal.textDim, lineHeight: 1.5 }}>
        {suggestion.rationale}
      </Typography>

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))',
          gap: 1,
          mt: 0.5,
        }}
      >
        {Object.entries(suggestion.parameters).map(([key, value]) => (
          <Box key={key} sx={{ border: `1px solid ${terminal.border}`, px: 1, py: 0.5 }}>
            <Typography sx={{ fontFamily: terminalFont, fontSize: 9, color: terminal.textDim, textTransform: 'uppercase' }}>
              {key.replace(/_/g, ' ')}
            </Typography>
            <Typography sx={{ fontFamily: terminalFont, fontSize: 13, color: terminal.text }}>
              {String(value)}
            </Typography>
          </Box>
        ))}
      </Box>

      {onApply ? (
        <Button
          onClick={onApply}
          size="small"
          sx={{
            mt: 1,
            fontFamily: terminalFont,
            fontSize: 11,
            color: terminal.bg,
            bgcolor: terminal.amber,
            '&:hover': { bgcolor: terminal.amber, opacity: 0.85 },
            alignSelf: 'flex-start',
          }}
        >
          Apply to Register a Strategy
        </Button>
      ) : null}
    </Box>
  )
}
