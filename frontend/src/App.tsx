import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth'
import Layout from './components/Layout'
import AdvicePage from './pages/Advice'
import AlertsPage from './pages/Alerts'
import ExplorerPage from './pages/Explorer'
import IssueDetailPage from './pages/IssueDetail'
import IssuesPage from './pages/Issues'
import KeywordsPage from './pages/Keywords'
import KeywordWatchPage from './pages/KeywordWatch'
import Login from './pages/Login'
import OverviewPage from './pages/Overview'
import ReportsPage from './pages/Reports'
import SentimentPage from './pages/Sentiment'
import SettingsPage from './pages/Settings'
import SourcesPage from './pages/Sources'

function Guard() {
  const { user, loading } = useAuth()
  if (loading) return <div className="grid min-h-screen place-items-center text-sm text-muted">Memuat sesi...</div>
  if (!user) return <Navigate to="/login" replace />
  return <Layout />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Guard />}>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/saran" element={<AdvicePage />} />
        <Route path="/sentimen" element={<SentimentPage />} />
        <Route path="/isu" element={<IssuesPage />} />
        <Route path="/pantauan" element={<KeywordWatchPage />} />
        <Route path="/isu/:id" element={<IssueDetailPage />} />
        <Route path="/sumber" element={<SourcesPage />} />
        <Route path="/explorer" element={<ExplorerPage />} />
        <Route path="/alert" element={<AlertsPage />} />
        <Route path="/laporan" element={<ReportsPage />} />
        <Route path="/kata-kunci" element={<KeywordsPage />} />
        <Route path="/pengaturan" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
