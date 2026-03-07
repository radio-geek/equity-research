import { useMemo } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import type { ReportView } from '../api'

const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#a855f7', '#ec4899', '#06b6d4', '#84cc16']

interface FinancialChartsProps {
  report: ReportView
  height?: number
}

export function FinancialCharts({ report, height = 280 }: FinancialChartsProps) {
  const charts = useMemo(() => {
    const metrics = report.yearlyMetrics ?? []
    if (!metrics.length) return []
    const periodKey = 'period_label'
    const series = [
      { key: 'roe', label: 'ROE (%)', yoy: 'roe_yoy_pct' },
      { key: 'roce', label: 'ROCE (%)', yoy: 'roce_yoy_pct' },
      { key: 'debt_equity', label: 'Debt/Equity', yoy: 'debt_equity_yoy_pct' },
      { key: 'revenue_cr', label: 'Revenue (Cr)', yoy: 'revenue_yoy_pct' },
      { key: 'cfo_cr', label: 'CFO (Cr)', yoy: 'cfo_yoy_pct' },
      { key: 'ebitda_cr', label: 'EBITDA (Cr)', yoy: 'ebitda_yoy_pct' },
      { key: 'pat_cr', label: 'PAT (Cr)', yoy: 'pat_yoy_pct' },
    ]
    return series.map((s, i) => ({
      title: s.label,
      color: COLORS[i % COLORS.length],
      data: metrics.map((m) => ({
        period: (m[periodKey] as string) ?? '',
        value: (m[s.key] as number) ?? 0,
        yoy: (m[s.yoy] as number | null) ?? null,
      })),
    }))
  }, [report.yearlyMetrics])

  if (!charts.length) return null
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1.5rem' }}>
      {charts.map((chart) => (
        <div key={chart.title} style={{ background: 'var(--surface)', borderRadius: 8, padding: '1rem', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.5rem' }}>{chart.title}</div>
          <ResponsiveContainer width="100%" height={height}>
            <LineChart data={chart.data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="period" tick={{ fontSize: 11 }} stroke="var(--textMuted)" />
              <YAxis tick={{ fontSize: 11 }} stroke="var(--textMuted)" />
              <Tooltip
                contentStyle={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 6 }}
                formatter={(value: number, _name: string, props: { payload?: { yoy?: number | null } }) => [
                  `${value}${props.payload?.yoy != null ? ` (${props.payload.yoy > 0 ? '+' : ''}${props.payload.yoy?.toFixed(1)}% YoY)` : ''}`,
                  chart.title,
                ]}
              />
              <Line type="monotone" dataKey="value" stroke={chart.color} strokeWidth={2} dot={{ r: 4 }} name={chart.title} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ))}
    </div>
  )
}
