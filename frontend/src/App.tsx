import { useEffect, useState } from 'react'
import { Routes, Route, Link, useLocation, useMatch } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import Header from './components/Header'
import Landing from './Landing'
import ReportPage from './ReportPage'
import TermsPage from './pages/TermsPage'
import PrivacyPage from './pages/PrivacyPage'
import { ContactModal } from './components/ContactModal'
import { initAnalytics, trackPageView } from './analytics'

function AnalyticsTracker() {
  const { pathname } = useLocation()
  useEffect(() => {
    trackPageView(pathname)
  }, [pathname])
  return null
}

/** Tab title: "Valyu" everywhere except report routes → "Valyu - SYMBOL". */
function DocumentTitle() {
  const reportMatch = useMatch('/:symbol/report')
  useEffect(() => {
    const raw = reportMatch?.params.symbol
    if (raw) {
      try {
        document.title = `Valyu - ${decodeURIComponent(raw).toUpperCase()}`
      } catch {
        document.title = 'Valyu - Report'
      }
    } else {
      document.title = 'Valyu'
    }
  }, [reportMatch?.params.symbol])
  return null
}

function AnalyticsInit() {
  useEffect(() => {
    initAnalytics()
  }, [])
  return null
}

function Footer({ onContactOpen }: { onContactOpen: () => void }) {
  const year = new Date().getFullYear()
  return (
    <footer className="se-footer">
      <div className="se-footer__inner">
        <div className="se-footer__left">
          <p className="se-footer__copyright">
            &copy; {year} valyu. All rights reserved.
          </p>
          <p className="se-footer__disclaimer">
            This site and its reports are for information only. We are{' '}
            <strong>not</strong> a SEBI-registered investment adviser; nothing here is investment advice, a
            recommendation, or an offer to buy or sell securities. For investment guidance, consult a SEBI-registered
            investment adviser.
          </p>
          <div className="se-footer__secondary-links">
            <Link to="/terms#compliance">Compliance</Link>
            <Link to="/terms#disclosures">Disclosures</Link>
          </div>
        </div>
        <div className="se-footer__links">
          <Link to="/privacy">Privacy Policy</Link>
          <Link to="/terms">Terms of Service</Link>
          <button
            type="button"
            onClick={onContactOpen}
            style={{
              background: 'none',
              border: 'none',
              padding: 0,
              cursor: 'pointer',
              fontSize: 'inherit',
              fontFamily: 'inherit',
              color: 'inherit',
              textDecoration: 'underline',
              textUnderlineOffset: '2px',
            }}
          >
            Contact Support
          </button>
        </div>
      </div>
    </footer>
  )
}

export default function App() {
  const [showContact, setShowContact] = useState(false)

  return (
    <AuthProvider>
      <AnalyticsInit />
      <DocumentTitle />
      <Header />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/:symbol/report" element={<ReportPage />} />
        <Route path="/terms" element={<TermsPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
      </Routes>
      <Footer onContactOpen={() => setShowContact(true)} />
      <AnalyticsTracker />
      {showContact && <ContactModal onClose={() => setShowContact(false)} />}
    </AuthProvider>
  )
}
