import useInView from '../hooks/useInView'
import AnimatedCounter from './AnimatedCounter'

const STATS = [
  { value: '45,000+', label: 'Training Samples', sub: 'Hand landmark dataset', color: '#60a5fa' },
  { value: '21', label: 'Tracked Landmarks', sub: 'Per-hand via MediaPipe', color: '#a78bfa' },
  { value: '30', label: 'FPS Processing', sub: 'Real-time on laptops', color: '#f472b6' },
  { value: '7', label: 'Brain Classes', sub: 'EfficientNet-B0', color: '#22d3ee' },
  { value: '2000', label: 'Rs. Hardware', sub: 'ESP32 + sensors + motor', color: '#fbbf24' },
  { value: '74', label: 'Features', sub: 'Angles, curls, spreads', color: '#34d399' },
]

export default function Stats() {
  const { ref, inView } = useInView()

  return (
    <section id="stats" className="relative overflow-hidden px-6 py-28 md:px-10 lg:px-16" style={{ background: 'var(--bg-root)' }}>
      <div className="ambient-glow w-[400px] h-[400px] bg-blue-600/5 left-[20%] top-[50%] -translate-y-1/2" />
      <div className="gradient-divider mx-auto mb-20 max-w-5xl" />

      <div ref={ref} className="relative z-10 mx-auto max-w-5xl">
        <div className={`mb-12 inline-flex items-center gap-2 rounded-full border border-cyan-500/15 px-4 py-1.5 text-[11px] font-bold uppercase tracking-[0.2em] text-cyan-300/60 transition-all duration-700 ${inView ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0'}`}
          style={{ background: 'rgba(34,211,238,0.04)' }}>
          <span className="relative flex h-1.5 w-1.5"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" /><span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-cyan-500" /></span>
          Impact & Scale
        </div>

        <div className="grid gap-px overflow-hidden rounded-2xl border border-white/[0.05] sm:grid-cols-2 lg:grid-cols-3">
          {STATS.map((stat, i) => (
            <div key={stat.label}
              className={`relative p-8 text-center group hover:bg-white/[0.015] transition-all duration-500 ${inView ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0'}`}
              style={{ transitionDelay: `${150 + i * 80}ms`, background: 'var(--bg-root)' }}>
              <div className="absolute top-4 right-4 w-1.5 h-1.5 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                style={{ background: stat.color, boxShadow: `0 0 8px ${stat.color}50` }} />
              <div className="mb-2 text-3xl font-bold md:text-4xl tracking-tight" style={{ color: stat.color }}>
                <AnimatedCounter value={stat.value} inView={inView} />
              </div>
              <div className="text-sm font-medium text-foreground/60 mb-0.5">{stat.label}</div>
              <div className="text-[11px] text-foreground/25">{stat.sub}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
