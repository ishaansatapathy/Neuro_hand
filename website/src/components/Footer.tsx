import { Link } from 'react-router-dom'
import { Heart, Code2, Globe, Mail } from 'lucide-react'

const LINKS = [
  { label: 'Problem', href: '#problem' },
  { label: 'How it works', href: '#how-it-works' },
  { label: 'Features', href: '#features' },
  { label: 'Stack', href: '#tech' },
  { label: 'Impact', href: '#stats' },
]

const SOCIAL = [
  { icon: Code2, href: '#', label: 'GitHub' },
  { icon: Globe, href: '#', label: 'Website' },
  { icon: Mail, href: '#', label: 'Email' },
]

export default function Footer() {
  return (
    <footer className="relative border-t border-white/[0.04]" style={{ background: 'var(--bg-root)' }}>
      <div className="mx-auto max-w-7xl px-6 py-16 md:px-10 lg:px-16">
        <div className="grid gap-12 md:grid-cols-3">
          {/* Brand */}
          <div>
            <Link to="/" className="text-xl font-bold text-foreground" style={{ fontFamily: 'var(--font-heading)' }}>
              Neuro<span className="text-gradient-hero">Hand</span>
            </Link>
            <p className="mt-3 text-sm text-foreground/30 leading-relaxed max-w-xs">
              AI-powered stroke rehabilitation. Your healthy hand guides the recovery of the other.
            </p>
          </div>

          {/* Links */}
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-foreground/25 mb-4">Navigation</p>
            <ul className="space-y-2.5">
              {LINKS.map((link) => (
                <li key={link.label}>
                  <a href={link.href} className="text-sm text-foreground/40 transition-colors hover:text-foreground/70">
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Social */}
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-foreground/25 mb-4">Connect</p>
            <div className="flex gap-3">
              {SOCIAL.map((s) => (
                <a key={s.label} href={s.href} aria-label={s.label}
                  className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/[0.04] border border-white/[0.06] text-foreground/40 transition-all duration-300 hover:bg-white/[0.08] hover:text-foreground/70 hover:border-white/[0.12] hover:-translate-y-0.5">
                  <s.icon className="w-4 h-4" />
                </a>
              ))}
            </div>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="mt-14 pt-6 border-t border-white/[0.04] flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-foreground/20">
            © {new Date().getFullYear()} NeuroHand. All rights reserved.
          </p>
          <p className="flex items-center gap-1.5 text-xs text-foreground/20">
            Built with <Heart className="w-3 h-3 text-pink-500/60" /> for rehabilitation
          </p>
        </div>
      </div>
    </footer>
  )
}
