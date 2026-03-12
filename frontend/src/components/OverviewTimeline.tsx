/** Vertical timeline with bubble dot per year; multiple events in the same year are grouped under one node. */
interface TimelineItem {
  year?: string
  event?: string
}

interface OverviewTimelineProps {
  items: TimelineItem[]
}

function groupByYear(items: TimelineItem[]): Array<{ year: string; events: string[] }> {
  const map = new Map<string, string[]>()
  for (const item of items) {
    const y = String(item.year ?? '').trim()
    const e = String(item.event ?? '').trim()
    if (!y && !e) continue
    const year = y || '—'
    if (!map.has(year)) map.set(year, [])
    if (e) map.get(year)!.push(e)
  }
  return Array.from(map.entries()).map(([year, events]) => ({ year, events }))
}

export function OverviewTimeline({ items }: OverviewTimelineProps) {
  const grouped = groupByYear(items)
  if (!grouped.length) return null

  return (
    <div style={{ position: 'relative', paddingLeft: '1.5rem', paddingTop: '0.25rem' }}>
      <div
        style={{
          position: 'absolute',
          left: 5,
          top: 14,
          bottom: 14,
          width: 2,
          background: 'var(--border)',
          borderRadius: 1,
        }}
        aria-hidden
      />
      {grouped.map(({ year, events }, i) => (
        <div
          key={i}
          style={{
            position: 'relative',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '0.75rem',
            marginBottom: i < grouped.length - 1 ? '1.5rem' : 0,
            paddingTop: i === 0 ? 0 : '0.125rem',
          }}
        >
          <div
            style={{
              position: 'absolute',
              left: '-1.5rem',
              top: 5,
              width: 12,
              height: 12,
              borderRadius: '50%',
              background: 'var(--accent)',
              border: '2px solid var(--surface)',
              flexShrink: 0,
            }}
            aria-hidden
          />
          <div style={{ flex: 1, minWidth: 0, lineHeight: 1.55 }}>
            <span
              style={{
                fontWeight: 600,
                fontSize: '0.9rem',
                color: 'var(--accent)',
                marginRight: '0.5rem',
              }}
            >
              {year}
            </span>
            {events.length > 0 && (
              events.length === 1 ? (
                <span style={{ fontSize: '0.95rem', color: 'var(--text)' }}>{events[0]}</span>
              ) : (
                <ul style={{ margin: '0.25rem 0 0 1rem', padding: 0, listStyleType: 'disc' }}>
                  {events.map((ev, j) => (
                    <li key={j} style={{ marginBottom: '0.2rem', fontSize: '0.95rem', color: 'var(--text)' }}>
                      {ev}
                    </li>
                  ))}
                </ul>
              )
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
