/** Renders concall data grouped by Financial Year with collapsible accordions. */
import { useState } from 'react'

/** Parse [text](url) markdown links into clickable <a> elements. */
function renderInlineLinks(text: string): React.ReactNode {
  const parts: React.ReactNode[] = []
  const regex = /\[([^\]]+)\]\(([^)]+)\)/g
  let lastIndex = 0
  let match
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index))
    parts.push(
      <a key={match.index} href={match[2]} target="_blank" rel="noopener noreferrer"
        style={{ color: 'var(--accent)', textDecoration: 'underline' }}>
        {match[1]}
      </a>
    )
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex))
  return parts.length > 0 ? parts : text
}

interface ConcallSectionProps {
  concall?: Record<string, unknown> | null
  concallUpdatesFallback?: string
  style?: React.CSSProperties
}

type EventData = { type?: string; headline?: string; details?: string[] }
type QAData = { q?: string; a?: string }
type CardData = {
  period?: string
  badge?: string
  link?: string | null
  events?: EventData[]
  qaHighlights?: QAData[]
  bullets?: string[]
  guidance?: string | null
  _firstConcall?: boolean
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

const EVENT_STYLES: Record<string, { color: string; bg: string; label: string }> = {
  acquisition:      { color: '#60a5fa', bg: 'rgba(96,165,250,0.15)',  label: 'Acquisition' },
  fundraise:        { color: 'var(--green)', bg: 'rgba(34,197,94,0.15)',  label: 'Fundraise' },
  stake_sale:       { color: 'var(--amber)', bg: 'rgba(245,158,11,0.15)', label: 'Stake Sale' },
  capex:            { color: '#a78bfa', bg: 'rgba(167,139,250,0.15)', label: 'Capex' },
  order_win:        { color: 'var(--green)', bg: 'rgba(34,197,94,0.15)',  label: 'Order Win' },
  mgmt_change:      { color: 'var(--amber)', bg: 'rgba(245,158,11,0.15)', label: 'Mgmt Change' },
  guidance_change:  { color: 'var(--textMuted)', bg: 'rgba(150,150,150,0.12)', label: 'Guidance' },
}

function isMissing(badge?: string) {
  return badge === 'missing' || badge === 'sme-missing'
}

function groupCardsIntoTwo(cards: CardData[]): Array<[string, CardData[]]> {
  if (cards.length === 0) return []
  const recent = cards.slice(0, 4)
  const older = cards.slice(4)
  const groups: Array<[string, CardData[]]> = [['Recent quarters', recent]]
  if (older.length > 0) groups.push(['Older quarters', older])
  return groups
}

/**
 * Strips trailing missing cards (pre-IPO quarters) from the oldest end and marks
 * the oldest real concall as _firstConcall. Middle missing cards (skipped quarters)
 * are left intact — those are genuinely missed, not pre-IPO.
 */
function processCards(cards: CardData[]): CardData[] {
  if (cards.length === 0) return cards
  let trailingStart = cards.length
  for (let i = cards.length - 1; i >= 0; i--) {
    if (isMissing(cards[i].badge)) trailingStart = i
    else break
  }
  if (trailingStart === cards.length) return cards
  if (trailingStart === 0) return []
  return cards.slice(0, trailingStart).map((card, i) =>
    i === trailingStart - 1 ? { ...card, _firstConcall: true } : card
  )
}

function Badge({ type, href }: { type?: string; href?: string | null }) {
  const label = (type && BADGE_LABELS[type]) || type || ''
  const isConcallBadge = type === 'concall' || type === 'sme-concall'
  const isMissingBadge = type === 'missing' || type === 'sme-missing'
  const style: React.CSSProperties = {
    fontSize: '0.7rem',
    padding: '0.2rem 0.5rem',
    borderRadius: 4,
    background: isConcallBadge ? 'rgba(34,197,94,0.2)' : isMissingBadge ? 'rgba(239,68,68,0.15)' : 'rgba(245,158,11,0.2)',
    color: isConcallBadge ? 'var(--green)' : isMissingBadge ? 'var(--red)' : 'var(--amber)',
    marginLeft: '0.5rem',
    textDecoration: 'none',
  }
  if (href) {
    return <a href={href} target="_blank" rel="noopener noreferrer" style={style} title="View source">{label} ↗</a>
  }
  return <span style={style}>{label}</span>
}

function EventChip({ type }: { type?: string }) {
  const style = (type && EVENT_STYLES[type]) || { color: 'var(--textMuted)', bg: 'rgba(150,150,150,0.12)', label: type || '' }
  return (
    <span style={{
      fontSize: '0.68rem',
      fontWeight: 600,
      padding: '0.15rem 0.45rem',
      borderRadius: 99,
      background: style.bg,
      color: style.color,
      whiteSpace: 'nowrap',
    }}>
      {style.label}
    </span>
  )
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none"
      style={{ transform: open ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.2s', flexShrink: 0 }}>
      <path d="M6 4l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function ConcallCard({ card }: { card: CardData }) {
  const [qaOpen, setQaOpen] = useState(false)
  const missing = isMissing(card.badge)
  const first = card._firstConcall
  const events = card.events?.filter(e => e.headline) ?? []
  const qa = card.qaHighlights?.filter(q => q.q && q.a) ?? []

  return (
    <div style={{
      background: missing ? 'var(--surface2)' : 'var(--surface)',
      border: `1px ${missing ? 'dashed' : 'solid'} ${first ? 'var(--accent)' : 'var(--border)'}`,
      borderRadius: 8,
      padding: '0.85rem',
      opacity: missing ? 0.5 : 1,
    }}>
      {/* First concall label */}
      {first && (
        <div style={{ fontSize: '0.68rem', fontWeight: 600, letterSpacing: '0.03em', color: 'var(--accent)', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
          <span>★</span> First concall post-listing
        </div>
      )}

      {/* Header: period + source badge (linked if URL available) */}
      <div style={{ fontSize: '0.88rem', fontWeight: 600, marginBottom: '0.4rem', display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '0.25rem' }}>
        {card.period}
        <Badge type={card.badge} href={card.link} />
      </div>

      {!missing && (
        <>
          {/* Event chips row */}
          {events.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem', marginBottom: '0.6rem' }}>
              {events.map((e, i) => <EventChip key={i} type={e.type} />)}
            </div>
          )}

          {/* Event details */}
          {events.map((e, i) => {
            const s = (e.type && EVENT_STYLES[e.type]) || null
            return (
              <div key={i} style={{ marginBottom: '0.5rem', paddingLeft: '0.5rem', borderLeft: `2px solid ${s?.color ?? 'var(--border)'}` }}>
                <div style={{ fontSize: '0.8rem', fontWeight: 600, color: s?.color ?? 'var(--text)', marginBottom: '0.2rem' }}>
                  {e.headline}
                </div>
                {(e.details ?? []).map((d, j) => (
                  <div key={j} style={{ fontSize: '0.78rem', color: 'var(--textMuted)', lineHeight: 1.45 }}>• {d}</div>
                ))}
              </div>
            )
          })}

          {/* Operational bullets */}
          {(card.bullets ?? []).length > 0 && (
            <ul style={{ margin: events.length > 0 ? '0.4rem 0 0' : '0', paddingLeft: '1.1rem', fontSize: '0.82rem', lineHeight: 1.55 }}>
              {(card.bullets ?? []).map((b, j) => <li key={j}>{b}</li>)}
            </ul>
          )}

          {/* Guidance */}
          {card.guidance && (
            <p style={{ margin: '0.5rem 0 0', fontSize: '0.78rem', color: 'var(--textMuted)', fontStyle: 'italic' }}>
              <strong>Guidance:</strong> {card.guidance}
            </p>
          )}

          {/* Q&A — collapsible, only shown if present */}
          {qa.length > 0 && (
            <div style={{ marginTop: '0.6rem', borderTop: '1px solid var(--border)', paddingTop: '0.5rem' }}>
              <button
                type="button"
                onClick={() => setQaOpen(o => !o)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--textMuted)', fontSize: '0.78rem', padding: 0, display: 'flex', alignItems: 'center', gap: '0.3rem' }}
              >
                <ChevronIcon open={qaOpen} />
                Key Q&A ({qa.length})
              </button>
              {qaOpen && (
                <div style={{ marginTop: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {qa.map((item, i) => (
                    <div key={i} style={{ fontSize: '0.78rem', lineHeight: 1.5 }}>
                      <div style={{ color: 'var(--textMuted)', marginBottom: '0.15rem' }}>
                        <strong style={{ color: 'var(--text)' }}>Q:</strong> {item.q}
                      </div>
                      <div style={{ color: 'var(--textMuted)' }}>
                        <strong style={{ color: 'var(--text)' }}>A:</strong> {item.a}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function FYAccordion({ groups }: { groups: Array<[string, CardData[]]> }) {
  const [openFYs, setOpenFYs] = useState<Set<string>>(
    () => new Set(groups.length > 0 ? [groups[0][0]] : [])
  )

  const toggleFY = (fy: string) => {
    setOpenFYs(prev => {
      const next = new Set(prev)
      if (next.has(fy)) next.delete(fy)
      else next.add(fy)
      return next
    })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1.5rem' }}>
      {groups.map(([fy, cards]) => {
        const isOpen = openFYs.has(fy)
        const count = cards.filter(c => !isMissing(c.badge)).length
        return (
          <div key={fy} style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
            <button
              type="button"
              onClick={() => toggleFY(fy)}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: '0.6rem',
                padding: '0.75rem 1rem',
                background: isOpen ? 'var(--surface)' : 'var(--surface2)',
                border: 'none',
                cursor: 'pointer',
                color: 'var(--text)',
                textAlign: 'left',
              }}
            >
              <ChevronIcon open={isOpen} />
              <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>{fy}</span>
              <span style={{
                fontSize: '0.75rem',
                padding: '0.15rem 0.5rem',
                borderRadius: 99,
                background: count > 0 ? 'rgba(34,197,94,0.15)' : 'rgba(150,150,150,0.15)',
                color: count > 0 ? 'var(--green)' : 'var(--textMuted)',
                marginLeft: '0.25rem',
              }}>
                {count} {count === 1 ? 'concall' : 'concalls'}
              </span>
              <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: 'var(--textMuted)' }}>
                {cards.length} {cards.length === 1 ? 'quarter' : 'quarters'}
              </span>
            </button>

            {isOpen && (
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
                gap: '0.75rem',
                padding: '0.75rem',
                background: 'var(--bg)',
              }}>
                {cards.map((card, i) => <ConcallCard key={i} card={card} />)}
              </div>
            )}
          </div>
        )
      })}
    </div>
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

  const type = concall.type as string | undefined

  // ---- no_concall_updates: company had no concalls in last 8 quarters ----
  if (type === 'no_concall_updates') {
    const sectionTitle = concall.sectionTitle as string | undefined
    const noConcallMessage = (concall.noConcallMessage as string | undefined) || 'No concalls held in last 8 quarters'
    const investorPresentation = concall.investorPresentation as { period?: string; link?: string; bullets?: string[] } | undefined
    const orderBook = concall.orderBook as { bullets?: string[] } | undefined
    const pressReleases = concall.pressReleases as { bullets?: string[] } | undefined

    return (
      <div className="concall-section" style={{ marginBottom: '2rem', ...style }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '0.75rem' }}>{sectionTitle || 'Company Updates'}</h2>

        {/* No concall alert */}
        <div style={{ marginBottom: '1.25rem', padding: '0.75rem 1rem', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, fontSize: '0.9rem', color: 'var(--red)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span>⚠</span>
          <span>{noConcallMessage}</span>
        </div>

        {/* Investor Presentation */}
        {(investorPresentation?.bullets?.length ?? 0) > 0 && (
          <div style={{ marginBottom: '1.25rem' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              Investor Presentation
              {investorPresentation!.period && (
                <span style={{ fontWeight: 400, fontSize: '0.85rem', color: 'var(--textMuted)' }}>— {investorPresentation!.period}</span>
              )}
              {investorPresentation!.link && (
                <a href={investorPresentation!.link} target="_blank" rel="noopener noreferrer"
                  style={{ fontSize: '0.75rem', color: 'var(--accent)', marginLeft: '0.25rem' }}>
                  View PPT ↗
                </a>
              )}
            </h3>
            <ul style={{ margin: 0, paddingLeft: '1.1rem', fontSize: '0.88rem', lineHeight: 1.6 }}>
              {investorPresentation!.bullets!.map((b, i) => <li key={i}>{renderInlineLinks(b)}</li>)}
            </ul>
          </div>
        )}

        {/* Order Book & Contracts */}
        {(orderBook?.bullets?.length ?? 0) > 0 && (
          <div style={{ marginBottom: '1.25rem' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.5rem' }}>Order Book & Contracts</h3>
            <ul style={{ margin: 0, paddingLeft: '1.1rem', fontSize: '0.88rem', lineHeight: 1.6 }}>
              {orderBook!.bullets!.map((b, i) => <li key={i}>{renderInlineLinks(b)}</li>)}
            </ul>
          </div>
        )}

        {/* Press Releases */}
        {(pressReleases?.bullets?.length ?? 0) > 0 && (
          <div style={{ marginBottom: '1.25rem' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.5rem' }}>Press Releases</h3>
            <ul style={{ margin: 0, paddingLeft: '1.1rem', fontSize: '0.88rem', lineHeight: 1.6 }}>
              {pressReleases!.bullets!.map((b, i) => <li key={i}>{renderInlineLinks(b)}</li>)}
            </ul>
          </div>
        )}
      </div>
    )
  }

  const sectionTitle = concall.sectionTitle as string | undefined
  const summary = concall.summary as string | undefined
  const summaryBar = concall.summaryBar as { badge?: string; text?: string } | undefined
  const cards = (concall.cards as CardData[]) ?? []
  const capex = (concall.capex as Array<{ project?: string; amount?: string; funding?: string; description?: string }>) ?? []
  const guidanceTable = concall.guidanceTable as { headers?: string[]; rows?: Array<{ metric?: string; cells?: Array<{ value?: string; trend?: string }> }> } | undefined
  const noConcallAlerts = (concall.noConcallAlerts as string[]) ?? []
  const sources = (concall.sources as Array<{ period?: string; source?: string }>) ?? []

  const processedCards = processCards(cards)
  const grouped = groupCardsIntoTwo(processedCards).filter(([, grpCards]) => grpCards.some((c: CardData) => !isMissing(c.badge)))

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

      {grouped.length > 0 && <FYAccordion groups={grouped} />}

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
          {noConcallAlerts.map((msg, i) => <div key={i}>{msg}</div>)}
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
