import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import logoMark from '../assets/logo.svg'
import { hasCompletedScan } from '../lib/sessionGate'

const PAGE_LINKS = [
  { label: 'Home', to: '/' },
  { label: 'Scan', to: '/scan' },
  { label: 'Brain', to: '/brain' },
  { label: 'Session', to: '/session' },
  { label: 'Dashboard', to: '/dashboard' },
]

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const [scanDone, setScanDone] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 24)
    window.addEventListener('scroll', handler, { passive: true })
    return () => window.removeEventListener('scroll', handler)
  }, [])

  useEffect(() => {
    const refresh = () => setScanDone(hasCompletedScan())
    refresh()
    window.addEventListener('nh-scan-saved', refresh)
    return () => window.removeEventListener('nh-scan-saved', refresh)
  }, [location.pathname])

  useEffect(() => {
    const id = requestAnimationFrame(() => setMobileOpen(false))
    return () => cancelAnimationFrame(id)
  }, [location.pathname])

  return (
    <nav
      className={`sticky top-0 z-50 w-full transition-all duration-500 ${
        scrolled
          ? 'border-b border-white/8 bg-background/80 backdrop-blur-xl shadow-lg shadow-black/10'
          : 'border-b border-transparent bg-background/40 backdrop-blur-sm'
      }`}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4 md:px-8">
        <Link to="/" className="flex items-center gap-2.5 group">
          <img
            src={logoMark}
            alt="NeuroHand"
            className="h-8 w-auto transition-all duration-300 group-hover:drop-shadow-[0_0_12px_rgba(167,139,250,0.5)]"
          />
        </Link>

        {/* Desktop links */}
        <div className="hidden items-center gap-1 md:flex">
          {PAGE_LINKS.map((link) => {
            const isSession = link.label === 'Session'
            const to = isSession && !scanDone ? '/scan' : link.to
            const active =
              location.pathname === link.to || (isSession && location.pathname === '/scan' && !scanDone)
            return (
              <Link
                key={link.label}
                to={to}
                title={isSession && !scanDone ? 'Complete a scan first — opens Scan' : undefined}
                className={`relative px-4 py-2 rounded-lg text-sm transition-all duration-300 ${
                  active
                    ? 'font-semibold text-foreground bg-white/8'
                    : 'text-foreground/60 hover:text-foreground hover:bg-white/5'
                }`}
              >
                {link.label}
                {active && (
                  <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-4 h-0.5 rounded-full bg-gradient-to-r from-indigo-500 to-purple-500" />
                )}
              </Link>
            )
          })}
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/scan"
            className="btn-primary rounded-full px-5 py-2 text-sm"
          >
            Get Started
          </Link>

          {/* Mobile menu button */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="md:hidden p-2 rounded-lg hover:bg-white/5 transition-colors"
          >
            {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      <div
        className={`md:hidden overflow-hidden transition-all duration-400 ${
          mobileOpen ? 'max-h-80 opacity-100' : 'max-h-0 opacity-0'
        }`}
      >
        <div className="px-6 pb-6 space-y-1">
          {PAGE_LINKS.map((link) => {
            const active = location.pathname === link.to
            return (
              <Link
                key={link.label}
                to={link.to}
                className={`block px-4 py-3 rounded-xl text-sm transition-all duration-300 ${
                  active
                    ? 'font-semibold text-foreground bg-white/8'
                    : 'text-foreground/60 hover:text-foreground hover:bg-white/5'
                }`}
              >
                {link.label}
              </Link>
            )
          })}
        </div>
      </div>

      {/* Gradient bottom border */}
      <div
        className="mx-auto h-px w-full max-w-[calc(100%-3rem)] bg-gradient-to-r from-transparent via-purple-500/15 to-transparent md:max-w-[calc(100%-4rem)]"
        aria-hidden
      />
    </nav>
  )
}
