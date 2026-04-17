import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
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

  return (
    <nav
      className={`sticky top-0 z-50 w-full border-b transition-colors ${
        scrolled
          ? 'border-foreground/10 bg-background/85 backdrop-blur-md'
          : 'border-transparent bg-background/40 backdrop-blur-sm'
      }`}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4 md:px-8">
        <Link to="/" className="flex items-center gap-2.5">
          <img src={logoMark} alt="NeuroHand" className="h-8 w-auto" />
        </Link>

        <div className="hidden items-center gap-8 md:flex">
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
                className={`text-sm transition-colors ${
                  active ? 'font-medium text-foreground' : 'text-foreground/70 hover:text-foreground'
                }`}
              >
                {link.label}
              </Link>
            )
          })}
        </div>

        <Link
          to="/scan"
          className="btn-hero-secondary rounded-full px-4 py-2 text-sm font-medium"
        >
          Sign Up
        </Link>
      </div>
      <div
        className="mx-auto h-px w-full max-w-[calc(100%-3rem)] 'bg-gradient-to-r' from-transparent via-foreground/15 to-transparent md:max-w-[calc(100%-4rem)]"
        aria-hidden
      />
    </nav>
  )
}
