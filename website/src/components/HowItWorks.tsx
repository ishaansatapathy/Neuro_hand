import { Camera, Hand } from 'lucide-react'
import useInView from '../hooks/useInView'
import SectionHeading from './SectionHeading'

const PHASES = [
  {
    phase: 'Phase 1', title: 'Capture the Healthy Hand',
    desc: 'The system records your unaffected hand. MediaPipe extracts 21 landmarks, computes joint angles, finger curl ratios — building a personalized reference.',
    steps: ['Position healthy hand in front of camera', 'System captures 30+ frames per gesture', 'Joint angles & landmarks averaged', 'Reference stored as your baseline'],
    icon: Camera, color: '#60a5fa',
  },
  {
    phase: 'Phase 2', title: 'Guide the Damaged Hand',
    desc: 'When exercising the affected hand, the system compares every movement against your healthy-hand reference in real time.',
    steps: ['Real-time landmark extraction', 'Angle-by-angle comparison vs. reference', 'On-screen guidance arrows & color joints', 'ESP32 vibration feedback for nudge'],
    icon: Hand, color: '#a78bfa',
  },
]

export default function HowItWorks() {
  const { ref, inView } = useInView()

  return (
    <section id="how-it-works" className="relative overflow-hidden px-6 py-28 md:px-10 lg:px-16" style={{ background: 'var(--bg-root)' }}>
      <div className="ambient-glow w-[500px] h-[500px] bg-indigo-600/6 left-[50%] top-[30%] -translate-x-1/2" />
      <div className="gradient-divider mx-auto mb-20 max-w-5xl" />

      <div ref={ref} className="relative z-10 mx-auto max-w-6xl">
        <SectionHeading label="How It Works" title="Your healthy hand is the best teacher." subtitle="Two phases. One goal — map healthy movement onto the affected side." inView={inView} />

        <div className="grid gap-5 lg:grid-cols-2">
          {PHASES.map((phase, i) => {
            const Icon = phase.icon
            return (
              <div key={phase.phase}
                className={`group relative rounded-xl border border-white/[0.05] p-7 transition-all duration-500 hover:border-white/[0.10] ${inView ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0'}`}
                style={{ transitionDelay: `${350 + i * 150}ms`, background: 'var(--bg-card)' }}>

                <div className="mb-5 flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg transition-transform duration-300 group-hover:scale-110"
                    style={{ background: `${phase.color}12`, border: `1px solid ${phase.color}20` }}>
                    <Icon className="w-5 h-5" style={{ color: phase.color }} />
                  </div>
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-foreground/25">{phase.phase}</span>
                    <h3 className="text-lg font-bold text-foreground">{phase.title}</h3>
                  </div>
                </div>

                <p className="mb-5 text-sm leading-relaxed text-foreground/35">{phase.desc}</p>

                <ol className="space-y-2.5">
                  {phase.steps.map((step, j) => (
                    <li key={j} className="flex items-start gap-2.5 text-sm">
                      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded text-[10px] font-bold mt-0.5"
                        style={{ background: `${phase.color}10`, color: phase.color, border: `1px solid ${phase.color}18` }}>{j + 1}</span>
                      <span className="text-foreground/40">{step}</span>
                    </li>
                  ))}
                </ol>
              </div>
            )
          })}
        </div>

        {/* Pipeline */}
        <div className={`mt-8 rounded-xl border border-white/[0.05] p-5 transition-all delay-600 duration-700 ${inView ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0'}`}
          style={{ background: 'var(--bg-card)' }}>
          <div className="flex flex-wrap items-center justify-center gap-2 font-mono text-xs tracking-wide">
            {[
              { text: 'Healthy Hand', cls: 'bg-blue-500/8 border-blue-500/15 text-blue-400 font-bold' },
              { text: '→' },
              { text: 'Capture', cls: 'text-foreground/35' },
              { text: '→' },
              { text: 'Reference', cls: 'bg-white/4 border-white/8 text-foreground font-semibold' },
              { text: '→' },
              { text: 'Damaged Hand', cls: 'bg-purple-500/8 border-purple-500/15 text-purple-400 font-bold' },
              { text: '→' },
              { text: 'Compare', cls: 'text-foreground/35' },
              { text: '→' },
              { text: 'Feedback', cls: 'bg-emerald-500/8 border-emerald-500/15 text-emerald-400 font-bold' },
            ].map((item, idx) => (
              <span key={idx} className={item.cls ? `${item.cls} px-2.5 py-1 rounded-md border` : 'text-foreground/15'}>{item.text}</span>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
