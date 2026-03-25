/** Report Type A: Dark dashboard — KPI strip, sections, charts and table. */
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ReportView } from '../api'
import { ConcallSection } from '../components/ConcallSection'
import { FlagsList } from '../components/FlagsList'
import { OverviewTimeline } from '../components/OverviewTimeline'
import { Section } from '../components/Section'
import { SectoralCard } from '../components/SectoralCard'
import { ValueChainFlowchart } from '../components/ValueChainFlowchart'
import { useAuth } from '../contexts/AuthContext'

function auditEventDateLabel(fy: string | undefined, date: string | undefined): string {
  if (!date) return fy ?? '—'
  if (date.length >= 7 && date[4] === '-') {
    const months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    const y = date.slice(0, 4)
    const m = parseInt(date.slice(5, 7), 10)
    if (m >= 1 && m <= 12) return `${fy ?? ''} · ${months[m]} ${y}`.trim()
  }
  return `${fy ?? ''} · ${date}`.trim() || '—'
}

type AuditorEvent = NonNullable<NonNullable<ReportView['auditorFlagsStructured']>['events']>[number]

const SIGNAL_META: Record<string, { label: string; color: string; bg: string; border: string }> = {
  red:    { label: 'RISK',   color: '#c62828', bg: 'rgba(198, 40, 40, 0.08)',   border: '#c62828' },
  yellow: { label: 'OK',     color: '#e65100', bg: 'rgba(239, 108, 0, 0.06)',   border: '#ef6c00' },
  green:  { label: 'GOOD',   color: '#047857', bg: 'rgba(5, 150, 105, 0.06)',   border: '#059669' },
}

const VERDICT_META: Record<string, { label: string; color: string; bg: string }> = {
  RISK: { label: 'RISK', color: '#fff', bg: '#c62828' },
  OK:   { label: 'OK',   color: '#fff', bg: '#e65100' },
  GOOD: { label: 'GOOD', color: '#fff', bg: '#059669' },
}

function AuditorTimelineView({ verdict, summary, events }: { verdict?: string; summary?: string; events: AuditorEvent[] }) {
  const v = VERDICT_META[(verdict ?? 'OK').toUpperCase()] ?? VERDICT_META.OK

  return (
    <div style={{ color: 'var(--text)', fontSize: '0.95rem' }}>
      {/* Verdict badge + summary */}
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 14,
          marginBottom: events.length ? '1.25rem' : 0,
          padding: '14px 16px',
          background: 'var(--surface)',
          borderRadius: 10,
        }}
      >
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '6px 18px',
            borderRadius: 8,
            fontSize: '0.85rem',
            fontWeight: 800,
            letterSpacing: '0.06em',
            color: v.color,
            background: v.bg,
            flexShrink: 0,
            marginTop: 2,
          }}
        >
          {v.label}
        </span>
        <p style={{ margin: 0, fontSize: '0.9rem', lineHeight: 1.55, color: 'var(--textMuted)' }}>
          {summary || 'No governance issues found.'}
        </p>
      </div>

      {/* Event cards */}
      {events.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
          {events.map((ev, i) => {
            const sig = SIGNAL_META[(ev.signal ?? 'yellow').toLowerCase()] ?? SIGNAL_META.yellow
            return (
              <div
                key={i}
                style={{
                  padding: '14px 16px',
                  background: sig.bg,
                  borderLeft: `4px solid ${sig.border}`,
                  borderRadius: 8,
                }}
              >
                {/* Header row: signal tag + category + date + status */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
                  <span
                    style={{
                      display: 'inline-block',
                      padding: '2px 10px',
                      borderRadius: 10,
                      fontSize: '0.65rem',
                      fontWeight: 800,
                      letterSpacing: '0.05em',
                      textTransform: 'uppercase',
                      color: '#fff',
                      background: sig.border,
                    }}
                  >
                    {sig.label}
                  </span>
                  {ev.category && (
                    <span style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text)' }}>
                      {ev.category}
                    </span>
                  )}
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--textMuted)', fontFamily: 'var(--fontMono)', marginLeft: 'auto' }}>
                    {auditEventDateLabel(ev.fy, ev.date)}
                  </span>
                  {ev.status && (
                    <span
                      style={{
                        fontSize: '0.65rem',
                        padding: '2px 8px',
                        borderRadius: 10,
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        background: ev.status === 'Resolved' ? 'rgba(5, 150, 105, 0.15)' : ev.status === 'Pending' ? 'rgba(255, 111, 0, 0.15)' : 'rgba(183, 28, 28, 0.15)',
                        color: ev.status === 'Resolved' ? '#047857' : ev.status === 'Pending' ? '#e65100' : '#b71c1c',
                      }}
                    >
                      {ev.status}
                    </span>
                  )}
                </div>

                {/* Type label */}
                {ev.type && ev.type !== 'Other' && (
                  <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--textMuted)', textTransform: 'uppercase', letterSpacing: '0.03em', marginBottom: 4 }}>
                    {ev.type}
                  </div>
                )}

                {/* Issue text */}
                <p style={{ margin: 0, fontSize: '0.9rem', lineHeight: 1.5, color: 'var(--text)' }}>{ev.issue ?? '—'}</p>

                {/* Evidence quote */}
                {ev.evidence && (
                  <div
                    style={{
                      margin: '10px 0 0 0',
                      padding: '8px 12px',
                      borderLeft: '3px solid var(--border)',
                      background: 'rgba(255,255,255,0.04)',
                      borderRadius: 4,
                      fontSize: '0.82rem',
                      lineHeight: 1.4,
                      color: 'var(--textMuted)',
                      fontStyle: 'italic',
                    }}
                  >
                    "{ev.evidence}"
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function LockIcon() {
  return (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  )
}

interface ReportAProps {
  report: ReportView
}

/** Key metrics strip order (from Screener): Stock P/E, Market Cap, ROCE %, ROE %, Debt/Equity, PAT Margin %, EBITDA Margin % */
const KEY_METRIC_KEYS: Array<{ key: string; label: string }> = [
  { key: 'pe', label: 'Stock P/E' },
  { key: 'market_cap', label: 'Market Cap' },
  { key: 'roce', label: 'ROCE %' },
  { key: 'roe', label: 'ROE %' },
  { key: 'debt_equity', label: 'Debt/Equity' },
  { key: 'pat_margin', label: 'PAT Margin %' },
  { key: 'ebitda_margin', label: 'EBITDA Margin %' },
]

/** 5-year trend: prefer mapped view, fallback to raw payload financials (e.g. if mapper missed it). */
function getFiveYearTrend(report: ReportView): ReportView['fiveYearTrend'] {
  if (report.fiveYearTrend?.headers?.length) return report.fiveYearTrend
  const raw = (report as ReportView & { financials?: { five_year_trend?: ReportView['fiveYearTrend'] } }).financials?.five_year_trend
  if (raw?.headers?.length && Array.isArray(raw.rows)) return raw
  return report.fiveYearTrend ?? undefined
}

export function ReportA({ report }: ReportAProps) {
  const { isAuthenticated, signIn } = useAuth()
  const fiveYearTrend = getFiveYearTrend(report)
  const ttm = report.yearlyMetrics?.find((m) => m.period_label === 'TTM') ?? report.yearlyMetrics?.[report.yearlyMetrics.length - 1]
  const sq = report.screenerQuote
  const keyMetrics = report.keyMetrics
  const kpis =
    keyMetrics && Object.keys(keyMetrics).length > 0
      ? KEY_METRIC_KEYS.filter(({ key }) => keyMetrics[key] != null && keyMetrics[key] !== '')
          .map(({ key, label }) => ({ label, value: keyMetrics[key]!, trend: undefined as number | undefined, lowerIsBetter: false }))
      : ttm
        ? [
            { label: 'ROE', value: `${ttm.roe ?? '—'}%`, trend: ttm.roe_yoy_pct != null ? Number(ttm.roe_yoy_pct) : undefined, lowerIsBetter: false },
            { label: 'ROCE', value: `${ttm.roce ?? '—'}%`, trend: ttm.roce_yoy_pct != null ? Number(ttm.roce_yoy_pct) : undefined, lowerIsBetter: false },
            { label: 'D/E', value: ttm.debt_equity != null ? Number(ttm.debt_equity).toFixed(2) : '—', trend: ttm.debt_equity_yoy_pct != null ? Number(ttm.debt_equity_yoy_pct) : undefined, lowerIsBetter: true },
            { label: 'CFO (Cr)', value: String(ttm.cfo_cr ?? '—'), trend: ttm.cfo_yoy_pct != null ? Number(ttm.cfo_yoy_pct) : undefined, lowerIsBetter: false },
            { label: 'EBITDA (Cr)', value: String(ttm.ebitda_cr ?? '—'), trend: ttm.ebitda_yoy_pct != null ? Number(ttm.ebitda_yoy_pct) : undefined, lowerIsBetter: false },
            { label: 'PAT (Cr)', value: String(ttm.pat_cr ?? '—'), trend: ttm.pat_yoy_pct != null ? Number(ttm.pat_yoy_pct) : undefined, lowerIsBetter: false },
            ...(sq?.marketCap != null && sq.marketCap !== '' ? [{ label: 'Market Cap', value: sq.marketCap, trend: undefined as number | undefined, lowerIsBetter: false }] : []),
          ]
        : []

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '2rem', fontFamily: 'var(--font)' }}>
      <header style={{ marginBottom: '2rem', borderBottom: '1px solid var(--border)', paddingBottom: '1.5rem' }}>
        <div style={{ fontSize: '0.875rem', color: 'var(--textMuted)' }}>{report.exchange} · {report.sector}</div>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: '0.25rem 0', color: 'var(--text)', display: 'flex', alignItems: 'baseline', flexWrap: 'wrap', gap: '0.5rem' }}>
          {report.companyName}
          {sq?.currentPrice != null && (
            <>
              <span style={{ fontWeight: 600, color: 'var(--text)', marginLeft: '0.35rem' }}>
                ₹ {sq.currentPrice.toLocaleString('en-IN')}
              </span>
              {sq?.priceChangePct && (
                <span
                  style={{
                    fontSize: '0.9em',
                    fontWeight: 600,
                    marginLeft: '0.25rem',
                    color: sq.priceChangePct.startsWith('-') ? 'var(--red)' : 'var(--green)',
                  }}
                >
                  {sq.priceChangePct}
                </span>
              )}
            </>
          )}
        </h1>
        <div style={{ display: 'flex', alignItems: 'baseline', flexWrap: 'wrap', gap: '0.5rem' }}>
          <span style={{ fontSize: '0.9rem', color: 'var(--accent)' }}>{report.symbol}</span>
          {sq?.lastPriceUpdated && (
            <span style={{ fontSize: '0.85rem', color: 'var(--textMuted)' }}> · {sq.lastPriceUpdated}</span>
          )}
        </div>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${kpis.length}, 1fr)`, gap: '0.75rem', marginBottom: '2rem' }}>
        {kpis.map((k) => (
          <div key={k.label} style={{ background: 'var(--surface)', borderRadius: 8, padding: '1rem', border: '1px solid var(--border)', textAlign: 'center' }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--textMuted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{k.label}</div>
            <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>{k.value}</div>
            {k.trend != null && (() => {
              const good = k.lowerIsBetter ? k.trend < 0 : k.trend >= 0
              return (
                <span style={{ color: good ? 'var(--green)' : 'var(--red)', fontSize: '0.8rem' }}>{k.trend >= 0 ? '+' : ''}{k.trend?.toFixed(1)}% YoY</span>
              )
            })()}
          </div>
        ))}
      </div>

      <Section title="Company overview" id="section-overview">
        {report.companyOverviewStructured ? (
          <div
            style={{
              color: 'var(--text)',
              fontSize: '0.95rem',
              lineHeight: 1.6,
              padding: '0.5rem 0',
            }}
          >
            {report.companyOverviewStructured.opening && (
              <p style={{ marginBottom: '2rem', lineHeight: 1.65 }}>
                {report.companyOverviewStructured.opening}
              </p>
            )}
            {report.companyOverviewStructured.valueChain?.stages?.length ? (
              <div style={{ marginBottom: '2.5rem' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.75rem', marginTop: 0, color: 'var(--text)' }}>
                  Industry value chain
                </h3>
                <ValueChainFlowchart
                  stages={report.companyOverviewStructured.valueChain.stages}
                  companyStageIndex={report.companyOverviewStructured.valueChain.companyStageIndex}
                  companyStageIndices={report.companyOverviewStructured.valueChain.companyStageIndices}
                  companyPosition={report.companyOverviewStructured.valueChain.companyPosition}
                  companyPositionDescription={report.companyOverviewStructured.valueChain.companyPositionDescription}
                />
              </div>
            ) : null}
            {report.companyOverviewStructured.businessModelTable?.rows?.length ? (
              <div style={{ marginBottom: '2.5rem' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.75rem', marginTop: 0, color: 'var(--text)' }}>
                  Business model & revenue drivers
                </h3>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--fontMono)', fontSize: '0.875rem' }}>
                    <thead>
                      <tr>
                        <th style={{ textAlign: 'left', padding: '0.75rem 1rem', borderBottom: '2px solid var(--border)', color: 'var(--textMuted)' }}>Segment</th>
                        <th style={{ textAlign: 'left', padding: '0.75rem 1rem', borderBottom: '2px solid var(--border)', color: 'var(--textMuted)' }}>Importance</th>
                        <th style={{ textAlign: 'left', padding: '0.75rem 1rem', borderBottom: '2px solid var(--border)', color: 'var(--textMuted)' }}>Description</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.companyOverviewStructured.businessModelTable.rows.map((row, ri) => (
                        <tr key={ri}>
                          <td style={{ padding: '0.75rem 1rem', borderBottom: '1px solid var(--border)', verticalAlign: 'top' }}>{row.segment}</td>
                          <td style={{ padding: '0.75rem 1rem', borderBottom: '1px solid var(--border)', verticalAlign: 'top' }}>{row.importance}</td>
                          <td style={{ padding: '0.75rem 1rem', borderBottom: '1px solid var(--border)', verticalAlign: 'top', lineHeight: 1.5 }}>{row.description}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}
            {report.companyOverviewStructured.keyProducts?.length ? (
              <div style={{ marginBottom: '2.5rem' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.75rem', marginTop: 0, color: 'var(--text)' }}>
                  Key products / services
                </h3>
                <ul style={{ margin: 0, paddingLeft: '1.5rem', listStyleType: 'disc' }}>
                  {report.companyOverviewStructured.keyProducts.map((p, i) => (
                    <li key={i} style={{ marginBottom: '0.5rem', lineHeight: 1.5 }}>{p}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {report.companyOverviewStructured.recentDevelopments?.length ? (
              <div style={{ marginBottom: 0 }}>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.75rem', marginTop: 0, color: 'var(--text)' }}>
                  Recent developments & milestones
                </h3>
                <OverviewTimeline items={report.companyOverviewStructured.recentDevelopments} />
              </div>
            ) : null}
          </div>
        ) : (
          <div className="report-markdown" style={{ color: 'var(--text)', fontSize: '0.95rem' }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {report.companyOverview ?? ''}
            </ReactMarkdown>
          </div>
        )}
      </Section>

      <Section title="Management & board" id="section-management">
        {report.managementPeople?.length ? (
          <>
            <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.75rem', color: 'var(--text)' }}>Promoter & Board</h2>
            <div style={{ overflowX: 'auto', marginBottom: '1.25rem' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--fontMono)', fontSize: '0.875rem' }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)', color: 'var(--textMuted)' }}>Name</th>
                    <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)', color: 'var(--textMuted)' }}>Designation</th>
                    <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)', color: 'var(--textMuted)' }}>Description</th>
                  </tr>
                </thead>
                <tbody>
                  {report.managementPeople.map((p, i) => (
                    <tr key={i}>
                      <td
                        className="management-people-name"
                        style={{
                          padding: '0.5rem 0.75rem',
                          borderBottom: '1px solid var(--border)',
                          fontWeight: 700,
                          color: 'var(--accent, #0f766e)',
                          background: 'rgba(15, 118, 110, 0.08)',
                          width: '12em',
                          verticalAlign: 'top',
                        }}
                      >
                        {p.name ?? '—'}
                      </td>
                      <td style={{ padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)' }}>{p.designation ?? '—'}</td>
                      <td style={{ padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)', maxWidth: '50%' }}>{p.description ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : null}
        {report.managementResearch ? (
          <div
            className="report-markdown"
            style={{ color: 'var(--text)', fontSize: '0.95rem' }}
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{report.managementResearch}</ReactMarkdown>
          </div>
        ) : null}
        {!report.managementPeople?.length && !report.managementResearch ? (
          <p style={{ color: 'var(--textMuted)', fontSize: '0.95rem' }}>No management data available.</p>
        ) : null}
      </Section>

      {(() => {
        const af = report.auditorFlagsStructured
        const hasStructuredBody =
          !!af &&
          (((af.events?.length ?? 0) > 0) || !!(af.summary && String(af.summary).trim()) || !!af.verdict)
        return hasStructuredBody && af ? (
          <Section title="Governance & auditor review" id="section-auditor">
            <AuditorTimelineView verdict={af.verdict} summary={af.summary} events={af.events ?? []} />
          </Section>
        ) : report.auditorFlags != null && report.auditorFlags !== '' ? (
          <Section title="Governance & auditor review" id="section-auditor">
            <div className="report-markdown" style={{ color: 'var(--text)', fontSize: '0.95rem', margin: 0 }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{report.auditorFlags}</ReactMarkdown>
            </div>
          </Section>
        ) : null
      })()}

      {isAuthenticated ? (
        <>
          {fiveYearTrend?.headers?.length ? (
            <Section title="5-Year Financial Trend" id="section-financials">
              <p style={{ fontSize: '0.9rem', color: 'var(--textMuted)', marginBottom: '1rem' }}>
                Latest 5 completed financial years. Values in ₹ Crores unless noted.
              </p>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--fontMono)', fontSize: '0.875rem' }}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)', color: 'var(--textMuted)' }}>Metric</th>
                      <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)', color: 'var(--textMuted)' }}>Unit</th>
                      {fiveYearTrend.headers.map((h) => (
                        <th key={h} style={{ textAlign: 'right', padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)', color: 'var(--textMuted)' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {fiveYearTrend.rows?.map((row, ri) => (
                      <tr key={ri}>
                        <td style={{ padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)' }}>{row.metric}</td>
                        <td style={{ padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)', color: 'var(--textMuted)' }}>{row.unit}</td>
                        {row.cells?.map((cell, ci) => (
                          <td key={ci} style={{ textAlign: 'right', padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)' }}>{cell}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {report.trendInsightSummary && (
                <p style={{ marginTop: '1rem', padding: '0.6rem 0.8rem', background: 'var(--surface)', borderLeft: '4px solid var(--accent)', borderRadius: 4, fontSize: '0.95rem' }}>
                  {report.trendInsightSummary}
                </p>
              )}
            </Section>
          ) : null}
          <div id="section-concall">
            <ConcallSection concall={report.concall ?? null} concallUpdatesFallback={report.concallUpdates} />
          </div>
          <Section title="Sectoral headwinds & tailwinds" id="section-sectoral">
            <SectoralCard headwinds={report.sectoralHeadwinds} tailwinds={report.sectoralTailwinds} source={report.sectoralSource} />
          </Section>
          <Section title="Green & red flags in financial data" id="section-flags">
            <FlagsList greenFlags={report.greenFlags} redFlags={report.redFlags} />
          </Section>
        </>
      ) : (
        <>
          {fiveYearTrend?.headers?.length ? (
            <Section title="5-Year Financial Trend" id="section-financials">
              <p style={{ fontSize: '0.9rem', color: 'var(--textMuted)', marginBottom: '1rem' }}>
                Latest 5 completed financial years. Values in ₹ Crores unless noted.
              </p>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--fontMono)', fontSize: '0.875rem' }}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)', color: 'var(--textMuted)' }}>Metric</th>
                      <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)', color: 'var(--textMuted)' }}>Unit</th>
                      {fiveYearTrend.headers.map((h) => (
                        <th key={h} style={{ textAlign: 'right', padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)', color: 'var(--textMuted)' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {fiveYearTrend.rows?.map((row, ri) => (
                      <tr key={ri}>
                        <td style={{ padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)' }}>{row.metric}</td>
                        <td style={{ padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)', color: 'var(--textMuted)' }}>{row.unit}</td>
                        {row.cells?.map((cell, ci) => (
                          <td key={ci} style={{ textAlign: 'right', padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)' }}>{cell}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {report.trendInsightSummary && (
                <p style={{ marginTop: '1rem', padding: '0.6rem 0.8rem', background: 'var(--surface)', borderLeft: '4px solid var(--accent)', borderRadius: 4, fontSize: '0.95rem' }}>
                  {report.trendInsightSummary}
                </p>
              )}
            </Section>
          ) : null}
          <Section title="Concall evaluation" id="section-concall">
            <div className="report-gated-wrap">
              <div className="report-gated-blur" aria-hidden>
                <ConcallSection concall={report.concall ?? null} concallUpdatesFallback={report.concallUpdates} />
              </div>
              <div className="report-gated-overlay">
                <span className="report-gated-lock" aria-hidden>
                  <LockIcon />
                </span>
                <p className="report-gated-text">Sign in to view concall evaluation.</p>
                <button type="button" className="report-download-btn report-gated-btn" onClick={signIn}>
                  Sign in
                </button>
              </div>
            </div>
          </Section>
          <Section title="Sectoral headwinds & tailwinds" id="section-sectoral">
            <div className="report-gated-wrap">
              <div className="report-gated-blur" aria-hidden>
                <SectoralCard headwinds={report.sectoralHeadwinds} tailwinds={report.sectoralTailwinds} source={report.sectoralSource} />
              </div>
              <div className="report-gated-overlay">
                <span className="report-gated-lock" aria-hidden>
                  <LockIcon />
                </span>
                <p className="report-gated-text">Sign in to view sectoral headwinds & tailwinds.</p>
                <button type="button" className="report-download-btn report-gated-btn" onClick={signIn}>
                  Sign in
                </button>
              </div>
            </div>
          </Section>
          <Section title="Green & red flags in financial data" id="section-flags">
            <div className="report-gated-wrap">
              <div className="report-gated-blur" aria-hidden>
                <FlagsList greenFlags={report.greenFlags} redFlags={report.redFlags} />
              </div>
              <div className="report-gated-overlay">
                <span className="report-gated-lock" aria-hidden>
                  <LockIcon />
                </span>
                <p className="report-gated-text">Sign in to view green & red flags in financial data.</p>
                <button type="button" className="report-download-btn report-gated-btn" onClick={signIn}>
                  Sign in
                </button>
              </div>
            </div>
          </Section>
        </>
      )}
    </div>
  )
}
