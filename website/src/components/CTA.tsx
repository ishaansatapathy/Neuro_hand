import { Link } from 'react-router-dom'
import useInView from '../hooks/useInView'

export default function CTA() {
  const { ref, inView } = useInView()

  return (
    <section id="contact" className="noise-overlay relative overflow-hidden bg-background px-6 py-32 text-foreground md:px-12 lg:px-16">
      <div className="glow-blob left-[50%] top-[50%] h-[600px] w-[600px] -translate-x-1/2 -translate-y-1/2 bg-purple-600/15" />
      <div className="gradient-divider mx-auto mb-24 max-w-4xl" />

      <div ref={ref} className="relative z-10 mx-auto max-w-4xl text-center">
        <h2
          className={`text-gradient mb-4 text-3xl font-semibold tracking-tight transition-all duration-700 md:text-4xl lg:text-5xl ${
            inView ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'
          }`}
          style={{ letterSpacing: '-0.03em' }}
        >
          Recovery should be personalized,
          <br />
          guided, and accessible.
        </h2>
        <p
          className={`mx-auto mb-10 max-w-xl text-base text-hero-sub transition-all delay-200 duration-700 md:text-lg ${
            inView ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'
          }`}
        >
          Not limited to clinic walls. Built for patients who need daily practice with
          intelligent feedback — right at home.
        </p>
        <div
          className={`flex flex-wrap items-center justify-center gap-4 transition-all delay-400 duration-700 ${
            inView ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'
          }`}
        >
          <Link
            to="/scan"
            className="rounded-lg bg-white px-8 py-3 font-medium text-black transition-all duration-200 hover:shadow-lg hover:shadow-white/20"
          >
            Upload a Scan
          </Link>
          <a
            href="#how-it-works"
            className="gradient-border rounded-lg bg-white/5 px-8 py-3 font-medium text-foreground transition-all duration-300 hover:bg-white hover:text-black"
          >
            Learn More
          </a>
        </div>
      </div>
    </section>
  )
}
