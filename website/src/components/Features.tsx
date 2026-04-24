import { Fingerprint, Zap, Brain, Vibrate, ScanLine, Gamepad2, TrendingUp, Home } from 'lucide-react'
import useInView from '../hooks/useInView'
import SectionHeading from './SectionHeading'

const FEATURES = [
  { title: 'Personalized Reference', desc: "Your healthy hand creates the benchmark — not a generic database.", icon: Fingerprint, color: '#60a5fa', featured: true },
  { title: 'Real-Time Feedback', desc: 'Frame-by-frame comparison at 30 FPS with on-screen guidance.', icon: Zap, color: '#fbbf24', featured: true },
  { title: 'AI Gesture Detection', desc: 'Ensemble ML classifies gestures and scores movement quality.', icon: Brain, color: '#a78bfa' },
  { title: 'Haptic Vibration', desc: 'ESP32-driven vibration motor gives physical nudges.', icon: Vibrate, color: '#f472b6' },
  { title: 'Brain Scan Analysis', desc: 'EfficientNet-B0 classifies MRI scans across 7 conditions.', icon: ScanLine, color: '#22d3ee' },
  { title: 'Gamified Recovery', desc: 'Score streaks turn repetitive rehab into engaging challenges.', icon: Gamepad2, color: '#34d399' },
  { title: 'Progress Tracking', desc: 'Every session logged with scores, angles, and trends.', icon: TrendingUp, color: '#818cf8' },
  { title: 'Home-Ready', desc: 'Standard webcam + ESP32. Total cost under ₹2,000.', icon: Home, color: '#fb923c' },
]

export default function Features() {
  const { ref, inView } = useInView()

  return (
    <section id="features" className="relative overflow-hidden px-6 py-28 md:px-10 lg:px-16" style={{ background: 'var(--bg-root)' }}>
      <div className="ambient-glow w-[500px] h-[500px] bg-purple-600/6 top-[20%] right-[5%]" />
      <div className="gradient-divider mx-auto mb-20 max-w-5xl" />

      <div ref={ref} className="relative z-10 mx-auto max-w-6xl">
        <SectionHeading label="Features" title="Everything recovery needs, in one system." subtitle="Multi-modal feedback, personalized AI, and affordable hardware." inView={inView} />

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {FEATURES.map((feat, i) => {
            const Icon = feat.icon
            const isWide = i < 2
            return (
              <div key={feat.title}
                className={`group relative rounded-xl border border-white/[0.05] p-6 transition-all duration-500 hover:border-white/[0.10] hover:-translate-y-1 ${isWide ? 'lg:col-span-2' : ''} ${inView ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0'}`}
                style={{ transitionDelay: `${200 + i * 60}ms`, background: 'var(--bg-card)' }}>

                {feat.featured && (
                  <div className="absolute top-3 right-3 px-2 py-0.5 rounded-md text-[9px] font-bold uppercase tracking-wider text-purple-300/70"
                    style={{ background: 'rgba(139,92,246,0.06)', border: '1px solid rgba(139,92,246,0.15)' }}>Core</div>
                )}

                <div className="mb-4 inline-flex items-center justify-center rounded-lg transition-transform duration-300 group-hover:scale-110"
                  style={{ width: isWide ? 44 : 36, height: isWide ? 44 : 36, background: `${feat.color}10`, border: `1px solid ${feat.color}18` }}>
                  <Icon className="text-white" style={{ width: isWide ? 22 : 18, height: isWide ? 22 : 18, color: feat.color }} />
                </div>

                <h3 className={`mb-1 font-semibold text-foreground ${isWide ? 'text-base' : 'text-sm'}`}>{feat.title}</h3>
                <p className={`leading-relaxed text-foreground/35 ${isWide ? 'text-sm' : 'text-xs'}`}>{feat.desc}</p>

                <div className="absolute bottom-0 left-4 right-4 h-px opacity-0 group-hover:opacity-100 transition-opacity"
                  style={{ background: `linear-gradient(90deg, transparent, ${feat.color}20, transparent)` }} />
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
