const API_BASE = import.meta.env.VITE_API_URL ?? ''

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

export interface ReportStatus {
  status: 'pending' | 'running' | 'completed' | 'failed'
  report_path?: string
  error?: string
}

export async function getReportStatus(reportId: string): Promise<ReportStatus> {
  const res = await fetch(`${API_BASE}/api/reports/${reportId}`)
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export async function getReportHtml(reportId: string): Promise<string> {
  const res = await fetch(`${API_BASE}/api/reports/${reportId}/html`)
  if (!res.ok) throw new Error(res.statusText)
  return res.text()
}
