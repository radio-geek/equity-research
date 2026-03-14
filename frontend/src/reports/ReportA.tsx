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

const auditTypeBadgeBg: Record<string, string> = {
  'qualified opinion': '#b71c1c',
  'emphasis of matter': '#e65100',
  'going concern': '#4a148c',
  caro: '#1565c0',
  'secretarial audit': '#004d40',
  'auditor change': '#880e4f',
}

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

function AuditorTimelineView({ summary, events }: { summary?: string; events: AuditorEvent[] }) {
  return (
    <div style={{ color: 'var(--text)', fontSize: '0.95rem' }}>
      {summary ? <p style={{ margin: '0 0 1rem 0', fontWeight: 600, color: 'var(--textMuted)' }}>{summary}</p> : null}
      <div style={{ borderLeft: '3px solid var(--border)', paddingLeft: '1.2rem', marginLeft: 2 }}>
        {events.map((ev, i) => {
          const typeKey = (ev.type ?? 'other').toLowerCase()
          const badgeBg = auditTypeBadgeBg[typeKey] ?? '#546e7a'
          const isRed = ev.isRedFlag === true
          return (
            <div
              key={i}
              style={{
                marginBottom: '1rem',
                padding: '10px 12px',
                background: isRed ? 'rgba(198, 40, 40, 0.08)' : 'var(--surface)',
                borderLeft: `4px solid ${isRed ? '#c62828' : 'var(--border)'}`,
                borderRadius: 6,
              }}
            >
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--textMuted)' }}>
                  {auditEventDateLabel(ev.fy, ev.date)}
                </span>
                <span
                  style={{
                    display: 'inline-block',
                    padding: '2px 8px',
                    borderRadius: 10,
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    color: '#fff',
                    background: badgeBg,
                    textTransform: 'uppercase',
                  }}
                >
                  {ev.type ?? 'Other'}
                </span>
                {ev.status ? (
                  <span
                    style={{
                      fontSize: '0.7rem',
                      padding: '2px 6px',
                      borderRadius: 6,
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      marginLeft: 'auto',
                      background: ev.status === 'Resolved' ? 'rgba(5, 150, 105, 0.2)' : ev.status === 'Pending' ? 'rgba(255, 111, 0, 0.25)' : 'rgba(183, 28, 28, 0.2)',
                      color: ev.status === 'Resolved' ? '#047857' : ev.status === 'Pending' ? '#e65100' : '#b71c1c',
                    }}
                  >
                    {ev.status}
                  </span>
                ) : null}
              </div>
              <p style={{ margin: 0, fontSize: '0.9rem', lineHeight: 1.4 }}>{ev.issue ?? '—'}</p>
              {ev.managementResponse ? (
                <p style={{ margin: '4px 0 0 0', fontSize: '0.85rem', color: 'var(--textMuted)', fontStyle: 'italic' }}>
                  {ev.managementResponse}
                </p>
              ) : null}
            </div>
          )
        })}
      </div>
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

export function ReportA({ report }: ReportAProps) {
  const { isAuthenticated, signIn } = useAuth()
  const ttm = report.yearlyMetrics?.find((m) => m.period_label === 'TTM') ?? report.yearlyMetrics?.[report.yearlyMetrics.length - 1]
  const sq = report.screenerQuote
  const kpis = ttm
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

      <Section title="Company overview">
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

      <Section title="Management & governance">
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
            style={{ color: 'var(--text)', fontSize: '0.95rem', marginBottom: report.managementGovernanceNews?.length ? '1.25rem' : 0 }}
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{report.managementResearch}</ReactMarkdown>
          </div>
        ) : null}
        {report.managementGovernanceNews?.length ? (
          <>
            <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.75rem', color: 'var(--text)' }}>Governance news</h2>
            <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
              {report.managementGovernanceNews.map((n, i) => (
                <li
                  key={i}
                  style={{
                    padding: '0.5rem 0.65rem',
                    marginBottom: '0.5rem',
                    borderRadius: 6,
                    borderLeft: `4px solid ${n.sentiment === 'positive' ? 'var(--green)' : n.sentiment === 'negative' ? 'var(--red)' : 'var(--border)'}`,
                    background: 'var(--surface)',
                    fontSize: '0.9rem',
                    lineHeight: 1.45,
                  }}
                >
                  {n.sentiment && n.sentiment !== 'neutral' ? (
                    <span
                      style={{
                        display: 'inline-block',
                        padding: '2px 8px',
                        borderRadius: 10,
                        fontSize: '0.7rem',
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        marginRight: '0.5rem',
                        background: n.sentiment === 'positive' ? 'rgba(5, 150, 105, 0.2)' : 'rgba(220, 38, 38, 0.2)',
                        color: n.sentiment === 'positive' ? 'var(--green)' : 'var(--red)',
                      }}
                    >
                      {n.sentiment}
                    </span>
                  ) : null}
                  {n.text ?? '—'}
                </li>
              ))}
            </ul>
          </>
        ) : null}
        {!report.managementPeople?.length && !report.managementResearch && !report.managementGovernanceNews?.length ? (
          <p style={{ color: 'var(--textMuted)', fontSize: '0.95rem' }}>No management & governance data available.</p>
        ) : null}
      </Section>

      {(() => {
        const af = report.auditorFlagsStructured
        const hasTimeline = (af?.events?.length ?? 0) > 0
        return hasTimeline && af ? (
          <Section title="Auditor flags & qualifications">
            <AuditorTimelineView summary={af.summary} events={af.events ?? []} />
          </Section>
        ) : report.auditorFlags != null && report.auditorFlags !== '' ? (
          <Section title="Auditor flags & qualifications">
            <div className="report-markdown" style={{ color: 'var(--text)', fontSize: '0.95rem', margin: 0 }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{report.auditorFlags}</ReactMarkdown>
            </div>
          </Section>
        ) : null
      })()}

      {isAuthenticated ? (
        <>
          {report.fiveYearTrend?.headers?.length ? (
            <Section title="5-Year Financial Trend">
              <p style={{ fontSize: '0.9rem', color: 'var(--textMuted)', marginBottom: '1rem' }}>
                Latest 5 completed financial years. Values in ₹ Crores unless noted.
              </p>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--fontMono)', fontSize: '0.875rem' }}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)', color: 'var(--textMuted)' }}>Metric</th>
                      <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)', color: 'var(--textMuted)' }}>Unit</th>
                      {report.fiveYearTrend.headers.map((h) => (
                        <th key={h} style={{ textAlign: 'right', padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)', color: 'var(--textMuted)' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {report.fiveYearTrend.rows?.map((row, ri) => (
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
          <ConcallSection concall={report.concall ?? null} concallUpdatesFallback={report.concallUpdates} />
          <Section title="Sectoral headwinds & tailwinds">
            <SectoralCard headwinds={report.sectoralHeadwinds} tailwinds={report.sectoralTailwinds} />
          </Section>
          <Section title="Green & red flags in financial data">
            <FlagsList greenFlags={report.greenFlags} redFlags={report.redFlags} />
          </Section>
        </>
      ) : (
        <>
          {report.fiveYearTrend?.headers?.length ? (
            <Section title="5-Year Financial Trend">
              <p style={{ fontSize: '0.9rem', color: 'var(--textMuted)', marginBottom: '1rem' }}>
                Latest 5 completed financial years. Values in ₹ Crores unless noted.
              </p>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--fontMono)', fontSize: '0.875rem' }}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)', color: 'var(--textMuted)' }}>Metric</th>
                      <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)', color: 'var(--textMuted)' }}>Unit</th>
                      {report.fiveYearTrend.headers.map((h) => (
                        <th key={h} style={{ textAlign: 'right', padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)', color: 'var(--textMuted)' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {report.fiveYearTrend.rows?.map((row, ri) => (
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
          <Section title="Concall evaluation">
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
          <Section title="Sectoral headwinds & tailwinds">
            <div className="report-gated-wrap">
              <div className="report-gated-blur" aria-hidden>
                <SectoralCard headwinds={report.sectoralHeadwinds} tailwinds={report.sectoralTailwinds} />
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
          <Section title="Green & red flags in financial data">
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
