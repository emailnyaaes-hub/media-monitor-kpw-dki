import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  Legend,
  LineChart,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { formatDay, formatNumber } from '../format'
import { useTheme } from '../theme'
import type { IssueCard, TrendPoint } from '../types'

const POS = '#0E7C4A'
const NET = '#8B97A3'
const NEG = '#B43333'

function useChrome() {
  const { theme } = useTheme()
  return {
    grid: theme === 'dark' ? '#2A3B52' : '#E3E8EF',
    text: theme === 'dark' ? '#A8B6C7' : '#5C6B7C',
    tooltip: {
      background: theme === 'dark' ? '#121C2C' : '#ffffff',
      border: `1px solid ${theme === 'dark' ? '#2A3B52' : '#E3E8EF'}`,
      borderRadius: 8,
      color: theme === 'dark' ? '#E7EEF6' : '#142033',
      fontSize: 12,
    },
  }
}

export function TrendChart({ data, onPick }: { data: TrendPoint[]; onPick: (day: string) => void }) {
  const chrome = useChrome()
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={data}
          onClick={(state) => {
            const label = (state as { activeLabel?: string } | null)?.activeLabel
            if (label) onPick(String(label))
          }}
        >
          <CartesianGrid stroke={chrome.grid} vertical={false} />
          <XAxis dataKey="date" tickFormatter={formatDay} tick={{ fill: chrome.text, fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: chrome.text, fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
          <Tooltip
            contentStyle={chrome.tooltip}
            labelFormatter={(label) => formatDay(String(label))}
            formatter={(value, name, item) => {
              const spike = (item?.payload as TrendPoint | undefined)?.spike
              const text = name === 'total' && spike ? `${value} (lonjakan)` : value
              return [text as string | number, name as string]
            }}
          />
          <Legend />
          <Area type="monotone" dataKey="positif" name="Positif" stackId="1" stroke={POS} fill={POS} fillOpacity={0.8} />
          <Area type="monotone" dataKey="netral" name="Netral" stackId="1" stroke={NET} fill={NET} fillOpacity={0.75} />
          <Area type="monotone" dataKey="negatif" name="Negatif" stackId="1" stroke={NEG} fill={NEG} fillOpacity={0.8} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

function SpikeDot(props: { cx?: number; cy?: number; payload?: TrendPoint }) {
  const { cx, cy, payload } = props
  if (!payload?.spike || cx == null || cy == null) return <g />
  return (
    <g>
      <title>Lonjakan</title>
      <polygon points={`${cx},${cy - 9} ${cx - 5},${cy} ${cx + 5},${cy}`} fill={NEG} />
    </g>
  )
}

export function VolumeChart({ data, onPick, className = 'h-72' }: { data: TrendPoint[]; onPick?: (day: string) => void; className?: string }) {
  const chrome = useChrome()
  const totals = data.map((item) => item.total)
  const mean = totals.length ? totals.reduce((sum, value) => sum + value, 0) / totals.length : 0
  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart
          data={data}
          margin={{ top: 16, right: 8, left: 0, bottom: 0 }}
          onClick={(state) => {
            const label = (state as { activeLabel?: string } | null)?.activeLabel
            if (label && onPick) onPick(String(label))
          }}
        >
          <CartesianGrid stroke={chrome.grid} vertical={false} />
          <XAxis dataKey="date" tickFormatter={formatDay} tick={{ fill: chrome.text, fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: chrome.text, fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} width={32} />
          <Tooltip
            contentStyle={chrome.tooltip}
            labelFormatter={(label) => formatDay(String(label))}
            formatter={(value, name, item) => {
              if (name === 'total') return ['', '']
              const spike = (item?.payload as TrendPoint | undefined)?.spike
              return [value as number, spike && name === 'Negatif' ? 'Negatif · lonjakan' : (name as string)]
            }}
          />
          <Legend />
          <Bar dataKey="positif" name="Positif" stackId="1" fill={POS} />
          <Bar dataKey="netral" name="Netral" stackId="1" fill={NET} />
          <Bar dataKey="negatif" name="Negatif" stackId="1" fill={NEG} />
          {totals.length >= 5 && (
            <ReferenceLine y={mean} stroke={chrome.text} strokeDasharray="4 4" label={{ value: 'Rata-rata', fill: chrome.text, fontSize: 11, position: 'insideTopRight' }} />
          )}
          <Line dataKey="total" name="total" stroke="transparent" dot={SpikeDot} legendType="none" activeDot={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

export function Donut({ positif, netral, negatif, onPick }: { positif: number; netral: number; negatif: number; onPick?: (name: string) => void }) {
  const chrome = useChrome()
  const data = [
    { name: 'Positif', value: positif, color: POS },
    { name: 'Netral', value: netral, color: NET },
    { name: 'Negatif', value: negatif, color: NEG },
  ]
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius={58} outerRadius={84} paddingAngle={2} onClick={(item) => onPick?.(String((item as { name?: string }).name || ''))}>
            {data.map((item) => <Cell key={item.name} fill={item.color} />)}
          </Pie>
          <Tooltip contentStyle={chrome.tooltip} formatter={(value) => `${value}%`} />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}

export function StackedCategories({
  data,
}: {
  data: { category: string; positif: number; netral: number; negatif: number }[]
}) {
  const chrome = useChrome()
  return (
    <div className="h-80">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 24 }}>
          <CartesianGrid stroke={chrome.grid} horizontal={false} />
          <XAxis type="number" tick={{ fill: chrome.text, fontSize: 11 }} allowDecimals={false} />
          <YAxis type="category" dataKey="category" width={140} tick={{ fill: chrome.text, fontSize: 11 }} />
          <Tooltip contentStyle={chrome.tooltip} />
          <Legend />
          <Bar dataKey="positif" name="Positif" stackId="a" fill={POS} />
          <Bar dataKey="netral" name="Netral" stackId="a" fill={NET} />
          <Bar dataKey="negatif" name="Negatif" stackId="a" fill={NEG} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function MatrixChart({ items }: { items: IssueCard[] }) {
  const chrome = useChrome()
  const groups = [
    { key: 'upside', name: 'Upside', fill: POS },
    { key: 'netral', name: 'Netral', fill: NET },
    { key: 'downside', name: 'Downside', fill: NEG },
  ] as const
  return (
    <div className="h-96">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 12, right: 12, bottom: 16, left: 0 }}>
          <CartesianGrid stroke={chrome.grid} />
          <XAxis type="number" dataKey="x" name="Kecepatan" domain={[0, 100]} tick={{ fill: chrome.text, fontSize: 11 }} label={{ value: 'Kecepatan penyebaran', position: 'bottom', fill: chrome.text, fontSize: 12 }} />
          <YAxis type="number" dataKey="y" name="Dampak" domain={[0, 100]} tick={{ fill: chrome.text, fontSize: 11 }} label={{ value: 'Dampak', angle: -90, position: 'insideLeft', fill: chrome.text, fontSize: 12 }} />
          <ReferenceLine x={50} stroke={chrome.text} strokeDasharray="4 4" />
          <ReferenceLine y={50} stroke={chrome.text} strokeDasharray="4 4" />
          <Tooltip
            contentStyle={chrome.tooltip}
            cursor={{ strokeDasharray: '3 3' }}
            content={({ payload }) => {
              const point = payload?.[0]?.payload as IssueCard | undefined
              if (!point) return null
              return (
                <div style={chrome.tooltip} className="max-w-xs px-3 py-2">
                  <p className="font-medium">{point.title}</p>
                  <p className="mt-1">{point.quadrant} · risiko {formatNumber(Math.round(point.risk_score))}</p>
                </div>
              )
            }}
          />
          <Legend />
          {groups.map((group) => (
            <Scatter key={group.key} name={group.name} data={items.filter((item) => item.stance === group.key)} fill={group.fill} />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}

export function KeywordLines({
  data,
  series,
  onPick,
  className = 'h-72',
}: {
  data: Record<string, string | number>[]
  series: { term: string; color: string }[]
  onPick?: (term: string, date?: string) => void
  className?: string
}) {
  const chrome = useChrome()
  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data}
          margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
          onClick={(state) => {
            const payload = (state as { activeLabel?: string; activePayload?: { dataKey?: string }[] } | null)
            const key = payload?.activePayload?.[0]?.dataKey
            if (key && onPick) onPick(String(key), payload?.activeLabel ? String(payload.activeLabel) : undefined)
          }}
        >
          <CartesianGrid stroke={chrome.grid} vertical={false} />
          <XAxis dataKey="date" tickFormatter={formatDay} tick={{ fill: chrome.text, fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: chrome.text, fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} width={32} />
          <Tooltip contentStyle={chrome.tooltip} labelFormatter={(label) => formatDay(String(label))} />
          {series.map((item) => (
            <Line key={item.term} type="monotone" dataKey={item.term} stroke={item.color} strokeWidth={2} dot={{ r: 3 }} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export function KeywordBars({
  data,
  onPick,
  className = 'h-72',
}: {
  data: { term: string; count: number; color: string }[]
  onPick?: (term: string) => void
  className?: string
}) {
  const chrome = useChrome()
  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
          <CartesianGrid stroke={chrome.grid} horizontal={false} />
          <XAxis type="number" tick={{ fill: chrome.text, fontSize: 11 }} allowDecimals={false} />
          <YAxis type="category" dataKey="term" width={150} tick={{ fill: chrome.text, fontSize: 11 }} />
          <Tooltip contentStyle={chrome.tooltip} />
          <Bar dataKey="count" name="Jumlah" onClick={(item) => onPick?.(String((item as { term?: string }).term || ''))}>
            {data.map((item) => <Cell key={item.term} fill={item.color} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function SimpleBars({ data, color = '#1E4A7A' }: { data: { name: string; value: number }[]; color?: string }) {
  const chrome = useChrome()
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid stroke={chrome.grid} vertical={false} />
          <XAxis dataKey="name" tick={{ fill: chrome.text, fontSize: 11 }} />
          <YAxis tick={{ fill: chrome.text, fontSize: 11 }} />
          <Tooltip contentStyle={chrome.tooltip} />
          <Bar dataKey="value" name="Jangkauan" fill={color} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
