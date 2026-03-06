import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { createReport, getReportStatus, getReportHtml } from './api'

const POLL_INTERVAL_MS = 2500

export default function ReportPage() {
  const { symbol } = useParams<{ symbol: string }>()
  const navigate = useNavigate()
  const [reportId, setReportId] = useState<string | null>(null)
  const [status, setStatus] = useState<'idle' | 'pending' | 'running' | 'completed' | 'failed'>('idle')
  const [error, setError] = useState<string | null>(null)
  const [html, setHtml] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval>>()

  const decodedSymbol = symbol ? decodeURIComponent(symbol).toUpperCase() : ''

  useEffect(() => {
    if (!decodedSymbol) {
      navigate('/', { replace: true })
      return
    }
    let cancelled = false
    createReport(decodedSymbol)
      .then(({ report_id }) => {
        if (cancelled) return
        setReportId(report_id)
        setStatus('pending')
      })
      .catch((e) => {
        if (cancelled) return
        setError(e.message ?? 'Failed to start report')
        setStatus('failed')
      })
    return () => {
      cancelled = true
    }
  }, [decodedSymbol, navigate])

  useEffect(() => {
    if (!reportId || status === 'completed' || status === 'failed') return
    const poll = async () => {
      try {
        const s = await getReportStatus(reportId)
        setStatus(s.status as 'pending' | 'running' | 'completed' | 'failed')
        if (s.status === 'completed') {
          const content = await getReportHtml(reportId)
          setHtml(content)
          if (pollRef.current) {
            clearInterval(pollRef.current)
            pollRef.current = undefined
          }
        } else if (s.status === 'failed') {
          setError(s.error ?? 'Report generation failed')
          if (pollRef.current) {
            clearInterval(pollRef.current)
            pollRef.current = undefined
          }
        }
      } catch {
        setError('Failed to fetch status')
      }
    }
    pollRef.current = setInterval(poll, POLL_INTERVAL_MS)
    poll()
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [reportId, status])

  if (!decodedSymbol) return null

  return (
    <div className="report-page">
      <header className="report-header">
        <button type="button" className="back-btn" onClick={() => navigate('/')} aria-label="Back to search">
          ← Back
        </button>
        <h1>{decodedSymbol}</h1>
        <p className="report-subtitle">Equity Research Report</p>
      </header>

      {status === 'failed' && error && (
        <div className="report-error">
          <p>{error}</p>
          <button type="button" onClick={() => window.location.reload()}>Retry</button>
        </div>
      )}

      {(status === 'pending' || status === 'running') && (
        <div className="report-loader" aria-live="polite">
          <div className="loader-spinner" />
          <p>Generating your report…</p>
          <p className="loader-hint">This may take a minute.</p>
        </div>
      )}

      {status === 'completed' && html && (
        <div className="report-container">
          <iframe
            title={`Report ${decodedSymbol}`}
            srcDoc={html}
            className="report-iframe"
            sandbox="allow-same-origin"
          />
        </div>
      )}
    </div>
  )
}
