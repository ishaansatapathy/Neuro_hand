import { useEffect, useRef } from 'react'
import { BrowserRouter, Routes, Route, Outlet, useLocation } from 'react-router-dom'
import Navbar from './components/Navbar'
import { disarmSession } from './lib/sessionGate'
import Hero from './components/Hero'
import Problem from './components/Problem'
import HowItWorks from './components/HowItWorks'
import Features from './components/Features'
import Stats from './components/Stats'
import TechStack from './components/TechStack'
import CTA from './components/CTA'
import Footer from './components/Footer'
import ScrollProgress from './components/ScrollProgress'
import ScanUpload from './pages/ScanUpload'
import Session from './pages/Session'
import Dashboard from './pages/Dashboard'
import BrainVisualization from './pages/BrainVisualization'

function LandingPage() {
  return (
    <>
      <ScrollProgress />
      <Hero />
      <Problem />
      <HowItWorks />
      <Features />
      <Stats />
      <TechStack />
      <CTA />
      <Footer />
    </>
  )
}

/**
 * Watches route changes and disarms the session gate whenever the user
 * navigates AWAY from /session. Safe under React Strict Mode because it only
 * reacts to pathname transitions, never on mount alone.
 */
function SessionGateWatcher() {
  const location = useLocation()
  const prevPathRef = useRef<string | null>(null)

  useEffect(() => {
    const prev = prevPathRef.current
    const curr = location.pathname
    if (prev === null) {
      // First load of the app in this tab. The only legitimate entry that
      // can already be armed is /scan (user is mid-flow). Any other landing
      // page — including /session itself — clears the armed flag so the
      // gate re-fires and forces "Scan → Start Rehab Session" again.
      if (curr !== '/scan') {
        disarmSession()
      }
    } else if (prev === '/session' && curr !== '/session') {
      disarmSession()
    }
    prevPathRef.current = curr
  }, [location.pathname])

  return null
}

function PageShell() {
  return (
    <>
      <ScrollProgress />
      <Navbar />
      <div className="page-enter">
        <Outlet />
      </div>
    </>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <SessionGateWatcher />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route element={<PageShell />}>
          <Route path="scan" element={<ScanUpload />} />
          <Route path="session" element={<Session />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="brain" element={<BrainVisualization />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
