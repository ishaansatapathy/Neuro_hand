import { Eye, Cpu, Database, Layout, Cog, Smartphone } from 'lucide-react'
import useInView from '../hooks/useInView'
import SectionHeading from './SectionHeading'

const SOFTWARE = [
  { name: 'MediaPipe', role: 'Hand & pose tracking (21 landmarks)', cat: 'Vision', icon: Eye, color: '#60a5fa' },
  { name: 'OpenCV', role: 'Camera capture, frame processing', cat: 'Vision', icon: Eye, color: '#60a5fa' },
  { name: 'scikit-learn', role: 'Random Forest, SVM, ensemble classifiers', cat: 'ML', icon: Cpu, color: '#a78bfa' },
  { name: 'PyTorch', role: 'EfficientNet-B0 brain scan classifier', cat: 'ML', icon: Cpu, color: '#a78bfa' },
  { name: 'NumPy / Pandas', role: 'Feature engineering, data pipelines', cat: 'Data', icon: Database, color: '#22d3ee' },
  { name: 'React + Vite', role: 'Dashboard & progress UI', cat: 'Frontend', icon: Layout, color: '#f472b6' },
  { name: 'Tailwind CSS', role: 'Styling & responsive design', cat: 'Frontend', icon: Layout, color: '#f472b6' },
]

const HARDWARE = [
  { name: 'ESP32', role: 'Central microcontroller', icon: Cpu, color: '#fbbf24' },
  { name: 'Flex Sensors', role: 'Finger bend detection', icon: Cog, color: '#fb923c' },
  { name: 'MPU6050', role: '6-axis IMU', icon: Smartphone, color: '#34d399' },
  { name: 'Vibration Motor', role: 'Haptic feedback', icon: Cog, color: '#f472b6' },
]

export default function TechStack() {
  const { ref, inView } = useInView()

  return (
    <section id="tech" className="relative overflow-hidden px-6 py-28 md:px-10 lg:px-16" style={{ background: 'var(--bg-root)' }}>
      <div className="ambient-glow w-[400px] h-[400px] bg-cyan-600/5 right-[-5%] top-[20%]" />
      <div className="gradient-divider mx-auto mb-20 max-w-5xl" />

      <div ref={ref} className="relative z-10 mx-auto max-w-6xl">
        <SectionHeading label="Technology" title="Built with precision, not complexity." subtitle="Open-source AI, affordable hardware, clean React frontend." inView={inView} />

        <div className="grid gap-4 lg:grid-cols-2">
          {/* Software */}
          <div className={`rounded-xl border border-white/[0.05] p-6 transition-all duration-500 ${inView ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'}`}
            style={{ transitionDelay: '350ms', background: 'var(--bg-card)' }}>
            <h3 className="mb-5 text-base font-bold flex items-center gap-2.5">
              <div className="h-7 w-7 rounded-md bg-purple-500/10 border border-purple-500/15 flex items-center justify-center"><Cpu className="w-3.5 h-3.5 text-purple-400" /></div>
              <span className="text-gradient-brand">Software Stack</span>
            </h3>
            <div className="space-y-1.5">
              {SOFTWARE.map((item) => {
                const Icon = item.icon
                return (
                  <div key={item.name} className="flex items-center justify-between gap-3 hover:bg-white/[0.015] rounded-lg p-2 -mx-2 transition-colors">
                    <div className="flex items-center gap-2.5">
                      <div className="w-6 h-6 rounded flex items-center justify-center shrink-0" style={{ background: `${item.color}10` }}>
                        <Icon className="w-3 h-3" style={{ color: item.color }} />
                      </div>
                      <div>
                        <span className="text-sm font-medium text-foreground">{item.name}</span>
                        <p className="text-[11px] text-foreground/25">{item.role}</p>
                      </div>
                    </div>
                    <span className="shrink-0 rounded px-1.5 py-0.5 text-[9px] font-bold" style={{ background: `${item.color}08`, color: item.color, border: `1px solid ${item.color}15` }}>{item.cat}</span>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Hardware */}
          <div className={`rounded-xl border border-white/[0.05] p-6 transition-all duration-500 ${inView ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'}`}
            style={{ transitionDelay: '500ms', background: 'var(--bg-card)' }}>
            <h3 className="mb-5 text-base font-bold flex items-center gap-2.5">
              <div className="h-7 w-7 rounded-md bg-amber-500/10 border border-amber-500/15 flex items-center justify-center"><Cog className="w-3.5 h-3.5 text-amber-400" /></div>
              <span className="text-gradient-brand">Hardware</span>
            </h3>
            <div className="space-y-2.5">
              {HARDWARE.map((item) => {
                const Icon = item.icon
                return (
                  <div key={item.name} className="group rounded-lg border border-white/[0.04] p-3.5 hover:border-white/[0.08] hover:bg-white/[0.01] transition-all"
                    style={{ background: 'rgba(255,255,255,0.008)' }}>
                    <div className="flex items-center gap-2.5">
                      <div className="w-8 h-8 rounded-md flex items-center justify-center shrink-0 transition-transform group-hover:scale-110" style={{ background: `${item.color}10` }}>
                        <Icon className="w-4 h-4" style={{ color: item.color }} />
                      </div>
                      <div><span className="text-sm font-medium text-foreground">{item.name}</span><p className="text-[11px] text-foreground/25">{item.role}</p></div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
