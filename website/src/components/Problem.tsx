import useInView from '../hooks/useInView'
import useSpotlight from '../hooks/useSpotlight'
import SectionHeading from './SectionHeading'

const PROBLEMS = [
  {
    stat: '2-3',
    unit: 'sessions / week',
    title: 'Limited Therapy Access',
    desc: 'Patients typically get only 2-3 physiotherapy sessions per week, each lasting 30-45 minutes. Recovery needs daily practice.',
  },
  {
    stat: '0',
    unit: 'guidance at home',
    title: 'No Feedback Loop',
    desc: 'Between sessions, patients practice alone with no real-time feedback — often performing movements incorrectly or giving up entirely.',
  },
  {
    stat: '80%',
    unit: 'subjective assessment',
    title: 'Manual Progress Tracking',
    desc: 'Therapists rely on visual observation during visits. Progress is subjective, infrequent, and easy to misjudge.',
  },
  {
    stat: '60%',
    unit: 'lack access',
    title: 'Rural Inequality',
    desc: 'In semi-urban and rural areas, qualified physiotherapists are scarce and expensive — millions are left without proper care.',
  },
]

export default function Problem() {
  const { ref, inView } = useInView()
  const { onMouseMove } = useSpotlight()

  return (
    <section id="problem" className="noise-overlay relative bg-background px-6 py-24 text-foreground md:px-12 lg:px-16">
      <div className="gradient-divider mx-auto mb-24 max-w-4xl" />

      <div ref={ref} className="relative z-10 mx-auto max-w-6xl">
        <SectionHeading
          label="The Problem"
          title="Recovery shouldn't stop at the clinic door."
          subtitle="Every year millions suffer strokes worldwide. The most common aftereffect — loss of motor control in one hand. Recovery demands consistent, guided repetition that today's system simply cannot provide."
          inView={inView}
        />

        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {PROBLEMS.map((item, i) => (
            <div
              key={item.title}
              onMouseMove={onMouseMove}
              className={`card-spotlight liquid-glass rounded-2xl border border-white/10 p-6 transition-all duration-700 hover:border-white/20 ${
                inView ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0'
              }`}
              style={{ transitionDelay: `${400 + i * 150}ms` }}
            >
              <div className="mb-4">
                <span className="text-gradient-brand text-4xl font-semibold">{item.stat}</span>
                <span className="ml-2 text-sm text-gray-500">{item.unit}</span>
              </div>
              <h3 className="mb-2 text-lg font-medium">{item.title}</h3>
              <p className="text-sm leading-relaxed text-gray-400">{item.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
