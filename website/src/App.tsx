import { BrowserRouter, Routes, Route, Outlet } from 'react-router-dom'
import Navbar from './components/Navbar'
import Hero from './components/Hero'
import Problem from './components/Problem'
import HowItWorks from './components/HowItWorks'
import Features from './components/Features'
import Stats from './components/Stats'
import TechStack from './components/TechStack'
import CTA from './components/CTA'
import Footer from './components/Footer'
import ScanUpload from './pages/ScanUpload'
import Session from './pages/Session'
import Dashboard from './pages/Dashboard'
import BrainVisualization from './pages/BrainVisualization'

function LandingPage() {
  return (
    <>
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

function PageShell() {
  return (
    <>
      <Navbar />
      <Outlet />
    </>
  )
}

export default function App() {
  return (
    <BrowserRouter>
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
