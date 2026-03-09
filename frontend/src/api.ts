const API_BASE = import.meta.env.VITE_API_URL ?? ''

// ── Auth helpers ──────────────────────────────────────────────────────────────

const TOKEN_KEY = 'er_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

function authHeaders(): Record<string, string> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export function loginWithGoogle(): void {
  const returnTo = window.location.pathname + window.location.search
  const params = new URLSearchParams()
  if (returnTo && returnTo !== '/') params.set('return_to', returnTo)
  const qs = params.toString()
  window.location.href = `${API_BASE}/auth/google${qs ? `?${qs}` : ''}`
}

export interface User {
  id: number
  email: string
  name: string | null
  picture: string | null
}

export async function getMe(): Promise<User | null> {
  const token = getToken()
  if (!token) return null
  const res = await fetch(`${API_BASE}/auth/me`, { headers: authHeaders() })
  if (!res.ok) {
    if (res.status === 401) clearToken()
    return null
  }
  return res.json()
}

export async function logout(): Promise<void> {
  await fetch(`${API_BASE}/auth/logout`, {
    method: 'POST',
    headers: authHeaders(),
  }).catch(() => {})
}

export interface SymbolSuggestion {
  symbol: string
  name: string
}

export async function suggest(query: string): Promise<SymbolSuggestion[]> {
  const q = encodeURIComponent(query.trim())
  const res = await fetch(`${API_BASE}/api/symbols/suggest?q=${q}`)
  if (!res.ok) return []
  const data = await res.json()
  return Array.isArray(data.symbols) ? data.symbols : []
}

export async function createReport(symbol: string, exchange: string = 'NSE'): Promise<{ report_id: string }> {
  const res = await fetch(`${API_BASE}/api/reports`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol, exchange }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json()
}

/** API report payload (snake_case from backend). */
export interface ReportPayload {
  meta?: {
    symbol?: string
    exchange?: string
    company_name?: string
    sector?: string
    industry?: string
  }
  company?: {
    meta?: unknown
    quote?: unknown
    shareholding?: unknown[]
    screener_quote?: { current_price?: number; price_change_pct?: string; market_cap?: string; last_price_updated?: string }
  }
  executive_summary?: string
  company_overview?: string
  management_research?: string
  financial_risk?: string
  auditor_flags?: string | null
  concall?: Record<string, unknown> | null
  sectoral?: {
    analysis?: string
    headwinds?: string[]
    tailwinds?: string[]
  }
  financials?: {
    ratios?: Array<{ metric?: string; value?: number | string; period?: string }>
    yearly_metrics?: Array<Record<string, number | string | null | undefined>>
    highlights?: { good?: string[]; bad?: string[] }
    financial_scorecard?: {
      score?: number
      total?: number
      verdict?: string
      verdict_tier?: 'strong' | 'average' | 'weak'
      letter_grade?: string
      metrics?: Array<{ name?: string; display_value?: string; passed?: boolean; signal?: string }>
    }
    five_year_trend?: { headers?: string[]; rows?: Array<{ metric?: string; unit?: string; cells?: string[] }> }
    trend_insight_summary?: string
  }
  generated_at?: string
}

/** View model for ReportA (camelCase). */
export interface ReportView {
  companyName: string
  symbol: string
  exchange: string
  sector: string
  companyOverview: string
  managementResearch: string
  financialRisk?: string
  auditorFlags?: string | null
  concall?: ReportPayload['concall']
  concallUpdates?: string
  yearlyMetrics?: Array<Record<string, number | string | null | undefined>>
  financialScorecard?: {
    score?: number
    total?: number
    verdict?: string
    verdictTier?: 'strong' | 'average' | 'weak'
    letterGrade?: string
    metrics?: Array<{ name?: string; display_value?: string; passed?: boolean; signal?: string }>
  }
  fiveYearTrend?: { headers?: string[]; rows?: Array<{ metric?: string; unit?: string; cells?: string[] }> }
  trendInsightSummary?: string
  sectoralHeadwinds?: string[]
  sectoralTailwinds?: string[]
  greenFlags?: string[]
  redFlags?: string[]
  screenerQuote?: { currentPrice?: number; priceChangePct?: string; marketCap?: string; lastPriceUpdated?: string }
}

export function mapReportPayloadToView(payload: ReportPayload | null | undefined): ReportView {
  const empty: ReportView = {
    companyName: '',
    symbol: '',
    exchange: 'NSE',
    sector: '',
    companyOverview: '',
    managementResearch: '',
  }
  if (!payload || typeof payload !== 'object') return empty
  const meta = payload.meta ?? {}
  const financials = payload.financials ?? {}
  const sectoral = payload.sectoral ?? {}
  const highlights = financials.highlights ?? {}
  return {
    companyName: meta.company_name ?? meta.symbol ?? '',
    symbol: meta.symbol ?? '',
    exchange: meta.exchange ?? 'NSE',
    sector: meta.sector ?? '',
    companyOverview: payload.company_overview ?? '',
    managementResearch: payload.management_research ?? '',
    financialRisk: payload.financial_risk,
    auditorFlags: payload.auditor_flags ?? undefined,
    concall: payload.concall ?? undefined,
    yearlyMetrics: financials.yearly_metrics ?? [],
    financialScorecard: financials.financial_scorecard
      ? {
          score: financials.financial_scorecard.score,
          total: financials.financial_scorecard.total,
          verdict: financials.financial_scorecard.verdict,
          verdictTier: financials.financial_scorecard.verdict_tier,
          letterGrade: financials.financial_scorecard.letter_grade,
          metrics: financials.financial_scorecard.metrics,
        }
      : undefined,
    fiveYearTrend: financials.five_year_trend,
    trendInsightSummary: financials.trend_insight_summary ?? undefined,
    sectoralHeadwinds: sectoral.headwinds ?? [],
    sectoralTailwinds: sectoral.tailwinds ?? [],
    greenFlags: highlights.good ?? [],
    redFlags: highlights.bad ?? [],
    screenerQuote: (() => {
      const sq = payload.company?.screener_quote
      if (!sq) return undefined
      return {
        currentPrice: sq.current_price,
        priceChangePct: sq.price_change_pct,
        marketCap: sq.market_cap,
        lastPriceUpdated: sq.last_price_updated,
      }
    })(),
  }
}

export interface ReportStatus {
  status: 'pending' | 'running' | 'completed' | 'failed'
  report?: ReportPayload
  from_cache?: boolean
  error?: string
}

export async function getReportStatus(reportId: string): Promise<ReportStatus> {
  const res = await fetch(`${API_BASE}/api/reports/${reportId}`, {
    headers: authHeaders(),
  })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export async function getReportPdfBlob(reportId: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/reports/${reportId}/pdf`, {
    headers: authHeaders(),
  })
  if (res.status === 401) {
    clearToken()
    throw new Error('Unauthorized')
  }
  if (!res.ok) throw new Error(res.statusText)
  return res.blob()
}

export interface FeedbackRequest {
  report_id: string
  rating: 'up' | 'down'
  comment?: string | null
}

export async function submitFeedback(body: FeedbackRequest): Promise<{ ok: boolean }> {
  const res = await fetch(`${API_BASE}/api/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json()
}
