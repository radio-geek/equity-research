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
  company_overview_structured?: {
    opening?: string
    value_chain?: {
      stages?: string[]
      company_position?: string
      company_stage_index?: number
      company_stage_indices?: number[]
      company_position_description?: string
    }
    business_model_table?: { rows?: Array<{ segment?: string; importance?: string; description?: string }> }
    key_products?: string[]
    recent_developments?: Array<{ year?: string; event?: string }>
  }
  management_research?: string
  management_people?: Array<{ name?: string; designation?: string; description?: string }>
  management_governance_news?: Array<{ text?: string; sentiment?: 'positive' | 'negative' | 'neutral' }>
  financial_risk?: string
  auditor_flags?: string | null
  auditor_flags_structured?: {
    summary?: string
    events?: Array<{
      date?: string
      fy?: string
      type?: string
      issue?: string
      is_red_flag?: boolean
      status?: string
      management_response?: string
    }>
  } | null
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
  companyOverviewStructured?: {
    opening?: string
    valueChain?: {
      stages?: string[]
      companyPosition?: string
      companyStageIndex?: number
      companyStageIndices?: number[]
      companyPositionDescription?: string
    }
    businessModelTable?: { rows?: Array<{ segment?: string; importance?: string; description?: string }> }
    keyProducts?: string[]
    recentDevelopments?: Array<{ year?: string; event?: string }>
  }
  managementResearch: string
  managementPeople?: Array<{ name?: string; designation?: string; description?: string }>
  managementGovernanceNews?: Array<{ text?: string; sentiment?: 'positive' | 'negative' | 'neutral' }>
  financialRisk?: string
  auditorFlags?: string | null
  auditorFlagsStructured?: {
    summary?: string
    events?: Array<{
      date?: string
      fy?: string
      type?: string
      issue?: string
      isRedFlag?: boolean
      status?: string
      managementResponse?: string
    }>
  } | null
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
    companyOverviewStructured: (() => {
      const co = payload.company_overview_structured
      if (!co || typeof co !== 'object') return undefined
      return {
        opening: co.opening,
        valueChain: co.value_chain
          ? {
              stages: co.value_chain.stages,
              companyPosition: co.value_chain.company_position,
              companyStageIndex: co.value_chain.company_stage_index,
              companyStageIndices: co.value_chain.company_stage_indices,
              companyPositionDescription: co.value_chain.company_position_description,
            }
          : undefined,
        businessModelTable: co.business_model_table
          ? { rows: co.business_model_table.rows }
          : undefined,
        keyProducts: co.key_products,
        recentDevelopments: co.recent_developments,
      }
    })(),
    managementResearch: payload.management_research ?? '',
    managementPeople: Array.isArray(payload.management_people) ? payload.management_people : undefined,
    managementGovernanceNews: Array.isArray(payload.management_governance_news) ? payload.management_governance_news : undefined,
    financialRisk: payload.financial_risk,
    auditorFlags: payload.auditor_flags ?? undefined,
    auditorFlagsStructured: (() => {
      const s = payload.auditor_flags_structured
      if (!s || typeof s !== 'object') return undefined
      type Ev = NonNullable<ReportView['auditorFlagsStructured']>['events'] extends (infer E)[] | undefined ? E : never
      const events: Ev[] | undefined = Array.isArray(s.events)
        ? s.events.map((e: Record<string, unknown>): Ev => ({
            date: e.date as string | undefined,
            fy: e.fy as string | undefined,
            type: e.type as string | undefined,
            issue: e.issue as string | undefined,
            isRedFlag: e.is_red_flag as boolean | undefined,
            status: e.status as string | undefined,
            managementResponse: e.management_response as string | undefined,
          }))
        : undefined
      return { summary: s.summary, events }
    })(),
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
