const LINKS = [
  { label: 'Problem', href: '#problem' },
  { label: 'How It Works', href: '#how-it-works' },
  { label: 'Features', href: '#features' },
  { label: 'Technology', href: '#technology' },
]

export default function Footer() {
  return (
    <footer className="border-t border-white/10 bg-background px-6 py-12 text-foreground md:px-12 lg:px-16">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-8 md:flex-row">
        <div className="text-center md:text-left">
          <span className="text-gradient text-xl font-semibold tracking-tight">NeuroHand</span>
          <p className="mt-1 text-sm text-gray-500">
            AI-Based Post-Stroke Rehabilitation System
          </p>
        </div>

        <div className="flex items-center gap-6">
          {LINKS.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="text-sm text-gray-500 transition-colors duration-200 hover:text-white"
            >
              {link.label}
            </a>
          ))}
        </div>

        <p className="text-xs text-gray-600">
          &copy; {new Date().getFullYear()} NeuroHand. All rights reserved.
        </p>
      </div>
    </footer>
  )
}
