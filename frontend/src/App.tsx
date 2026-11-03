import { BrowserRouter as Router, Routes, Route, NavLink as Link } from 'react-router-dom'
import ExecutiveOverview from './pages/ExecutiveOverview'
import FinancialPerformance from './pages/FinancialPerformance'
import ScenarioPlanning from './pages/ScenarioPlanning'
import AskFinance from './pages/AskFinance'
import FinancialEvidence from './pages/FinancialEvidence'

function App() {
  return (
    <Router>
      <div className="app">
        <header>
          <h1>FinSight Planner</h1>
          <p>Financial Planning &amp; Scenario Intelligence · Phynapse - Applied AI Consulting &amp; Engineering · Synthetic data (Asteron Group)</p>
        </header>
        <nav>
          <Link to="/" end>Executive Overview</Link>
          <Link to="/performance">Financial Performance</Link>
          <Link to="/scenarios">Scenario Planning</Link>
          <Link to="/ask">Ask Finance</Link>
          <Link to="/evidence">Financial Evidence</Link>
        </nav>
        <main>
          <Routes>
            <Route path="/" element={<ExecutiveOverview />} />
            <Route path="/performance" element={<FinancialPerformance />} />
            <Route path="/scenarios" element={<ScenarioPlanning />} />
            <Route path="/ask" element={<AskFinance />} />
            <Route path="/evidence" element={<FinancialEvidence />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}

export default App

