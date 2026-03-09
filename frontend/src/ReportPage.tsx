import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  createReport,
  getReportStatus,
  getReportPdfBlob,
  submitFeedback,
  mapReportPayloadToView,
  type ReportView,
} from './api'
import { useAuth } from './contexts/AuthContext'
import { ReportA } from './reports/ReportA'

const POLL_INTERVAL_MS = 2500
const CACHE_LOADER_MS = 3000

export default function ReportPage() {
  const { symbol } = useParams<{ symbol: string }>()
  const navigate = useNavigate()
  const { isAuthenticated, signIn } = useAuth()
  const [reportId, setReportId] = useState<string | null>(null)
  const [status, setStatus] = useState<'idle' | 'pending' | 'running' | 'completed' | 'failed'>('idle')
  const [error, setError] = useState<string | null>(null)
  const [reportView, setReportView] = useState<ReportView | null>(null)
  const [showCacheLoader, setShowCacheLoader] = useState(false)
  const [pdfLoading, setPdfLoading] = useState(false)
  const [showDownloadLoginModal, setShowDownloadLoginModal] = useState(false)
  const [feedbackSent, setFeedbackSent] = useState<'up' | 'down' | null>(null)
  const [feedbackComment, setFeedbackComment] = useState('')
  const [showFeedbackComment, setShowFeedbackComment] = useState(false)
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
        if (s.status === 'completed' && s.report) {
          const view = mapReportPayloadToView(s.report)
          if (s.from_cache) {
            setReportView(view)
            setShowCacheLoader(true)
          } else {
            setReportView(view)
          }
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

  useEffect(() => {
    if (!showCacheLoader) return
    const t = setTimeout(() => setShowCacheLoader(false), CACHE_LOADER_MS)
    return () => clearTimeout(t)
  }, [showCacheLoader])

  const handleDownloadPdf = async () => {
    if (!reportId) return
    if (!isAuthenticated) {
      setShowDownloadLoginModal(true)
      return
    }
    setPdfLoading(true)
    try {
      const blob = await getReportPdfBlob(reportId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `equity-report-${decodedSymbol}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      setShowDownloadLoginModal(true)
    } finally {
      setPdfLoading(false)
    }
  }

  const handleFeedback = async (rating: 'up' | 'down') => {
    if (!reportId || feedbackSent) return
    if (rating === 'down') {
      setShowFeedbackComment(true)
      return
    }
    try {
      await submitFeedback({ report_id: reportId, rating })
      setFeedbackSent('up')
    } catch {
      // ignore
    }
  }

  const handleSubmitFeedbackWithComment = async () => {
    if (!reportId || feedbackSent) return
    try {
      await submitFeedback({ report_id: reportId, rating: 'down', comment: feedbackComment || undefined })
      setFeedbackSent('down')
      setShowFeedbackComment(false)
    } catch {
      // ignore
    }
  }

  const showLoader = status === 'pending' || status === 'running' || showCacheLoader
  const showReport = status === 'completed' && reportView && !showCacheLoader

  if (!decodedSymbol) return null

  return (
    <div className="report-page">
      <header className="report-header">
        <div className="report-header-top">
          <button type="button" className="back-btn" onClick={() => navigate('/')} aria-label="Back to search">
            ← Back
          </button>
          {showReport && (
            <div className="report-actions">
              <button
                type="button"
                className="report-download-btn"
                onClick={handleDownloadPdf}
                disabled={pdfLoading}
              >
                {pdfLoading ? '…' : '↓ Download PDF'}
              </button>
              <div className="report-feedback">
                <span className="feedback-label">Helpful?</span>
                <button
                  type="button"
                  className="feedback-btn feedback-up"
                  onClick={() => handleFeedback('up')}
                  disabled={feedbackSent !== null}
                  aria-label="Thumbs up"
                >
                  👍
                </button>
                <button
                  type="button"
                  className="feedback-btn feedback-down"
                  onClick={() => handleFeedback('down')}
                  disabled={feedbackSent !== null}
                  aria-label="Thumbs down"
                >
                  👎
                </button>
              </div>
            </div>
          )}
        </div>
        <h1>{decodedSymbol}</h1>
        <p className="report-subtitle">Equity Research Report</p>
        {showReport && showFeedbackComment && (
          <div className="feedback-comment-wrap">
            <textarea
              className="feedback-comment"
              placeholder="Optional: tell us what we could improve…"
              value={feedbackComment}
              onChange={(e) => setFeedbackComment(e.target.value)}
              rows={2}
            />
            <div className="feedback-comment-actions">
              <button type="button" className="feedback-cancel" onClick={() => setShowFeedbackComment(false)}>
                Cancel
              </button>
              <button type="button" className="feedback-submit" onClick={handleSubmitFeedbackWithComment}>
                Send feedback
              </button>
            </div>
          </div>
        )}
      </header>

      {status === 'failed' && error && (
        <div className="report-error">
          <p>{error}</p>
          <button type="button" onClick={() => window.location.reload()}>Retry</button>
        </div>
      )}

      {showLoader && (
        <div className="report-loader" aria-live="polite">
          <div className="loader-ticker-wrap" aria-hidden>
            <div className="loader-ticker">
              <span>NSE</span><span>BSE</span><span>RELIANCE</span><span>TCS</span><span>INFY</span><span>HDFC</span><span>ROE</span><span>EBITDA</span><span>PAT</span><span>NSE</span><span>BSE</span><span>RELIANCE</span><span>TCS</span><span>INFY</span><span>HDFC</span><span>ROE</span><span>EBITDA</span><span>PAT</span>
            </div>
          </div>
          <div className="loader-chart-bars" aria-hidden>
            <span /><span /><span /><span /><span /><span /><span />
          </div>
          <p>{showCacheLoader ? 'Loading your report…' : 'Analyzing markets & building your report…'}</p>
          <p className="loader-hint">
            {showCacheLoader ? 'Serving cached report.' : 'This may take a minute. We’re fetching financials, concalls, and sector data.'}
          </p>
        </div>
      )}

      {showReport && (
        <div className="report-container">
          <ReportA report={reportView!} />
        </div>
      )}

      {showDownloadLoginModal && (
        <div
          className="report-login-modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-labelledby="download-login-modal-title"
          onClick={() => setShowDownloadLoginModal(false)}
        >
          <div
            className="report-login-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="download-login-modal-title">Sign in to download the report</h2>
            <p>You need to be signed in to download the PDF.</p>
            <div className="report-login-modal-actions">
              <button
                type="button"
                className="report-download-btn"
                onClick={() => {
                  setShowDownloadLoginModal(false)
                  signIn()
                }}
              >
                Sign in
              </button>
              <button
                type="button"
                className="feedback-cancel"
                onClick={() => setShowDownloadLoginModal(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
