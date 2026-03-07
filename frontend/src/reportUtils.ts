import type { ReportView } from './api'

export function getYearlyTable(report: ReportView): { headers: string[]; rows: Array<{ metric: string; cells: Array<{ value_display: string; qoq_pct: number | null; trend: 'positive' | 'negative' | 'neutral' }> }> } {
  const metrics = report.yearlyMetrics
  if (!metrics?.length) return { headers: [], rows: [] }
  const headers = metrics.map((m) => (m.period_label as string) ?? '')
  const rowDefs = [
    { key: 'roe', label: 'ROE (%)', pctKey: 'roe_yoy_pct' },
    { key: 'roce', label: 'ROCE (%)', pctKey: 'roce_yoy_pct' },
    { key: 'debt_equity', label: 'Debt/Equity', pctKey: 'debt_equity_yoy_pct' },
    { key: 'revenue_cr', label: 'Revenue (Cr)', pctKey: 'revenue_yoy_pct' },
    { key: 'cfo_cr', label: 'CFO (Cr)', pctKey: 'cfo_yoy_pct' },
    { key: 'ebitda_cr', label: 'EBITDA (Cr)', pctKey: 'ebitda_yoy_pct' },
    { key: 'pat_cr', label: 'PAT (Cr)', pctKey: 'pat_yoy_pct' },
  ]
  const rows = rowDefs.map(({ key, label, pctKey }) => ({
    metric: label,
    cells: metrics.map((m) => {
      const val = m[key]
      const pct = m[pctKey] != null ? Number(m[pctKey]) : null
      const value_display = val != null ? (typeof val === 'number' ? (Number.isFinite(val) ? (val as number).toFixed(2) : '—') : String(val)) : '—'
      let trend: 'positive' | 'negative' | 'neutral' = 'neutral'
      if (pct != null) trend = pct > 0 ? 'positive' : pct < 0 ? 'negative' : 'neutral'
      return { value_display, qoq_pct: pct, trend }
    }),
  }))
  return { headers, rows }
}
