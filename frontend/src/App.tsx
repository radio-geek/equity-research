import { useEffect } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import Header from './components/Header'
import Landing from './Landing'
import ReportPage from './ReportPage'
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

function Footer() {
  return (
    <footer className="app-footer">
      <div className="app-footer-inner">
        <p className="app-footer-disclaimer">
          This report is for information purposes only and does not constitute investment advice or a recommendation.
          For investment recommendations, please consult a SEBI registered investment advisor.
        </p>
      </div>
    </footer>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AnalyticsInit />
      <Header />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/:symbol/report" element={<ReportPage />} />
      </Routes>
      <Footer />
      <AnalyticsTracker />
    </AuthProvider>
  )
}
