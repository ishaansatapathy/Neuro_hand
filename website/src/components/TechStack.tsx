import useInView from '../hooks/useInView'
import useSpotlight from '../hooks/useSpotlight'
import SectionHeading from './SectionHeading'

const SOFTWARE = [
  { name: 'MediaPipe', role: 'Hand & pose tracking (21 landmarks)', category: 'Vision' },
  { name: 'OpenCV', role: 'Camera capture, frame processing, overlays', category: 'Vision' },
  { name: 'scikit-learn', role: 'Random Forest, SVM, ensemble classifiers', category: 'ML' },
  { name: 'PyTorch', role: 'EfficientNet-B0 brain scan classifier', category: 'ML' },
  { name: 'NumPy / Pandas', role: 'Feature engineering, data pipelines', category: 'Data' },
  { name: 'React + Vite', role: 'Dashboard & progress UI', category: 'Frontend' },
  { name: 'Tailwind CSS', role: 'Styling & responsive design', category: 'Frontend' },
]

const HARDWARE = [
  { name: 'ESP32', role: 'Central microcontroller — serial/WiFi comms between sensors and software' },
  { name: 'Flex Sensors', role: 'Resistance-based finger bend detection — analog curl data' },
  { name: 'MPU6050', role: '6-axis IMU — hand tilt, rotation, movement speed' },
  { name: 'Vibration Motor', role: 'Haptic feedback — intensity scales with deviation error' },
]

export default function TechStack() {
  const { ref, inView } = useInView()
  const { onMouseMove } = useSpotlight()

  return (
    <section id="tech" className="noise-overlay relative overflow-hidden bg-background px-6 py-24 text-foreground md:px-12 lg:px-16">
      <div className="glow-blob right-[-10%] top-[20%] h-[500px] w-[500px] bg-cyan-500/10" />
      <div className="gradient-divider mx-auto mb-24 max-w-4xl" />

      <div ref={ref} className="relative z-10 mx-auto max-w-6xl">
        <SectionHeading
          label="Technology"
          title="Built with precision, not complexity."
          subtitle="Open-source AI libraries, affordable embedded hardware, and a clean React frontend — production-grade stack, student budget."
          inView={inView}
        />

        <div className="grid gap-8 lg:grid-cols-2">
          {/* Software */}
          <div
            onMouseMove={onMouseMove}
            className={`card-spotlight liquid-glass rounded-2xl border border-white/10 p-8 transition-all duration-700 hover:border-white/20 ${
              inView ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0'
            }`}
            style={{ transitionDelay: '400ms' }}
          >
            <h3 className="text-gradient mb-6 text-xl font-semibold">Software Stack</h3>
            <div className="space-y-4">
              {SOFTWARE.map((item) => (
                <div key={item.name} className="flex items-start justify-between gap-4">
                  <div>
                    <span className="font-medium">{item.name}</span>
                    <p className="mt-0.5 text-sm text-gray-400">{item.role}</p>
                  </div>
                  <span className="shrink-0 rounded-full bg-white/10 px-2.5 py-0.5 text-xs text-gray-400">
                    {item.category}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Hardware */}
          <div
            onMouseMove={onMouseMove}
            className={`card-spotlight liquid-glass rounded-2xl border border-white/10 p-8 transition-all duration-700 hover:border-white/20 ${
              inView ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0'
            }`}
            style={{ transitionDelay: '600ms' }}
          >
            <h3 className="text-gradient mb-6 text-xl font-semibold">Hardware Components</h3>
            <div className="space-y-4">
              {HARDWARE.map((item) => (
                <div
                  key={item.name}
                  className="rounded-xl border border-white/5 bg-white/3 p-4 transition-colors duration-200 hover:border-white/10"
                >
                  <span className="font-medium">{item.name}</span>
                  <p className="mt-1 text-sm text-gray-400">{item.role}</p>
                </div>
              ))}
            </div>

            <div className="mt-6 rounded-xl bg-white/3 p-4">
              <p className="font-mono text-xs leading-relaxed text-gray-500">
                Flex Sensors ──┐<br />
                {'               '}\u251C── ESP32 ── Serial ── Python Backend<br />
                MPU6050 ───────┘{'                            '}\u2502<br />
                {'                                          '}\u25BC<br />
                Vibration Motor \u25C4── ESP32 \u25C4── Feedback ──────┘
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
