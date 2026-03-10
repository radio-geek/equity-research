/** Report Type A: Dark dashboard — KPI strip, sections, charts and table. */
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ReportView } from '../api'
import { ConcallSection } from '../components/ConcallSection'
import { FlagsList } from '../components/FlagsList'
import { Section } from '../components/Section'
import { SectoralCard } from '../components/SectoralCard'
import { useAuth } from '../contexts/AuthContext'

const verdictTierStyles = {
  strong: { bg: 'var(--green)', label: '#047857', wrapBg: 'rgba(5, 150, 105, 0.12)', border: 'var(--green)' },
  average: { bg: '#d97706', label: '#b45309', wrapBg: 'rgba(217, 119, 6, 0.12)', border: '#d97706' },
  weak: { bg: 'var(--red)', label: '#b91c1c', wrapBg: 'rgba(220, 38, 38, 0.12)', border: 'var(--red)' },
} as const

function FinancialScorecard({ scorecard }: { scorecard: NonNullable<ReportView['financialScorecard']> }) {
  const tier = (scorecard.verdictTier ?? 'average') as keyof typeof verdictTierStyles
  const style = verdictTierStyles[tier] ?? verdictTierStyles.average
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 12, padding: '1.25rem 1.5rem', background: 'var(--surface)', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
      <p style={{ fontSize: '0.875rem', color: 'var(--textMuted)', margin: '0 0 1rem 0' }}>
        30-second health check across 6 core signals (TTM and YoY).
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '1.25rem', marginBottom: '1rem', paddingBottom: '1rem', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
          <span
            style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center', minWidth: 44, height: 44,
              fontSize: '1.5rem', fontWeight: 700, borderRadius: 10, background: style.bg, color: '#fff',
            }}
          >
            {scorecard.letterGrade ?? '—'}
          </span>
          <span style={{ fontSize: '1.125rem', fontWeight: 600, color: 'var(--text)' }}>
            {scorecard.score} / {scorecard.total}
          </span>
        </div>
        <div style={{ flex: 1, minWidth: 220, padding: '0.5rem 0.75rem', borderRadius: 8, background: style.wrapBg, borderLeft: `4px solid ${style.border}` }}>
          <span style={{ fontWeight: 600, fontSize: '0.9rem', color: style.label, marginRight: '0.35rem' }}>Verdict:</span>
          <span style={{ fontSize: '0.95rem', color: 'var(--text)' }}>{scorecard.verdict}</span>
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
        {scorecard.metrics?.map((m) => (
          <div
            key={m.name}
            style={{
              display: 'grid', gridTemplateColumns: '1fr auto auto auto', alignItems: 'center', gap: '0.75rem',
              padding: '0.5rem 0.6rem', borderRadius: 8, fontSize: '0.95rem',
              background: m.passed ? 'rgba(5, 150, 105, 0.08)' : 'rgba(220, 38, 38, 0.08)',
              borderLeft: `3px solid ${m.passed ? 'var(--green)' : 'var(--red)'}`,
            }}
          >
            <span style={{ fontWeight: 600, color: 'var(--text)' }}>{m.name}</span>
            <span style={{ color: 'var(--text)' }}>{m.display_value}</span>
            {m.signal && <span style={{ color: 'var(--textMuted)', fontSize: '0.85rem' }}>({m.signal})</span>}
            <span
              style={{
                fontSize: '0.8rem', fontWeight: 600, padding: '0.2rem 0.5rem', borderRadius: 6, justifySelf: 'end',
                background: m.passed ? 'var(--green)' : 'var(--red)', color: '#fff',
              }}
            >
              {m.passed ? 'Pass' : 'Needs improvement'}
            </span>
          </div>
        ))}
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
        <div
          className="report-markdown"
          style={{
            color: 'var(--text)',
            fontSize: '0.95rem',
          }}
        >
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {report.companyOverview ?? ''}
          </ReactMarkdown>
        </div>
      </Section>

      <Section title="Management & governance">
        <div
          className="report-markdown"
          style={{
            color: 'var(--text)',
            fontSize: '0.95rem',
          }}
        >
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {report.managementResearch ?? ''}
          </ReactMarkdown>
        </div>
      </Section>

      {report.auditorFlags != null && report.auditorFlags !== '' && (
        <Section title="Auditor flags & qualifications">
          <div
            className="report-markdown"
            style={{
              color: 'var(--text)',
              fontSize: '0.95rem',
              margin: 0,
            }}
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{report.auditorFlags}</ReactMarkdown>
          </div>
        </Section>
      )}

      {isAuthenticated ? (
        <>
          {report.financialScorecard && (
            <Section title="Financial Strength Scorecard">
              <FinancialScorecard scorecard={report.financialScorecard} />
            </Section>
          )}
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
          {report.financialScorecard && (
            <Section title="Financial Strength Scorecard">
              <FinancialScorecard scorecard={report.financialScorecard} />
            </Section>
          )}
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
