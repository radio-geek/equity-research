import { useEffect, useState } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import Header from './components/Header'
import Landing from './Landing'
import ReportPage from './ReportPage'
import { ContactModal } from './components/ContactModal'
import { initAnalytics, trackPageView } from './analytics'

function AnalyticsTracker() {
  const { pathname } = useLocation()
  useEffect(() => {
    trackPageView(pathname)
  }, [pathname])
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
            &copy; {year} Equity Research. All rights reserved.
          </p>
          <p className="se-footer__disclaimer">
            This site and its reports are for information only. We are{' '}
            <strong>not</strong> a SEBI-registered investment adviser; nothing here is investment advice, a
            recommendation, or an offer to buy or sell securities. For investment guidance, consult a SEBI-registered
            investment adviser.
          </p>
          <div className="se-footer__secondary-links">
            <a href="/">Compliance</a>
            <a href="/">Disclosures</a>
          </div>
        </div>
        <div className="se-footer__links">
          <a href="/">Privacy Policy</a>
          <a href="/">Terms of Service</a>
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
      <Header />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/:symbol/report" element={<ReportPage />} />
      </Routes>
      <Footer onContactOpen={() => setShowContact(true)} />
      <AnalyticsTracker />
      {showContact && <ContactModal onClose={() => setShowContact(false)} />}
    </AuthProvider>
  )
}
