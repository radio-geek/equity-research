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
import { ReportLoaderVisual } from './components/ReportLoaderVisual'
import { ReportA } from './reports/ReportA'

const POLL_INTERVAL_MS = 2500
const LOADER_TICK_MS = 200
/** Client-side cap while status is not completed (sublinear curve approaches this). */
const HEURISTIC_PROGRESS_CAP = 90
const HEURISTIC_PENDING_PCT = 6
const HEURISTIC_STAGE_SECONDS = 14

const LOADER_STEPS = [
  'Resolving company and live quote data…',
  'Pulling financials, ratios, and trends…',
  'Reviewing governance and auditor signals…',
  'Gathering concall context and sector view…',
  'Synthesizing the full dossier…',
]

function heuristicProgressPercent(status: 'pending' | 'running', elapsedSec: number): number {
  if (status === 'pending') return HEURISTIC_PENDING_PCT
  const lo = HEURISTIC_PENDING_PCT
  const cap = HEURISTIC_PROGRESS_CAP
  return lo + (cap - lo) * (1 - Math.exp(-elapsedSec / 42))
}

function heuristicStageIndex(elapsedSec: number, nSteps: number): number {
  return Math.min(nSteps - 1, Math.floor(elapsedSec / HEURISTIC_STAGE_SECONDS))
}

/** Stepper active index from overall progress (aligns with backend milestones). */
function stageIndexFromProgress(p: number): number {
  const x = Math.max(0, Math.min(100, p))
  if (x <= 15) return 0
  if (x <= 40) return 1
  if (x <= 60) return 2
  if (x <= 82) return 3
  return 4
}

const SECTION_NAVS = [
  { id: 'section-overview',   label: 'Overview' },
  { id: 'section-management', label: 'Management' },
  { id: 'section-auditor',    label: 'Governance' },
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
  const [loaderTick, setLoaderTick] = useState(0)
  const [serverProgress, setServerProgress] = useState<number | undefined>()
  const [serverStage, setServerStage] = useState<string | undefined>()
  const pollRef = useRef<ReturnType<typeof setInterval>>()
  const headerRef = useRef<HTMLElement>(null)
  const loadStartedAtRef = useRef<number>(Date.now())

  const decodedSymbol = symbol ? decodeURIComponent(symbol).toUpperCase() : ''

  useEffect(() => {
    if (!decodedSymbol) {
      navigate('/', { replace: true })
      return
    }
    let cancelled = false
    createReport(decodedSymbol)
      .then(async ({ report_id }) => {
        if (cancelled) return
        try {
          const s = await getReportStatus(report_id)
          if (cancelled) return
          if (s.status === 'completed' && s.report) {
            setReportId(report_id)
            setStatus('completed')
            setReportView(
              mapReportPayloadToView(s.report, { fromCache: s.from_cache === true })
            )
            trackEvent('Report Viewed', {
              symbol: decodedSymbol,
              from_cache: s.from_cache === true ? '1' : '0',
            })
            return
          }
          setReportId(report_id)
          setStatus(s.status as 'pending' | 'running' | 'completed' | 'failed')
          if (s.status === 'failed') {
            setError(s.error ?? 'Report generation failed')
          }
        } catch {
          if (cancelled) return
          setReportId(report_id)
          setStatus('pending')
        }
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
        if (s.status === 'pending' || s.status === 'running') {
          if (typeof s.progress === 'number' && !Number.isNaN(s.progress)) {
            setServerProgress(s.progress)
          }
          if (typeof s.stage === 'string' && s.stage.trim() !== '') {
            setServerStage(s.stage.trim())
          }
        }
        if (s.status === 'completed' && s.report) {
          const view = mapReportPayloadToView(s.report, { fromCache: s.from_cache === true })
          setReportView(view)
          trackEvent('Report Viewed', {
            symbol: decodedSymbol,
            from_cache: s.from_cache === true ? '1' : '0',
          })
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

  const showLoader = status === 'pending' || status === 'running'

  useEffect(() => {
    if (!showLoader) return
    loadStartedAtRef.current = Date.now()
    setServerProgress(undefined)
    setServerStage(undefined)
    setLoaderTick(0)
  }, [showLoader, reportId])

  useEffect(() => {
    if (!showLoader) return
    const id = window.setInterval(() => setLoaderTick((t) => t + 1), LOADER_TICK_MS)
    return () => window.clearInterval(id)
  }, [showLoader])

  // loaderTick triggers re-renders so elapsed time and the heuristic bar update smoothly.
  const elapsedSec = (Date.now() - loadStartedAtRef.current + loaderTick * 0) / 1000
  const clientProgressPct = heuristicProgressPercent(status === 'pending' ? 'pending' : 'running', elapsedSec)
  const displayProgressPct =
    serverProgress !== undefined ? Math.max(0, Math.min(100, serverProgress)) : clientProgressPct
  const stageLabel =
    serverStage ??
    LOADER_STEPS[heuristicStageIndex(elapsedSec, LOADER_STEPS.length)]
  const displayStageIndex = stageIndexFromProgress(displayProgressPct)
  const progressRounded = Math.round(displayProgressPct)

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

  const copyShareLink = async () => {
    const url = window.location.href
    try {
      await navigator.clipboard.writeText(url)
      addToast('Link copied to clipboard', 'success')
      trackEvent('Share Link Copied', { symbol: decodedSymbol })
    } catch {
      addToast('Could not copy link', 'error')
    }
  }

  const showReport = status === 'completed' && reportView

  if (!decodedSymbol) return null

  return (
    <div className="report-page">
      <header className={`report-header${showReport ? ' report-header--compact' : ''}`} ref={headerRef}>
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
              <button type="button" className="feedback-btn" onClick={copyShareLink}>
                Copy link
              </button>
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
        {!showReport && (
          <>
            <h1 className="report-header-title">{decodedSymbol}</h1>
            <p className="report-header-status">Preparing your analysis…</p>
          </>
        )}
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
              <button type="button" className="feedback-btn" onClick={copyShareLink}>
                Copy link
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
        <div
          className="report-container report-loader-shell"
          aria-busy="true"
          aria-live="polite"
        >
          <div
            className="report-loader-top-bar"
            role="progressbar"
            aria-valuenow={progressRounded}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Report generation progress"
          >
            <div className="report-loader-top-bar-fill" style={{ width: `${displayProgressPct}%` }} />
          </div>
          <div className="report-loader-inner report-loader-inner--premium">
            <ReportLoaderVisual
              progressPercent={displayProgressPct}
              stageIndex={displayStageIndex}
              totalStages={LOADER_STEPS.length}
              stageLabel={stageLabel}
            />
            <p className="loader-hint loader-hint--center">
              This usually takes about a minute. Keep this tab open—we’ll show the report when each part is ready.
            </p>
          </div>
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
