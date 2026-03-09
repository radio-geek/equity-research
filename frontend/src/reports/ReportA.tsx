/** Report Type A: Dark dashboard — KPI strip, sections, charts and table. */
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ReportView } from '../api'
import { useAuth } from '../contexts/AuthContext'
import { Section } from '../components/Section'
import { FinancialTable } from '../components/FinancialTable'
import { FinancialCharts } from '../components/FinancialCharts'
import { SectoralCard } from '../components/SectoralCard'
import { FlagsList } from '../components/FlagsList'
import { ConcallSection } from '../components/ConcallSection'

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
  const kpis = ttm
    ? [
        { label: 'ROE', value: `${ttm.roe ?? '—'}%`, trend: ttm.roe_yoy_pct != null ? Number(ttm.roe_yoy_pct) : undefined, lowerIsBetter: false },
        { label: 'ROCE', value: `${ttm.roce ?? '—'}%`, trend: ttm.roce_yoy_pct != null ? Number(ttm.roce_yoy_pct) : undefined, lowerIsBetter: false },
        { label: 'D/E', value: ttm.debt_equity != null ? Number(ttm.debt_equity).toFixed(2) : '—', trend: ttm.debt_equity_yoy_pct != null ? Number(ttm.debt_equity_yoy_pct) : undefined, lowerIsBetter: true },
        { label: 'CFO (Cr)', value: String(ttm.cfo_cr ?? '—'), trend: ttm.cfo_yoy_pct != null ? Number(ttm.cfo_yoy_pct) : undefined, lowerIsBetter: false },
        { label: 'EBITDA (Cr)', value: String(ttm.ebitda_cr ?? '—'), trend: ttm.ebitda_yoy_pct != null ? Number(ttm.ebitda_yoy_pct) : undefined, lowerIsBetter: false },
        { label: 'PAT (Cr)', value: String(ttm.pat_cr ?? '—'), trend: ttm.pat_yoy_pct != null ? Number(ttm.pat_yoy_pct) : undefined, lowerIsBetter: false },
      ]
    : []

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '2rem', fontFamily: 'var(--font)' }}>
      <header style={{ marginBottom: '2rem', borderBottom: '1px solid var(--border)', paddingBottom: '1.5rem' }}>
        <div style={{ fontSize: '0.875rem', color: 'var(--textMuted)' }}>{report.exchange} · {report.sector}</div>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: '0.25rem 0' }}>{report.companyName}</h1>
        <div style={{ fontSize: '0.9rem', color: 'var(--accent)' }}>{report.symbol}</div>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '0.75rem', marginBottom: '2rem' }}>
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
        <p style={{ margin: 0, color: 'var(--text)', fontSize: '0.95rem' }}>{report.managementResearch}</p>
      </Section>

      {report.auditorFlags != null && report.auditorFlags !== '' && (
        <Section title="Auditor flags & qualifications">
          <p style={{ margin: 0, color: 'var(--text)', fontSize: '0.95rem' }}>{report.auditorFlags}</p>
        </Section>
      )}

      {isAuthenticated ? (
        <>
          <Section title="Financial data (YoY & TTM)">
            <FinancialCharts report={report} height={240} />
            <div style={{ marginTop: '1.5rem' }}>
              <FinancialTable report={report} />
            </div>
          </Section>
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
          <Section title="Financial data (YoY & TTM)">
            <FinancialCharts report={report} height={240} />
            <div style={{ marginTop: '1.5rem' }}>
              <FinancialTable report={report} />
            </div>
          </Section>
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
