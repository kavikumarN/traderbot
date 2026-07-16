import { Box, Typography } from '@mui/material'
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { terminal, terminalFont } from '../terminal'
import type { Candle, PatternMatch } from '../types'

interface ChartDatum {
  time: string
  open: number
  high: number
  low: number
  close: number
  range: [number, number]
}

interface CandlestickChartProps {
  candles: Candle[]
  patterns: PatternMatch[]
}

function CandleShape(props: {
  x?: number
  y?: number
  width?: number
  height?: number
  payload?: ChartDatum
}) {
  const { x = 0, y = 0, width = 0, height = 0, payload } = props
  if (!payload || height <= 0) return null

  const { open, close, high, low } = payload
  const range = high - low
  if (range <= 0) return null

  const bullish = close >= open
  const color = bullish ? terminal.green : terminal.red
  const bodyTop = y + ((high - Math.max(open, close)) / range) * height
  const bodyBottom = y + ((high - Math.min(open, close)) / range) * height
  const bodyHeight = Math.max(1, bodyBottom - bodyTop)
  const wickX = x + width / 2
  const bodyWidth = Math.max(2, width * 0.6)
  const bodyX = x + (width - bodyWidth) / 2

  return (
    <g>
      <line x1={wickX} x2={wickX} y1={y} y2={y + height} stroke={color} strokeWidth={1} />
      <rect x={bodyX} y={bodyTop} width={bodyWidth} height={bodyHeight} fill={color} />
    </g>
  )
}

export function CandlestickChart({ candles, patterns }: CandlestickChartProps) {
  if (candles.length === 0) {
    return (
      <Box sx={{ py: 6, textAlign: 'center' }}>
        <Typography sx={{ fontFamily: terminalFont, fontSize: 12, color: terminal.textDim }}>
          NO CANDLE DATA
        </Typography>
      </Box>
    )
  }

  const data: ChartDatum[] = candles.map((c) => ({
    time: new Date(c.open_time).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }),
    open: Number(c.open),
    high: Number(c.high),
    low: Number(c.low),
    close: Number(c.close),
    range: [Number(c.low), Number(c.high)],
  }))

  // Pattern markers snap to the nearest candle by timestamp, plotted just
  // above that candle's high (bullish/neutral) or below its low (bearish).
  const markers = patterns
    .map((pattern) => {
      const patternTime = new Date(pattern.at).getTime()
      let closestIndex = 0
      let closestDiff = Infinity
      candles.forEach((c, i) => {
        const diff = Math.abs(new Date(c.open_time).getTime() - patternTime)
        if (diff < closestDiff) {
          closestDiff = diff
          closestIndex = i
        }
      })
      const candle = candles[closestIndex]
      const spread = Number(candle.high) - Number(candle.low) || Number(candle.high) * 0.001
      const y =
        pattern.signal === 'BEARISH'
          ? Number(candle.low) - spread * 0.6
          : Number(candle.high) + spread * 0.6
      return { time: data[closestIndex].time, y, pattern }
    })
    .filter((m, i, arr) => arr.findIndex((other) => other.time === m.time && other.pattern.name === m.pattern.name) === i)

  const markerColor = (signal: string) =>
    signal === 'BULLISH' ? terminal.green : signal === 'BEARISH' ? terminal.red : terminal.cyan

  return (
    <Box sx={{ width: '100%', height: 420 }}>
      <ResponsiveContainer>
        <ComposedChart data={data} margin={{ top: 16, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="2 4" stroke={terminal.border} vertical={false} />
          <XAxis
            dataKey="time"
            tick={{ fontSize: 10, fill: terminal.textDim, fontFamily: terminalFont }}
            tickLine={false}
            axisLine={{ stroke: terminal.border }}
            minTickGap={40}
          />
          <YAxis
            domain={['auto', 'auto']}
            tick={{ fontSize: 10, fill: terminal.textDim, fontFamily: terminalFont }}
            tickLine={false}
            axisLine={false}
            width={70}
          />
          <Tooltip
            contentStyle={{
              background: terminal.panelAlt,
              border: `1px solid ${terminal.border}`,
              fontFamily: terminalFont,
              fontSize: 11,
              color: terminal.text,
            }}
            labelStyle={{ color: terminal.amber }}
            formatter={(value: unknown, name: string) => {
              if (name === 'range' && Array.isArray(value)) return [`${value[0]} - ${value[1]}`, 'Range']
              return [String(value), name]
            }}
          />
          <Bar dataKey="range" shape={CandleShape} isAnimationActive={false} />
          <Scatter
            data={markers.map((m) => ({ time: m.time, marker: m.y }))}
            dataKey="marker"
            shape={(props: { cx?: number; cy?: number; payload?: { time: string } }) => {
              const marker = markers.find((m) => m.time === props.payload?.time)
              const color = marker ? markerColor(marker.pattern.signal) : terminal.cyan
              return <circle cx={props.cx} cy={props.cy} r={3} fill={color} stroke={terminal.bg} strokeWidth={1} />
            }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </Box>
  )
}
