import { AlertTriangle, Wifi, BarChart3, MapPin } from 'lucide-react'
import useInView from '../hooks/useInView'
import SectionHeading from './SectionHeading'

const PROBLEMS = [
  { stat: '2-3', unit: 'sessions/week', title: 'Limited Therapy Access', desc: 'Patients typically get only 2-3 physiotherapy sessions per week. Recovery needs daily practice.', icon: AlertTriangle, color: '#f472b6' },
  { stat: '0', unit: 'home guidance', title: 'No Feedback Loop', desc: 'Between sessions, patients practice alone with no real-time feedback — often performing incorrectly.', icon: Wifi, color: '#a78bfa' },
  { stat: '80%', unit: 'subjective', title: 'Manual Tracking', desc: 'Therapists rely on visual observation. Progress is subjective, infrequent, and easy to misjudge.', icon: BarChart3, color: '#60a5fa' },
  { stat: '60%', unit: 'lack access', title: 'Rural Inequality', desc: 'In semi-urban and rural areas, qualified physiotherapists are scarce — millions left without care.', icon: MapPin, color: '#fbbf24' },
]

export default function Problem() {
  const { ref, inView } = useInView()

  return (
    <section id="problem" className="relative overflow-hidden px-6 py-28 md:px-10 lg:px-16" style={{ background: 'var(--bg-root)' }}>
      <div className="ambient-glow w-[500px] h-[500px] bg-pink-600/8 top-[20%] left-[-5%]" />
      <div className="gradient-divider mx-auto mb-20 max-w-5xl" />

      <div ref={ref} className="relative z-10 mx-auto max-w-6xl">
        <SectionHeading label="The Problem" title="Recovery shouldn't stop at the clinic door." subtitle="Every year millions suffer strokes. The most common aftereffect — loss of motor control." inView={inView} />

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {PROBLEMS.map((item, i) => {
            const Icon = item.icon
            return (
              <div key={item.title}
                className={`group relative rounded-xl border border-white/[0.05] p-6 transition-all duration-500 hover:border-white/[0.10] hover:-translate-y-1 ${inView ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0'}`}
                style={{ transitionDelay: `${250 + i * 100}ms`, background: 'var(--bg-card)' }}>

                <div className="mb-5 inline-flex h-10 w-10 items-center justify-center rounded-lg transition-transform duration-300 group-hover:scale-110"
                  style={{ background: `${item.color}12`, border: `1px solid ${item.color}20` }}>
                  <Icon className="w-5 h-5" style={{ color: item.color }} />
                </div>

                <div className="mb-3">
                  <span className="text-3xl font-bold tracking-tight" style={{ color: item.color }}>{item.stat}</span>
                  <span className="ml-1.5 text-[10px] text-foreground/25 uppercase tracking-wider">{item.unit}</span>
                </div>

                <h3 className="mb-1.5 text-sm font-semibold text-foreground">{item.title}</h3>
                <p className="text-xs leading-relaxed text-foreground/35">{item.desc}</p>

                <div className="absolute bottom-0 left-5 right-5 h-px opacity-0 group-hover:opacity-100 transition-opacity"
                  style={{ background: `linear-gradient(90deg, transparent, ${item.color}25, transparent)` }} />
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
