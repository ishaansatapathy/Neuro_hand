import { Link } from 'react-router-dom'
import { Sparkles, ArrowRight } from 'lucide-react'
import useInView from '../hooks/useInView'

export default function CTA() {
  const { ref, inView } = useInView()

  return (
    <section className="relative overflow-hidden px-6 py-36 md:px-10 lg:px-16" style={{ background: 'var(--bg-root)' }}>
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[500px] rounded-full bg-gradient-to-br from-purple-600/6 to-indigo-600/4 blur-[100px]" />
      </div>
      <div className="gradient-divider mx-auto mb-20 max-w-5xl" />

      <div ref={ref} className="relative z-10 mx-auto max-w-2xl">
        <div className={`mb-6 inline-flex items-center gap-2 rounded-full border border-purple-500/15 px-4 py-2 text-sm font-medium text-purple-200/70 transition-all duration-700 ${inView ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0'}`}
          style={{ background: 'rgba(139,92,246,0.04)' }}>
          <Sparkles className="w-4 h-4 text-purple-400" />
          Ready to begin?
        </div>

        <h2 className={`mb-5 text-3xl font-bold tracking-tight md:text-4xl lg:text-5xl transition-all duration-700 ${inView ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'}`}
          style={{ fontFamily: 'var(--font-heading)', letterSpacing: '-0.03em', lineHeight: '1.1' }}>
          Recovery should be personalized, guided, and accessible.
        </h2>

        <p className={`mb-10 max-w-lg text-base text-foreground/35 leading-relaxed transition-all delay-200 duration-700 ${inView ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0'}`}>
          Not limited to clinic walls. Built for patients who need daily practice with intelligent feedback — right at home.
        </p>

        <div className={`flex flex-wrap items-center gap-4 transition-all delay-300 duration-700 ${inView ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0'}`}>
          <Link to="/scan"
            className="group relative inline-flex items-center gap-2.5 rounded-2xl px-8 py-4 text-base font-semibold text-white overflow-hidden transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_8px_32px_rgba(139,92,246,0.3)]"
            style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6, #a855f7)' }}>
            <div className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/20 to-white/0 -translate-x-full group-hover:translate-x-full transition-transform duration-700" />
            <Sparkles className="w-5 h-5 relative z-10" /><span className="relative z-10">Upload a Scan</span><ArrowRight className="w-5 h-5 relative z-10" />
          </Link>
          <a href="#how-it-works" className="group inline-flex items-center gap-2 rounded-2xl border border-white/8 px-7 py-4 text-base font-medium text-foreground/50 transition-all hover:bg-white/[0.03] hover:border-white/12 hover:-translate-y-0.5"
            style={{ background: 'var(--bg-card)' }}>
            Learn More <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
          </a>
        </div>
      </div>
    </section>
  )
}
