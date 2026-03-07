/** Renders concall data: mainboard_concall (8 quarters, capex, guidance table) or sme_updates (cards, capex, sources). */

interface ConcallSectionProps {
  concall?: Record<string, unknown> | null
  concallUpdatesFallback?: string
  style?: React.CSSProperties
}

const BADGE_LABELS: Record<string, string> = {
  concall: 'Concall',
  'press-release': 'Press release',
  ppt: 'PPT',
  missing: 'Missing',
  'sme-concall': 'Concall',
  'sme-board': 'Board letter',
  'sme-ppt': 'PPT',
  'sme-results': 'Results',
  'sme-interview': 'Interview',
  'sme-missing': 'Missing',
}

const TREND_CLASS: Record<string, { color: string; label: string }> = {
  raised: { color: 'var(--green)', label: 'Raised' },
  cut: { color: 'var(--red)', label: 'Cut' },
  maintained: { color: 'var(--amber)', label: 'Maintained' },
  neutral: { color: 'var(--textMuted)', label: '—' },
}

function Badge({ type }: { type?: string }) {
  const label = (type && BADGE_LABELS[type]) || type || ''
  const isConcall = type === 'concall' || type === 'sme-concall'
  const isMissing = type === 'missing' || type === 'sme-missing'
  return (
    <span
      style={{
        fontSize: '0.7rem',
        padding: '0.2rem 0.5rem',
        borderRadius: 4,
        background: isConcall ? 'rgba(34,197,94,0.2)' : isMissing ? 'rgba(239,68,68,0.15)' : 'rgba(245,158,11,0.2)',
        color: isConcall ? 'var(--green)' : isMissing ? 'var(--red)' : 'var(--amber)',
        marginLeft: '0.5rem',
      }}
    >
      {label}
    </span>
  )
}

export function ConcallSection({ concall, concallUpdatesFallback, style = {} }: ConcallSectionProps) {
  if (!concall) {
    if (!concallUpdatesFallback) return null
    return (
      <div style={style}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '0.75rem' }}>Concall / Company Updates</h2>
        <p style={{ margin: 0 }}>{concallUpdatesFallback}</p>
      </div>
    )
  }

  const sectionTitle = concall.sectionTitle as string | undefined
  const type = concall.type as string | undefined
  const summary = concall.summary as string | undefined
  const summaryBar = concall.summaryBar as { badge?: string; text?: string } | undefined
  const cards = (concall.cards as Array<{ period?: string; badge?: string; bullets?: string[]; guidance?: string | null }>) ?? []
  const capex = (concall.capex as Array<{ project?: string; amount?: string; funding?: string; description?: string }>) ?? []
  const guidanceTable = concall.guidanceTable as { headers?: string[]; rows?: Array<{ metric?: string; cells?: Array<{ value?: string; trend?: string }> }> } | undefined
  const noConcallAlerts = (concall.noConcallAlerts as string[]) ?? []
  const sources = (concall.sources as Array<{ period?: string; source?: string }>) ?? []

  return (
    <div className="concall-section" style={{ marginBottom: '2rem', ...style }}>
      <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '0.75rem' }}>{sectionTitle}</h2>

      {type === 'mainboard_concall' && summary && (
        <p style={{ marginBottom: '1rem', color: 'var(--text)', fontSize: '0.95rem' }}>{summary}</p>
      )}

      {type === 'sme_updates' && summaryBar && (
        <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', background: 'var(--surface)', borderRadius: 8, border: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem', background: 'var(--accent)', color: '#fff', borderRadius: 4 }}>{summaryBar.badge}</span>
          <span style={{ fontSize: '0.9rem' }}>{summaryBar.text}</span>
        </div>
      )}

      {cards.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
          {cards.map((card, i) => (
            <div
              key={i}
              style={{
                background: 'var(--surface)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: '1rem',
              }}
            >
              <div style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem', display: 'flex', alignItems: 'center', flexWrap: 'wrap' }}>
                {card.period}
                <Badge type={card.badge} />
              </div>
              <ul style={{ margin: 0, paddingLeft: '1.1rem', fontSize: '0.85rem', lineHeight: 1.5 }}>
                {(card.bullets || []).map((b, j) => (
                  <li key={j}>{b}</li>
                ))}
              </ul>
              {card.guidance && (
                <p style={{ margin: '0.5rem 0 0', fontSize: '0.8rem', color: 'var(--textMuted)', fontStyle: 'italic' }}>
                  <strong>Guidance:</strong> {card.guidance}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {capex.length > 0 && (
        <div style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.5rem' }}>Capital expenditure & major developments</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {capex.map((item, i) => (
              <div key={i} style={{ padding: '0.6rem 0.8rem', background: 'var(--surface2)', borderRadius: 6, border: '1px solid var(--border)', fontSize: '0.9rem' }}>
                {'project' in item && item.project ? (
                  <>
                    <strong>{item.project}</strong>
                    {item.amount && <span style={{ color: 'var(--accent)', marginLeft: '0.5rem' }}>{item.amount}</span>}
                    {item.funding && <div style={{ fontSize: '0.85rem', color: 'var(--textMuted)', marginTop: '0.25rem' }}>Funding: {item.funding}</div>}
                  </>
                ) : (
                  (item as { description?: string }).description
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {type === 'mainboard_concall' && guidanceTable?.headers && guidanceTable.rows && guidanceTable.rows.length > 0 && (
        <div style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.5rem' }}>Guidance tracker</h3>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
              <thead>
                <tr>
                  {guidanceTable.headers.map((h, i) => (
                    <th key={i} style={{ textAlign: i === 0 ? 'left' : 'center', padding: '0.5rem 0.4rem', borderBottom: '1px solid var(--border)', color: 'var(--textMuted)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {guidanceTable.rows.map((row, ri) => (
                  <tr key={ri}>
                    <td style={{ padding: '0.5rem 0.4rem', borderBottom: '1px solid var(--border)', fontWeight: 500 }}>{row.metric}</td>
                    {(row.cells || []).map((cell, ci) => {
                      const trend = (cell.trend as string) || 'neutral'
                      const trendStyle = TREND_CLASS[trend] || TREND_CLASS.neutral
                      return (
                        <td key={ci} style={{ textAlign: 'center', padding: '0.5rem 0.4rem', borderBottom: '1px solid var(--border)', color: trendStyle.color }}>
                          {cell.value}
                          {trend !== 'neutral' && <span style={{ fontSize: '0.75rem', marginLeft: '0.2rem' }}>{trend === 'raised' ? '▲' : trend === 'cut' ? '▼' : ''}</span>}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p style={{ fontSize: '0.75rem', color: 'var(--textMuted)', marginTop: '0.35rem' }}>Green = Raised · Red = Cut · Yellow = Maintained</p>
        </div>
      )}

      {noConcallAlerts.length > 0 && (
        <div style={{ padding: '0.6rem 0.8rem', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 6, fontSize: '0.85rem', color: 'var(--red)' }}>
          {noConcallAlerts.map((msg, i) => (
            <div key={i}>{msg}</div>
          ))}
        </div>
      )}

      {type === 'sme_updates' && sources.length > 0 && (
        <div>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.5rem' }}>Information sources</h3>
          <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.9rem' }}>
            {sources.map((s, i) => (
              <li key={i}><strong>{s.period}:</strong> {s.source}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
