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

export default function App() {
  return (
    <AuthProvider>
      <AnalyticsInit />
      <Header />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/:symbol/report" element={<ReportPage />} />
      </Routes>
      <AnalyticsTracker />
    </AuthProvider>
  )
}
