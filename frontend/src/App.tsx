import { Routes, Route } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import Header from './components/Header'
import Landing from './Landing'
import ReportPage from './ReportPage'

export default function App() {
  return (
    <AuthProvider>
      <Header />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/:symbol/report" element={<ReportPage />} />
      </Routes>
    </AuthProvider>
  )
}
