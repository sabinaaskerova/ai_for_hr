import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import HistoryPage from './pages/History'
import GoalEvaluator from './pages/GoalEvaluator'
import GoalGenerator from './pages/GoalGenerator'
import Analytics from './pages/Analytics'
import DocumentBrowser from './pages/DocumentBrowser'

export default function App() {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar />
      <main className="flex-1 ml-64 min-h-screen">
        <Routes>
          <Route path="/" element={<GoalEvaluator />} />
          <Route path="/generate" element={<GoalGenerator />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/documents" element={<DocumentBrowser />} />
          <Route path="/history" element={<HistoryPage />} />
        </Routes>
      </main>
    </div>
  )
}
