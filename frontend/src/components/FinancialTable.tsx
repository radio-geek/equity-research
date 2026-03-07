import type { ReportView } from '../api'
import { getYearlyTable } from '../reportUtils'

const trendColors: Record<string, string> = { positive: '#22c55e', negative: '#ef4444', neutral: 'var(--textMuted)' }

interface FinancialTableProps {
  report: ReportView
  style?: React.CSSProperties
}

export function FinancialTable({ report, style = {} }: FinancialTableProps) {
  const { headers, rows } = getYearlyTable(report)
  if (!headers.length) return null
  return (
    <div style={{ overflowX: 'auto', ...style }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--fontMono)', fontSize: '0.875rem' }}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)', color: 'var(--textMuted)' }}>Metric</th>
            {headers.map((h) => (
              <th key={h} style={{ textAlign: 'right', padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)', color: 'var(--textMuted)' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.metric}>
              <td style={{ padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)' }}>{row.metric}</td>
              {row.cells.map((cell, i) => (
                <td key={i} style={{ textAlign: 'right', padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)' }}>
                  <span>{cell.value_display}</span>
                  {cell.qoq_pct != null && (
                    <span style={{ marginLeft: '0.25rem', fontSize: '0.8em', color: trendColors[cell.trend] }}>
                      ({cell.qoq_pct > 0 ? '+' : ''}{cell.qoq_pct?.toFixed(1)}%)
                    </span>
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
