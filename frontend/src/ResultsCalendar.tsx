import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  getEarningsCalendar,
  type EarningsCalendarEntry,
  type EarningsComparison,
} from './api'
import { trackEvent } from './analytics'

type LoadPhase = 'loading' | 'ready' | 'error'
type SortKey = 'results_date' | 'yoy' | 'qoq' | 'lag'
type WindowKey = '7' | '14' | '30' | 'past'

const WINDOWS: { key: WindowKey; label: string }[] = [
  { key: '7', label: 'Next 7 days' },
  { key: '14', label: 'Next 14 days' },
  { key: '30', label: 'Next 30 days' },
  { key: 'past', label: 'Last 30 days' },
]

const PERIOD_FILTERS = [
  { key: '', label: 'All' },
  { key: 'Q', label: 'Quarterly' },
  { key: 'H', label: 'Half-yearly' },
  { key: 'FY', label: 'Annual' },
]

/** Why a comparison has no number, in words. */
const REASON_LABEL: Record<string, string> = {
  no_peer: 'no prior period',
  not_comparable_audit_cycle: 'n/a — audited',
  cadence_change: 'cadence changed',
  gap_in_history: 'gap in history',
  period_unattributed: 'period unknown',
  half_yearly_no_sequential_peer: 'n/a — half-yearly',
}

const MS_PER_DAY = 86400000

function isoToday(): string {
  return new Date().toISOString().slice(0, 10)
}

function shiftDays(iso: string, days: number): string {
  return new Date(+new Date(iso) + days * MS_PER_DAY).toISOString().slice(0, 10)
}

function daysBetween(a: string, b: string): number {
  return Math.round((+new Date(a) - +new Date(b)) / MS_PER_DAY)
}

/** '2026-10-17' -> '17 Oct 2026'. No date library is installed; don't add one. */
function formatDate(iso: string | null): string {
  if (!iso) return '—'
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return `${d.getUTCDate()} ${months[d.getUTCMonth()]} ${d.getUTCFullYear()}`
}

/** 'Q2 FY27', or 'H FY27' / 'FY27' for non-quarterly filers. */
function periodLabel(e: EarningsCalendarEntry): string {
  if (!e.fiscal_year || !e.period_type) return '—'
  const fy = `FY${String(e.fiscal_year % 100).padStart(2, '0')}`
  if (e.period_type === 'Q') return `Q${e.fiscal_quarter ?? '?'} ${fy}`
  if (e.period_type === 'FY') return fy
  return `${e.period_type} ${fy}`
}

function relativeDay(iso: string): string {
  const diff = daysBetween(iso, isoToday())
  if (diff === 0) return 'today'
  if (diff === 1) return 'tomorrow'
  if (diff > 0) return `in ${diff}d`
  return `${Math.abs(diff)}d ago`
}

/** Render a YoY/QoQ cell. Branches on `reason` first: `value` is null when there is no peer,
 *  and `null < 0` is false in JS, so comparing it numerically would silently print "later". */
function ComparisonCell({ c }: { c: EarningsComparison }) {
  if (c.reason !== 'ok' || c.value === null) {
    return (
      <span style={{ color: 'var(--textMuted)', fontSize: '0.85em' }}>
        {REASON_LABEL[c.reason] ?? '—'}
      </span>
    )
  }
  const earlier = c.value < 0
  const color = c.value === 0 ? 'var(--textMuted)' : earlier ? 'var(--green)' : 'var(--red)'
  return (
    <span>
      <span style={{ color: 'var(--textMuted)', fontSize: '0.85em' }}>
        {formatDate(c.peer_results_date)}
      </span>
      <span style={{ marginLeft: '0.5rem', color, fontWeight: 600 }}>
        {c.value === 0 ? 'same' : `${c.value > 0 ? '+' : ''}${c.value}d`}
      </span>
    </span>
  )
}

const th: React.CSSProperties = {
  textAlign: 'left',
  padding: '0.5rem 0.75rem',
  borderBottom: '1px solid var(--border)',
  color: 'var(--textMuted)',
  fontWeight: 600,
  whiteSpace: 'nowrap',
}
const thNum: React.CSSProperties = { ...th, textAlign: 'right' }
const td: React.CSSProperties = {
  padding: '0.5rem 0.75rem',
  borderBottom: '1px solid var(--border)',
  verticalAlign: 'top',
}
const tdNum: React.CSSProperties = { ...td, textAlign: 'right' }

export default function ResultsCalendar() {
  const [entries, setEntries] = useState<EarningsCalendarEntry[]>([])
  const [loadPhase, setLoadPhase] = useState<LoadPhase>('loading')
  const [windowKey, setWindowKey] = useState<WindowKey>('30')
  const [periodType, setPeriodType] = useState('')
  const [query, setQuery] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('results_date')

  useEffect(() => {
    const today = isoToday()
    const range =
      windowKey === 'past'
        ? { from: shiftDays(today, -30), to: today }
        : { from: today, to: shiftDays(today, Number(windowKey)) }

    let cancelled = false
    setLoadPhase('loading')
    getEarningsCalendar({ ...range, periodType: periodType || undefined })
      .then((data) => {
        if (cancelled) return
        setEntries(data)
        setLoadPhase('ready')
      })
      .catch(() => {
        if (!cancelled) setLoadPhase('error')
      })
    return () => {
      cancelled = true
    }
  }, [windowKey, periodType])

  const rows = useMemo(() => {
    const q = query.trim().toUpperCase()
    const filtered = q
      ? entries.filter(
          (e) =>
            e.symbol.includes(q) ||
            (e.company_name ?? '').toUpperCase().includes(q),
        )
      : entries
    const sorted = [...filtered]
    sorted.sort((a, b) => {
      if (sortKey === 'results_date') {
        // ISO dates sort lexicographically.
        return a.results_date.localeCompare(b.results_date) || a.symbol.localeCompare(b.symbol)
      }
      if (sortKey === 'lag') return (a.lag_days ?? 1e9) - (b.lag_days ?? 1e9)
      // Delta sorts: rows without a comparable value sink to the bottom either way.
      const av = a[sortKey].reason === 'ok' ? a[sortKey].value : null
      const bv = b[sortKey].reason === 'ok' ? b[sortKey].value : null
      if (av === null && bv === null) return a.symbol.localeCompare(b.symbol)
      if (av === null) return 1
      if (bv === null) return -1
      return av - bv
    })
    return sorted
  }, [entries, query, sortKey])

  const summary = useMemo(() => {
    const comparable = rows.filter((r) => r.yoy.reason === 'ok' && r.yoy.value !== null)
    return {
      total: rows.length,
      earlier: comparable.filter((r) => (r.yoy.value as number) < 0).length,
      later: comparable.filter((r) => (r.yoy.value as number) > 0).length,
      same: comparable.filter((r) => r.yoy.value === 0).length,
    }
  }, [rows])

  return (
    <div className="report-page">
      <div className="rc-head">
        <h1 className="rc-title">Results Calendar</h1>
        <p className="rc-sub">
          Companies that have announced a results date, with how that timing compares to the
          same period last year and to the previous period. Comparisons use{' '}
          <strong>lag</strong> — days from period end to declaration — because results dates
          fall in different months each quarter and raw dates are not comparable.
        </p>
      </div>

      <div className="rc-controls">
        <div className="rc-tabs" role="tablist" aria-label="Date window">
          {WINDOWS.map((w) => (
            <button
              key={w.key}
              type="button"
              role="tab"
              aria-selected={windowKey === w.key}
              className={`report-sticky-section-btn${windowKey === w.key ? ' active' : ''}`}
              onClick={() => {
                setWindowKey(w.key)
                trackEvent('Results Calendar Window', { window: w.key })
              }}
            >
              {w.label}
            </button>
          ))}
        </div>

        <div className="rc-filters">
          <select
            className="rc-select"
            value={periodType}
            onChange={(e) => setPeriodType(e.target.value)}
            aria-label="Filter by reporting period type"
          >
            {PERIOD_FILTERS.map((p) => (
              <option key={p.key} value={p.key}>{p.label}</option>
            ))}
          </select>

          <select
            className="rc-select"
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value as SortKey)}
            aria-label="Sort rows"
          >
            <option value="results_date">Sort: results date</option>
            <option value="yoy">Sort: YoY delta (earliest first)</option>
            <option value="qoq">Sort: QoQ delta (earliest first)</option>
            <option value="lag">Sort: lag</option>
          </select>

          <input
            className="rc-search"
            type="search"
            placeholder="Filter by company or symbol"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Filter by company or symbol"
          />
        </div>
      </div>

      {loadPhase === 'loading' && (
        <div className="rc-state">Loading results calendar…</div>
      )}

      {loadPhase === 'error' && (
        <div className="report-error">
          <p>Could not load the results calendar.</p>
          <button type="button" onClick={() => window.location.reload()}>Retry</button>
        </div>
      )}

      {loadPhase === 'ready' && rows.length === 0 && (
        <div className="rc-state">
          No announced results dates in this window.
        </div>
      )}

      {loadPhase === 'ready' && rows.length > 0 && (
        <>
          <p className="rc-summary">
            {summary.total} announced
            {summary.earlier + summary.later + summary.same > 0 && (
              <>
                {' · '}
                <span style={{ color: 'var(--green)' }}>{summary.earlier} earlier</span>
                {' · '}
                <span style={{ color: 'var(--red)' }}>{summary.later} later</span>
                {' · '}
                {summary.same} unchanged vs last year
              </>
            )}
          </p>
          <p className="rc-caveat">
            Mid-season this split skews early, because only companies that have already announced
            appear here and they are the early reporters by definition, while last year's
            comparison covers the whole season. Read the per-company deltas, not this ratio.
          </p>

          <div className="report-container" style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
              <thead>
                <tr>
                  <th style={th}>Company</th>
                  <th style={th}>Period</th>
                  <th style={th}>Results date</th>
                  <th style={thNum}>Lag</th>
                  <th style={th}>vs last year (YoY)</th>
                  <th style={th}>vs prev period (QoQ)</th>
                  <th style={th}>Announced</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((e) => (
                  <tr key={e.id}>
                    <td style={td}>
                      <Link
                        to={`/${encodeURIComponent(e.symbol)}/report`}
                        style={{ color: 'var(--accent)', fontWeight: 600,
                          textDecoration: 'none' }}
                      >
                        {e.symbol}
                      </Link>
                      {e.company_name && (
                        <div style={{ color: 'var(--textMuted)', fontSize: '0.8em',
                          maxWidth: 190 }}>
                          {e.company_name}
                        </div>
                      )}
                    </td>

                    <td style={td}>
                      {periodLabel(e)}
                      {e.period_type && e.period_type !== 'Q' && (
                        <span className="rc-badge" title="Not a quarterly filing">
                          {e.period_type === 'H' ? 'half-yearly' : e.period_type}
                        </span>
                      )}
                      {e.period_confidence !== null && e.period_confidence < 60 && (
                        <span className="rc-badge rc-badge--warn" title="Period inferred from
                          the meeting date rather than stated in the filing">
                          inferred
                        </span>
                      )}
                    </td>

                    <td style={td}>
                      {formatDate(e.results_date)}
                      <div style={{ color: 'var(--textMuted)', fontSize: '0.8em' }}>
                        {relativeDay(e.results_date)}
                        {e.revision_count > 0 && (
                          <span title={`Moved from ${formatDate(e.first_intimated_date)}`}>
                            {' · '}revised
                          </span>
                        )}
                      </div>
                    </td>

                    <td style={tdNum}>
                      {e.lag_days === null ? '—' : `${e.lag_days}d`}
                    </td>

                    <td style={td}><ComparisonCell c={e.yoy} /></td>
                    <td style={td}><ComparisonCell c={e.qoq} /></td>

                    <td style={td}>
                      <span style={{ fontSize: '0.85em', color: 'var(--textMuted)' }}>
                        {e.announced_at
                          ? `${formatDate(e.announced_at.slice(0, 10))} (${Math.max(
                              0,
                              daysBetween(e.results_date, e.announced_at.slice(0, 10)),
                            )}d notice)`
                          : '—'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="rc-note">
            Dates are board-meeting intimations filed with NSE, so they are the company's stated
            plan and can move. “Lag” is days from period end to declaration; a negative delta
            means the company reported earlier than the comparison period. Q4 and annual results
            are audited and structurally take longer, so they are never compared against a
            quarter. Treat a single quarter's shift as weak evidence on its own — timing also
            moves for auditor scheduling and board availability.
          </p>
        </>
      )}
    </div>
  )
}
