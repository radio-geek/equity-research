/** Report Type A: Dark dashboard — KPI strip, sections, charts and table. */
import type { ReportView } from '../api'
import { Section } from '../components/Section'
import { FinancialTable } from '../components/FinancialTable'
import { FinancialCharts } from '../components/FinancialCharts'
import { SectoralCard } from '../components/SectoralCard'
import { FlagsList } from '../components/FlagsList'
import { ConcallSection } from '../components/ConcallSection'

interface ReportAProps {
  report: ReportView
}

export function ReportA({ report }: ReportAProps) {
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
        <p style={{ margin: 0, color: 'var(--text)', fontSize: '0.95rem' }}>{report.companyOverview}</p>
      </Section>

      <Section title="Management & governance">
        <p style={{ margin: 0, color: 'var(--text)', fontSize: '0.95rem' }}>{report.managementResearch}</p>
      </Section>

      {report.auditorFlags != null && report.auditorFlags !== '' && (
        <Section title="Auditor flags & qualifications">
          <p style={{ margin: 0, color: 'var(--text)', fontSize: '0.95rem' }}>{report.auditorFlags}</p>
        </Section>
      )}

      <ConcallSection concall={report.concall ?? null} concallUpdatesFallback={report.concallUpdates} />

      <Section title="Financial data (YoY & TTM)">
        <FinancialCharts report={report} height={240} />
        <div style={{ marginTop: '1.5rem' }}>
          <FinancialTable report={report} />
        </div>
      </Section>

      <Section title="Sectoral headwinds & tailwinds">
        <SectoralCard headwinds={report.sectoralHeadwinds} tailwinds={report.sectoralTailwinds} />
      </Section>

      <Section title="Green & red flags in financial data">
        <FlagsList greenFlags={report.greenFlags} redFlags={report.redFlags} />
      </Section>
    </div>
  )
}
