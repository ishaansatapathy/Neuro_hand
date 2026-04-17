import useInView from '../hooks/useInView'
import useSpotlight from '../hooks/useSpotlight'
import SectionHeading from './SectionHeading'

const PHASES = [
  {
    phase: 'Phase 1',
    title: 'Capture the Healthy Hand',
    desc: 'The system records your unaffected hand using a webcam. MediaPipe extracts 21 landmarks, computes joint angles, finger curl ratios, and spread distances — building a personalized reference unique to your body.',
    steps: [
      'Position healthy hand in front of camera',
      'System captures 30+ frames per gesture',
      'Joint angles & landmarks are averaged',
      'Reference stored as your personal baseline',
    ],
    accent: 'bg-blue-500',
  },
  {
    phase: 'Phase 2',
    title: 'Guide the Damaged Hand',
    desc: 'When exercising with your affected hand, the system compares every movement against your own healthy-hand reference in real time — telling you exactly what to fix through visual cues and haptic vibration.',
    steps: [
      'Real-time landmark extraction on affected hand',
      'Angle-by-angle comparison vs. your reference',
      'On-screen guidance arrows & color-coded joints',
      'ESP32 vibration feedback for physical nudge',
    ],
    accent: 'bg-purple-500',
  },
]

export default function HowItWorks() {
  const { ref, inView } = useInView()
  const { onMouseMove } = useSpotlight()

  return (
    <section id="how-it-works" className="noise-overlay relative overflow-hidden bg-background px-6 py-24 text-foreground md:px-12 lg:px-16">
      <div className="glow-blob left-[50%] top-[30%] h-[600px] w-[600px] -translate-x-1/2 bg-indigo-500/10" />
      <div className="gradient-divider mx-auto mb-24 max-w-4xl" />

      <div ref={ref} className="relative z-10 mx-auto max-w-6xl">
        <SectionHeading
          label="How It Works"
          title="Your healthy hand is the best teacher."
          subtitle="Two phases. One goal — map healthy movement onto the affected side using neuroplasticity: neurons that fire together, wire together."
          inView={inView}
        />

        <div className="grid gap-8 lg:grid-cols-2">
          {PHASES.map((phase, i) => (
            <div
              key={phase.phase}
              onMouseMove={onMouseMove}
              className={`card-spotlight liquid-glass rounded-2xl border border-white/10 p-8 transition-all duration-700 hover:border-white/20 ${
                inView ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0'
              }`}
              style={{ transitionDelay: `${400 + i * 200}ms` }}
            >
              <div className="mb-4 flex items-center gap-3">
                <div className={`h-2 w-2 rounded-full ${phase.accent}`} />
                <span className="text-xs font-medium uppercase tracking-wider text-gray-400">
                  {phase.phase}
                </span>
              </div>
              <h3 className="mb-3 text-2xl font-semibold">{phase.title}</h3>
              <p className="mb-6 text-sm leading-relaxed text-gray-400">{phase.desc}</p>
              <ol className="space-y-3">
                {phase.steps.map((step, j) => (
                  <li key={j} className="flex items-start gap-3 text-sm">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-white/10 text-xs font-medium text-gray-300">
                      {j + 1}
                    </span>
                    <span className="text-gray-300">{step}</span>
                  </li>
                ))}
              </ol>
            </div>
          ))}
        </div>

        {/* Flow diagram */}
        <div
          className={`mt-12 rounded-2xl border border-white/10 bg-white/3 p-8 text-center transition-all delay-700 duration-700 ${
            inView ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'
          }`}
        >
          <p className="font-mono text-sm tracking-wide text-gray-500 md:text-base">
            <span className="text-gradient-brand font-semibold">Healthy Hand</span>
            {' \u2192 Capture \u2192 Compute Angles \u2192 '}
            <span className="text-white">Store Reference</span>
            {' \u2192 '}
            <span className="text-gradient-brand font-semibold">Damaged Hand</span>
            {' \u2192 Compare \u2192 '}
            <span className="text-white">Feedback</span>
          </p>
        </div>
      </div>
    </section>
  )
}
