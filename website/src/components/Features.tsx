import useInView from '../hooks/useInView'
import useSpotlight from '../hooks/useSpotlight'
import SectionHeading from './SectionHeading'

const FEATURES = [
  {
    title: 'Personalized Reference',
    desc: "Your own healthy hand creates the benchmark — not a generic database. Whether you're 25 or 70, the targets adapt to your body.",
  },
  {
    title: 'Real-Time Feedback',
    desc: 'Frame-by-frame comparison at 30 FPS. Every second of practice is guided with on-screen arrows and color-coded joint overlays.',
  },
  {
    title: 'AI Gesture Detection',
    desc: 'Ensemble ML models (Random Forest + Gradient Boosting) classify gestures and score movement quality with deviation analysis.',
  },
  {
    title: 'Haptic Vibration',
    desc: 'ESP32-driven vibration motor gives physical nudges scaled to error magnitude — feel corrections without looking at the screen.',
  },
  {
    title: 'Brain Scan Analysis',
    desc: 'EfficientNet-B0 classifies MRI scans across 7 neurological conditions — helping stratify patients and inform recovery goals.',
  },
  {
    title: 'Gamified Recovery',
    desc: 'Score streaks, guided exercises, and session-by-session progress tracking turn repetitive rehab into an engaging challenge.',
  },
  {
    title: 'Progress Tracking',
    desc: 'Every session is logged with scores, joint angles, and improvement trends. Therapists can review data remotely.',
  },
  {
    title: 'Home-Ready',
    desc: 'Standard webcam + affordable ESP32 components. Total hardware cost under Rs.2,000. No clinic visits needed for daily practice.',
  },
]

export default function Features() {
  const { ref, inView } = useInView()
  const { onMouseMove } = useSpotlight()

  return (
    <section id="features" className="noise-overlay relative bg-background px-6 py-24 text-foreground md:px-12 lg:px-16">
      <div className="gradient-divider mx-auto mb-24 max-w-4xl" />

      <div ref={ref} className="relative z-10 mx-auto max-w-6xl">
        <SectionHeading
          label="Features"
          title="Everything recovery needs, in one system."
          subtitle="Multi-modal feedback, personalized AI, and affordable hardware — designed for daily home use."
          inView={inView}
        />

        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((feat, i) => (
            <div
              key={feat.title}
              onMouseMove={onMouseMove}
              className={`card-spotlight group rounded-2xl border border-white/10 bg-white/3 p-6 transition-all duration-700 hover:border-white/20 hover:bg-white/6 ${
                inView ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0'
              }`}
              style={{ transitionDelay: `${300 + i * 100}ms` }}
            >
              <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-white/10 transition-colors duration-300 group-hover:bg-white/20">
                <span className="text-sm font-semibold text-gray-300">
                  {String(i + 1).padStart(2, '0')}
                </span>
              </div>
              <h3 className="mb-2 text-base font-semibold">{feat.title}</h3>
              <p className="text-sm leading-relaxed text-gray-400">{feat.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
