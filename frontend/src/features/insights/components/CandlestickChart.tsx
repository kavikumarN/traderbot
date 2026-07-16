import { useCallback, useEffect, useRef, useState } from 'react'
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

const priceFormatter = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })

const MIN_VISIBLE_CANDLES = 15
const PAN_FRACTION = 0.5
// Matches the <YAxis width={70}> and ComposedChart margin.right={16} below —
// used to convert a pointer/touch clientX into a fraction across the plot
// area (excluding the price-axis gutter) so zoom anchors on the data point
// under the cursor/fingers rather than always on the window's center.
const PLOT_LEFT_INSET = 70
const PLOT_RIGHT_INSET = 16
const WHEEL_ZOOM_SENSITIVITY = 0.0015
const PINCH_ZOOM_CLAMP: [number, number] = [0.5, 2]

interface ChartDatum {
  time: string
  open: number
  high: number
  low: number
  close: number
  range: [number, number]
  volume: number
}

interface MarkerGroup {
  time: string
  y: number
  signal: PatternMatch['signal']
  patterns: PatternMatch[]
}

interface CandlestickChartProps {
  candles: Candle[]
  patterns: PatternMatch[]
}

interface ShapeProps {
  x?: number
  y?: number
  width?: number
  height?: number
  payload?: ChartDatum
}

interface ViewWindow {
  size: number
  start: number
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: Array<{ payload?: ChartDatum }>
  label?: string
}) {
  if (!active || !payload || payload.length === 0) return null
  const datum = payload.find((p) => p.payload && typeof p.payload.open === 'number')?.payload
  if (!datum) return null

  const rows: [string, number][] = [
    ['O', datum.open],
    ['H', datum.high],
    ['L', datum.low],
    ['C', datum.close],
  ]

  return (
    <Box
      sx={{
        bgcolor: terminal.panelAlt,
        border: `1px solid ${terminal.border}`,
        fontFamily: terminalFont,
        fontSize: 11,
        color: terminal.text,
        p: 1,
        minWidth: 140,
      }}
    >
      <Typography sx={{ fontFamily: terminalFont, fontSize: 11, color: terminal.amber, mb: 0.5 }}>
        {label}
      </Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'auto 1fr', columnGap: 1.5, rowGap: 0.25 }}>
        {rows.map(([key, value]) => (
          <Box key={key} sx={{ display: 'contents' }}>
            <Typography sx={{ fontFamily: terminalFont, fontSize: 11, color: terminal.textDim }}>{key}</Typography>
            <Typography sx={{ fontFamily: terminalFont, fontSize: 11, color: terminal.text, textAlign: 'right' }}>
              {priceFormatter.format(value)}
            </Typography>
          </Box>
        ))}
      </Box>
    </Box>
  )
}

// Recharts' `shape` prop typing varies across chart types and doesn't
// export a single reusable "custom shape" interface, so these render
// functions take loosely-typed props (the well-known pragmatic pattern for
// Recharts custom shapes) rather than fighting its generics.
function CandleShape(props: ShapeProps) {
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

function VolumeShape(props: ShapeProps) {
  const { x = 0, y = 0, width = 0, height = 0, payload } = props
  if (!payload || height <= 0) return null

  const bullish = payload.close >= payload.open
  const color = bullish ? terminal.green : terminal.red
  const barWidth = Math.max(1, width * 0.6)
  const barX = x + (width - barWidth) / 2

  return <rect x={barX} y={y} width={barWidth} height={height} fill={color} opacity={0.35} />
}

const LEGEND_ITEMS: Array<{ label: string; color: string }> = [
  { label: 'Bullish', color: terminal.green },
  { label: 'Bearish', color: terminal.red },
  { label: 'Neutral', color: terminal.cyan },
]

function ZoomButton({
  label,
  onClick,
  disabled,
}: {
  label: string
  onClick: () => void
  disabled: boolean
}) {
  return (
    <Box
      component="button"
      onClick={onClick}
      disabled={disabled}
      sx={{
        cursor: disabled ? 'default' : 'pointer',
        px: 1,
        py: 0.25,
        minWidth: 24,
        lineHeight: 1.4,
        borderRadius: 0,
        outline: 'none',
        fontFamily: terminalFont,
        fontSize: 12,
        fontWeight: 700,
        bgcolor: 'transparent',
        border: `1px solid ${disabled ? terminal.border : terminal.borderStrong}`,
        color: disabled ? terminal.textDim : terminal.text,
        opacity: disabled ? 0.4 : 1,
        '&:hover': disabled ? {} : { borderColor: terminal.amber, color: terminal.amber },
      }}
    >
      {label}
    </Box>
  )
}

export function CandlestickChart({ candles, patterns }: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [view, setView] = useState<ViewWindow>({ size: candles.length || 1, start: 0 })

  // A fresh candle set (new symbol/interval/re-analyze) always opens fully
  // zoomed out — a stale zoom window from the previous chart would otherwise
  // silently slice the new data at the wrong offset.
  useEffect(() => {
    setView({ size: candles.length || 1, start: 0 })
  }, [candles])

  // Zooms so that whatever data point sits at `anchorFraction` (0 = left
  // edge of the plot area, 1 = right edge) stays under the cursor/fingers
  // after the zoom — the same "zoom toward the pointer" feel as any native
  // map/chart pinch gesture. `factor` > 1 zooms in, < 1 zooms out. Reads
  // `candles.length` fresh via the closure rather than a captured render
  // value, so wheel/touch listeners attached once per `candles` change never
  // zoom against stale bounds.
  const zoomAt = useCallback(
    (anchorFraction: number, factor: number) => {
      setView((prev) => {
        const total = candles.length
        const minSize = Math.min(MIN_VISIBLE_CANDLES, total)
        const prevSize = clamp(prev.size, minSize, total)
        const prevStart = clamp(prev.start, 0, total - prevSize)
        const newSize = clamp(Math.round(prevSize / factor), minSize, total)
        const anchorIndex = prevStart + anchorFraction * prevSize
        const newStart = clamp(Math.round(anchorIndex - anchorFraction * newSize), 0, total - newSize)
        return { size: newSize, start: newStart }
      })
    },
    [candles]
  )

  // Pinch-to-zoom: trackpad pinch arrives as a `wheel` event with
  // `ctrlKey: true` (the standard signal browsers use so apps can tell a
  // pinch gesture apart from ordinary scrolling — plain wheel scroll is left
  // alone here so it doesn't hijack page scrolling). Real touchscreen pinch
  // is handled via two-finger `touchmove` distance. `touch-action: none` on
  // the container (below) stops the browser's own native pinch-zoom/pan
  // from fighting these handlers.
  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    function fractionFromClientX(clientX: number): number {
      const rect = el!.getBoundingClientRect()
      const plotLeft = rect.left + PLOT_LEFT_INSET
      const plotWidth = Math.max(1, rect.width - PLOT_LEFT_INSET - PLOT_RIGHT_INSET)
      return clamp((clientX - plotLeft) / plotWidth, 0, 1)
    }

    function handleWheel(event: WheelEvent) {
      if (!event.ctrlKey) return
      event.preventDefault()
      const factor = clamp(Math.exp(-event.deltaY * WHEEL_ZOOM_SENSITIVITY), ...PINCH_ZOOM_CLAMP)
      zoomAt(fractionFromClientX(event.clientX), factor)
    }

    let pinchDistance: number | null = null
    let pinchAnchor = 0.5

    function touchDistance(touches: TouchList): number {
      return Math.hypot(touches[0].clientX - touches[1].clientX, touches[0].clientY - touches[1].clientY)
    }

    function handleTouchStart(event: TouchEvent) {
      if (event.touches.length !== 2) return
      pinchDistance = touchDistance(event.touches)
      pinchAnchor = fractionFromClientX((event.touches[0].clientX + event.touches[1].clientX) / 2)
    }

    function handleTouchMove(event: TouchEvent) {
      if (event.touches.length !== 2 || pinchDistance == null) return
      event.preventDefault()
      const distance = touchDistance(event.touches)
      zoomAt(pinchAnchor, clamp(distance / pinchDistance, ...PINCH_ZOOM_CLAMP))
      pinchDistance = distance
    }

    function handleTouchEnd(event: TouchEvent) {
      if (event.touches.length < 2) pinchDistance = null
    }

    el.addEventListener('wheel', handleWheel, { passive: false })
    el.addEventListener('touchstart', handleTouchStart, { passive: true })
    el.addEventListener('touchmove', handleTouchMove, { passive: false })
    el.addEventListener('touchend', handleTouchEnd, { passive: true })
    el.addEventListener('touchcancel', handleTouchEnd, { passive: true })

    return () => {
      el.removeEventListener('wheel', handleWheel)
      el.removeEventListener('touchstart', handleTouchStart)
      el.removeEventListener('touchmove', handleTouchMove)
      el.removeEventListener('touchend', handleTouchEnd)
      el.removeEventListener('touchcancel', handleTouchEnd)
    }
  }, [zoomAt])

  if (candles.length === 0) {
    return (
      <Box sx={{ py: 6, textAlign: 'center' }}>
        <Typography sx={{ fontFamily: terminalFont, fontSize: 12, color: terminal.textDim }}>
          NO CANDLE DATA
        </Typography>
      </Box>
    )
  }

  const clampedSize = clamp(view.size, Math.min(MIN_VISIBLE_CANDLES, candles.length), candles.length)
  const clampedStart = clamp(view.start, 0, candles.length - clampedSize)
  const visibleCandles = candles.slice(clampedStart, clampedStart + clampedSize)

  const canPanLeft = clampedStart > 0
  const canPanRight = clampedStart + clampedSize < candles.length

  function resetZoom() {
    setView({ size: candles.length, start: 0 })
  }

  function panLeft() {
    setView((prev) => ({
      ...prev,
      start: clamp(clampedStart - Math.round(clampedSize * PAN_FRACTION), 0, candles.length - clampedSize),
    }))
  }

  function panRight() {
    setView((prev) => ({
      ...prev,
      start: clamp(clampedStart + Math.round(clampedSize * PAN_FRACTION), 0, candles.length - clampedSize),
    }))
  }

  const data: ChartDatum[] = visibleCandles.map((c) => ({
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
    volume: Number(c.volume),
  }))

  const last = data.at(-1)!
  const first = data[0]
  const change = last.close - first.open
  const changePct = first.open !== 0 ? (change / first.open) * 100 : 0
  const rangeHigh = Math.max(...data.map((d) => d.high))
  const rangeLow = Math.min(...data.map((d) => d.low))
  const changeColor = change >= 0 ? terminal.green : terminal.red
  const maxVolume = Math.max(...data.map((d) => d.volume), 1)

  // Pattern markers snap to the nearest candle by timestamp (matched against
  // the *full* candle set, so zooming doesn't shift which candle a pattern
  // belongs to), then dropped if that candle falls outside the visible
  // window. Multiple patterns landing on the same candle are grouped into
  // one marker (with a count badge and a native hover title listing each)
  // so they don't render as an illegible overlapping blob.
  const groupsByIndex = new Map<number, MarkerGroup>()
  for (const pattern of patterns) {
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

    if (closestIndex < clampedStart || closestIndex >= clampedStart + clampedSize) continue
    const visibleIndex = closestIndex - clampedStart

    const candle = candles[closestIndex]
    const spread = Number(candle.high) - Number(candle.low) || Number(candle.high) * 0.001
    const existing = groupsByIndex.get(visibleIndex)
    if (existing) {
      existing.patterns.push(pattern)
      if (pattern.signal !== existing.signal && pattern.signal !== 'NEUTRAL') {
        existing.signal = pattern.signal
      }
      continue
    }

    const y =
      pattern.signal === 'BEARISH' ? Number(candle.low) - spread * 0.6 : Number(candle.high) + spread * 0.6
    groupsByIndex.set(visibleIndex, {
      time: data[visibleIndex].time,
      y,
      signal: pattern.signal,
      patterns: [pattern],
    })
  }
  const markers = Array.from(groupsByIndex.values())

  const markerColor = (signal: string) =>
    signal === 'BULLISH' ? terminal.green : signal === 'BEARISH' ? terminal.red : terminal.cyan

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1, mb: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 2, flexWrap: 'wrap' }}>
          <Typography sx={{ fontFamily: terminalFont, fontSize: 20, fontWeight: 700, color: terminal.text }}>
            {priceFormatter.format(last.close)}
          </Typography>
          <Typography sx={{ fontFamily: terminalFont, fontSize: 12, fontWeight: 700, color: changeColor }}>
            {change >= 0 ? '+' : ''}
            {priceFormatter.format(change)} ({change >= 0 ? '+' : ''}
            {changePct.toFixed(2)}%)
          </Typography>
          <Typography sx={{ fontFamily: terminalFont, fontSize: 11, color: terminal.textDim }}>
            H {priceFormatter.format(rangeHigh)} · L {priceFormatter.format(rangeLow)}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Box sx={{ display: 'flex', gap: 1.5 }}>
            {LEGEND_ITEMS.map((item) => (
              <Box key={item.label} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: item.color }} />
                <Typography sx={{ fontFamily: terminalFont, fontSize: 10, color: terminal.textDim }}>
                  {item.label}
                </Typography>
              </Box>
            ))}
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Typography sx={{ fontFamily: terminalFont, fontSize: 10, color: terminal.textDim, mr: 0.5 }}>
              PINCH TO ZOOM
            </Typography>
            <ZoomButton label="◀" onClick={panLeft} disabled={!canPanLeft} />
            <ZoomButton label="▶" onClick={panRight} disabled={!canPanRight} />
            <ZoomButton label="FIT" onClick={resetZoom} disabled={clampedSize === candles.length} />
            <Typography sx={{ fontFamily: terminalFont, fontSize: 10, color: terminal.textDim, ml: 0.5 }}>
              {clampedSize}/{candles.length}
            </Typography>
          </Box>
        </Box>
      </Box>

      <Box ref={containerRef} sx={{ width: '100%', height: 540, touchAction: 'none' }}>
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
            tickFormatter={(value: number) => priceFormatter.format(value)}
          />
          <YAxis yAxisId="volume" domain={[0, maxVolume * 4]} hide />
          <Tooltip content={<ChartTooltip />} cursor={{ stroke: terminal.borderStrong, strokeDasharray: '2 4' }} />
          <Bar yAxisId="volume" dataKey="volume" shape={VolumeShape} isAnimationActive={false} />
          <Bar dataKey="range" shape={CandleShape} isAnimationActive={false} />
          <Scatter
            data={markers.map((m) => ({ time: m.time, marker: m.y }))}
            dataKey="marker"
            isAnimationActive={false}
            shape={(props: { cx?: number; cy?: number; payload?: { time: string } }) => {
              const marker = markers.find((m) => m.time === props.payload?.time)
              if (!marker || props.cx == null || props.cy == null) return <g />
              const color = markerColor(marker.signal)
              const title = marker.patterns
                .map((p) => `${p.name} (${p.signal}, ${(Number(p.confidence) * 100).toFixed(0)}%)`)
                .join('\n')
              return (
                <g>
                  <circle cx={props.cx} cy={props.cy} r={4} fill={color} stroke={terminal.bg} strokeWidth={1}>
                    <title>{title}</title>
                  </circle>
                  {marker.patterns.length > 1 ? (
                    <text
                      x={props.cx}
                      y={props.cy - 7}
                      textAnchor="middle"
                      fontFamily={terminalFont}
                      fontSize={9}
                      fill={color}
                    >
                      ×{marker.patterns.length}
                    </text>
                  ) : null}
                </g>
              )
            }}
          />
        </ComposedChart>
      </ResponsiveContainer>
      </Box>
    </Box>
  )
}
