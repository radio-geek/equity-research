import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  createReport,
  getReportStatus,
  getReportPdfBlob,
  mapReportPayloadToView,
  type ReportView,
} from './api'
import { FeedbackModal } from './components/FeedbackModal'
import { useToast, ToastContainer } from './components/Toast'
import { trackEvent } from './analytics'
import { useAuth } from './contexts/AuthContext'
import { ReportA } from './reports/ReportA'

const POLL_INTERVAL_MS = 2500

const SECTION_NAVS = [
  { id: 'section-overview',   label: 'Overview' },
  { id: 'section-management', label: 'Management' },
  { id: 'section-auditor',    label: 'Auditor' },
  { id: 'section-financials', label: 'Financials' },
  { id: 'section-concall',    label: 'Concalls' },
  { id: 'section-sectoral',   label: 'Sectoral' },
  { id: 'section-flags',      label: 'Flags' },
]

export default function ReportPage() {
  const { symbol } = useParams<{ symbol: string }>()
  const navigate = useNavigate()
  const { isAuthenticated, signIn } = useAuth()
  const [reportId, setReportId] = useState<string | null>(null)
  const [status, setStatus] = useState<'idle' | 'pending' | 'running' | 'completed' | 'failed'>('idle')
  const [error, setError] = useState<string | null>(null)
  const [reportView, setReportView] = useState<ReportView | null>(null)
  const [pdfLoading, setPdfLoading] = useState(false)
  const [showDownloadLoginModal, setShowDownloadLoginModal] = useState(false)
  const { toasts, addToast, addPersistentToast, dismiss } = useToast()
  const [showFeedbackModal, setShowFeedbackModal] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const [activeSection, setActiveSection] = useState('')
  const pollRef = useRef<ReturnType<typeof setInterval>>()
  const headerRef = useRef<HTMLElement>(null)

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
          setReportView(view)
          trackEvent('Report Viewed', { symbol: decodedSymbol })
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
    const STICKY_H = 92 // approx height of two-row sticky nav
    const onScroll = () => {
      const h = headerRef.current?.offsetHeight ?? 120
      setScrolled(window.scrollY > h)
      // Scrollspy: last section whose top is above the sticky nav threshold
      let active = ''
      for (const { id } of SECTION_NAVS) {
        const el = document.getElementById(id)
        if (el && el.getBoundingClientRect().top <= STICKY_H + 24) active = id
      }
      setActiveSection(active)
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const handleDownloadPdf = async () => {
    if (!reportId) return
    if (!isAuthenticated) {
      setShowDownloadLoginModal(true)
      return
    }
    setPdfLoading(true)
    const loadingToastId = addPersistentToast('Brewing your report, hang tight…', 'info')
    try {
      const blob = await getReportPdfBlob(reportId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `equity-report-${decodedSymbol}.pdf`
      a.click()
      URL.revokeObjectURL(url)
      trackEvent('PDF Downloaded', { symbol: decodedSymbol })
      dismiss(loadingToastId)
      addToast('PDF downloaded successfully', 'success')
    } catch (e) {
      dismiss(loadingToastId)
      const msg = e instanceof Error ? e.message : 'Download failed'
      if (msg === 'Unauthorized') setShowDownloadLoginModal(true)
      else addToast(msg, 'error')
    } finally {
      setPdfLoading(false)
    }
  }

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id)
    if (!el) return
    const top = el.getBoundingClientRect().top + window.scrollY - 100
    window.scrollTo({ top, behavior: 'smooth' })
  }

  const showLoader = status === 'pending' || status === 'running'
  const showReport = status === 'completed' && reportView

  if (!decodedSymbol) return null

  return (
    <div className="report-page">
      <header className="report-header" ref={headerRef}>
        <div className="report-header-top">
          <button type="button" className="back-btn" onClick={() => navigate('/')} aria-label="Back to search">
            ← Back
          </button>
          {showReport && (
            <div className="report-actions">
              <div className="report-actions-pdf">
                <button
                  type="button"
                  className="report-download-btn"
                  onClick={handleDownloadPdf}
                  disabled={pdfLoading}
                >
                  {pdfLoading ? '…' : '↓ Download PDF'}
                </button>
              </div>
              <div className="report-feedback">
                <button
                  type="button"
                  className="feedback-btn"
                  onClick={() => setShowFeedbackModal(true)}
                  aria-label="Give feedback"
                >
                  Feedback
                </button>
              </div>
            </div>
          )}
        </div>
        <h1>{decodedSymbol}</h1>
        <p className="report-subtitle">Equity Research Report</p>
      </header>

      {showReport && scrolled && (
        <div className="report-sticky-nav">
          <div className="report-sticky-top">
            <button type="button" className="back-btn" onClick={() => navigate('/')} aria-label="Back to search">
              ← Back
            </button>
            <span className="report-sticky-symbol">{decodedSymbol}</span>
            <div className="report-sticky-actions">
              <button
                type="button"
                className="report-download-btn"
                onClick={handleDownloadPdf}
                disabled={pdfLoading}
              >
                {pdfLoading ? '…' : <><span>↓</span><span className="download-label"> Download PDF</span></>}
              </button>
              <button
                type="button"
                className="feedback-btn"
                onClick={() => setShowFeedbackModal(true)}
              >
                Feedback
              </button>
            </div>
          </div>
          <div className="report-sticky-sections">
            {SECTION_NAVS.map(({ id, label }) => (
              <button
                key={id}
                type="button"
                className={`report-sticky-section-btn${activeSection === id ? ' active' : ''}`}
                onClick={() => scrollToSection(id)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      )}

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
          <p>Analyzing markets & building your report…</p>
          <p className="loader-hint">
            This may take a minute. We’re fetching financials, concalls, and sector data.
          </p>
        </div>
      )}

      {showReport && (
        <div className="report-container">
          <ReportA report={reportView!} />
        </div>
      )}

      {showFeedbackModal && (
        <FeedbackModal symbol={decodedSymbol} onClose={() => setShowFeedbackModal(false)} />
      )}

      <ToastContainer toasts={toasts} onDismiss={dismiss} />

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
