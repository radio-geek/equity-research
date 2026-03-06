import { Routes, Route } from 'react-router-dom'
import Landing from './Landing'
import ReportPage from './ReportPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/:symbol/report" element={<ReportPage />} />
    </Routes>
  )
}
