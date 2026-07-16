import { useState } from 'react'
import { Box, Button, TextField } from '@mui/material'
import { terminal, terminalFont } from '../terminal'

const AVAILABLE_INTERVALS = ['5m', '15m', '1h', '4h', '1d'] as const

interface AnalyzeFormProps {
  symbol: string
  onSymbolChange: (symbol: string) => void
  intervals: string[]
  onIntervalsChange: (intervals: string[]) => void
  onAnalyze: () => void
  isLoading: boolean
}

export function AnalyzeForm({
  symbol,
  onSymbolChange,
  intervals,
  onIntervalsChange,
  onAnalyze,
  isLoading,
}: AnalyzeFormProps) {
  const [localSymbol, setLocalSymbol] = useState(symbol)

  function toggleInterval(interval: string) {
    if (intervals.includes(interval)) {
      onIntervalsChange(intervals.filter((i) => i !== interval))
    } else if (intervals.length < 5) {
      onIntervalsChange([...intervals, interval])
    }
  }

  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 1.5 }}>
      <TextField
        size="small"
        value={localSymbol}
        onChange={(e) => setLocalSymbol(e.target.value.toUpperCase())}
        onBlur={() => onSymbolChange(localSymbol)}
        sx={{
          width: 140,
          '& .MuiInputBase-input': { fontFamily: terminalFont, fontSize: 13, color: terminal.text, py: 0.75 },
          '& .MuiOutlinedInput-notchedOutline': { borderColor: terminal.border },
        }}
      />

      <Box sx={{ display: 'flex', gap: 0.5 }}>
        {AVAILABLE_INTERVALS.map((interval) => {
          const selected = intervals.includes(interval)
          return (
            <Box
              key={interval}
              onClick={() => toggleInterval(interval)}
              sx={{
                cursor: 'pointer',
                px: 1,
                py: 0.5,
                fontFamily: terminalFont,
                fontSize: 11,
                border: `1px solid ${selected ? terminal.amber : terminal.border}`,
                color: selected ? terminal.amber : terminal.textDim,
                userSelect: 'none',
              }}
            >
              {interval}
            </Box>
          )
        })}
      </Box>

      <Button
        onClick={() => {
          onSymbolChange(localSymbol)
          onAnalyze()
        }}
        disabled={isLoading || intervals.length === 0}
        size="small"
        sx={{
          fontFamily: terminalFont,
          fontSize: 11,
          color: terminal.bg,
          bgcolor: terminal.green,
          '&:hover': { bgcolor: terminal.green, opacity: 0.85 },
          '&.Mui-disabled': { bgcolor: terminal.border, color: terminal.textDim },
        }}
      >
        {isLoading ? 'ANALYZING…' : 'ANALYZE'}
      </Button>
    </Box>
  )
}
