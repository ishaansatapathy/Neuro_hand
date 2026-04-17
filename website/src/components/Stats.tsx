import useInView from '../hooks/useInView'
import AnimatedCounter from './AnimatedCounter'

const STATS = [
  { value: '45,000+', label: 'Training Samples', sub: 'Hand landmark dataset' },
  { value: '21', label: 'Tracked Landmarks', sub: 'Per-hand via MediaPipe' },
  { value: '30', label: 'FPS Processing', sub: 'Real-time on standard laptops' },
  { value: '7', label: 'Brain Scan Classes', sub: 'EfficientNet-B0 classifier' },
  { value: '2000', label: 'Rs. Hardware Cost', sub: 'ESP32 + sensors + motor' },
  { value: '74', label: 'Engineered Features', sub: 'Angles, curls, spreads' },
]

export default function Stats() {
  const { ref, inView } = useInView()

  return (
    <section id="stats" className="noise-overlay relative bg-background px-6 py-24 text-foreground md:px-12 lg:px-16">
      <div className="glow-blob left-[20%] top-[50%] h-[400px] w-[400px] bg-blue-600/10" />
      <div className="glow-blob right-[20%] top-[50%] h-[400px] w-[400px] bg-purple-600/10" />
      <div className="gradient-divider mx-auto mb-24 max-w-4xl" />

      <div ref={ref} className="relative z-10 mx-auto max-w-6xl">
        <div className="grid gap-px overflow-hidden rounded-2xl border border-white/10 bg-white/10 sm:grid-cols-2 lg:grid-cols-3">
          {STATS.map((stat, i) => (
            <div
              key={stat.label}
              className={`bg-background p-8 text-center transition-all duration-700 ${
                inView ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'
              }`}
              style={{ transitionDelay: `${200 + i * 100}ms` }}
            >
              <div className="text-gradient-brand mb-2 text-3xl font-semibold md:text-4xl">
                <AnimatedCounter value={stat.value} inView={inView} />
              </div>
              <div className="text-sm font-medium text-foreground/80">{stat.label}</div>
              <div className="mt-1 text-xs text-foreground/45">{stat.sub}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
