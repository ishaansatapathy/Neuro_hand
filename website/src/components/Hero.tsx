import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown, Sparkles, Play } from 'lucide-react'
const LOGO_URL = '/rehab-twin-logo.png'

const VIDEO_URL =
  'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260416_101255_3099d3e4-d0cf-4e59-9666-97fbf521ac71.mp4'
const FADE_SEC = 0.5

const NAV_ITEMS: { label: string; href: string; chevron?: boolean }[] = [
  { label: 'How it works', href: '#how-it-works' },
  { label: 'Features', href: '#features', chevron: true },
  { label: 'Stack', href: '#tech', chevron: true },
  { label: 'Impact', href: '#stats' },
]

const MARQUEE_BRANDS = ['MediaPipe', 'OpenCV', 'PyTorch', 'scikit-learn', 'React', 'ESP32', 'NumPy', 'Vite']

function LogoMarqueeItem({ name }: { name: string }) {
  return (
    <div className="flex shrink-0 items-center gap-3 group cursor-default">
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/5 border border-white/8 text-xs font-bold text-foreground/60 transition-all duration-300 group-hover:bg-white/10 group-hover:scale-110">
        {name[0]}
      </div>
      <span className="text-sm font-medium text-foreground/35 transition-colors duration-300 group-hover:text-foreground/60">{name}</span>
    </div>
  )
}

export default function Hero() {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [videoOpacity, setVideoOpacity] = useState(0)
  const [step, setStep] = useState(0)

  /* Video fade-in / fade-out loop */
  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    let rafId = 0
    let cancelled = false

    const tick = () => {
      if (cancelled) return
      const v = videoRef.current
      if (!v) return
      const d = v.duration
      const t = v.currentTime
      let o = 0
      if (d && !Number.isNaN(d) && d > 0) {
        if (t < FADE_SEC) o = t / FADE_SEC
        else if (t > d - FADE_SEC) o = Math.max(0, (d - t) / FADE_SEC)
        else o = 1
      }
      setVideoOpacity(o)
      rafId = requestAnimationFrame(tick)
    }

    const onEnded = () => {
      setVideoOpacity(0)
      setTimeout(() => {
        const el = videoRef.current
        if (!el) return
        el.currentTime = 0
        el.play().catch(() => {})
      }, 100)
    }
    const onLoaded = () => video.play().catch(() => {})

    video.addEventListener('ended', onEnded)
    video.addEventListener('loadeddata', onLoaded)
    rafId = requestAnimationFrame(tick)

    return () => {
      cancelled = true
      cancelAnimationFrame(rafId)
      video.removeEventListener('ended', onEnded)
      video.removeEventListener('loadeddata', onLoaded)
    }
  }, [])

  useEffect(() => {
    const timers = [
      setTimeout(() => setStep(1), 300),
      setTimeout(() => setStep(2), 600),
      setTimeout(() => setStep(3), 1000),
      setTimeout(() => setStep(4), 1400),
    ]
    return () => timers.forEach(clearTimeout)
  }, [])

  return (
    <section className="relative flex min-h-screen flex-col overflow-hidden text-foreground" style={{ background: '#0c0a12' }}>
      {/* ── FULLSCREEN VIDEO ── */}
      <div className="absolute inset-0 z-0 overflow-hidden">
        <video
          ref={videoRef}
          className="absolute inset-0 h-full w-full object-cover"
          style={{ opacity: videoOpacity }}
          src={VIDEO_URL}
          muted
          playsInline
          preload="auto"
        />
      </div>

      {/* Minimal vignette — just enough for text readability, NOT blocking video */}
      <div className="pointer-events-none absolute inset-0 z-[1]" style={{ background: 'radial-gradient(ellipse at center, transparent 30%, rgba(5,0,16,0.4) 100%)' }} />
      {/* Bottom fade to merge into next section */}
      <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-40 z-[1] bg-gradient-to-t from-[#0c0a12] to-transparent" />

      {/* ── CONTENT ── */}
      <div className="relative z-10 flex min-h-screen flex-col">
        {/* Navbar */}
        <nav className="flex w-full items-center justify-between px-6 py-5 md:px-10 lg:px-16">
          <Link to="/" className="group flex items-center rounded-lg bg-white/95 px-2 py-1 shadow-sm ring-1 ring-black/5 transition-all duration-300 hover:bg-white hover:shadow-md md:px-2.5 md:py-1.5">
            <img
              src={LOGO_URL}
              alt="RehabTwin"
              className="h-8 w-auto max-h-9 object-contain object-left md:h-9"
            />
          </Link>
          <div className="hidden md:flex items-center gap-1">
            {NAV_ITEMS.map((item) => (
              <a key={item.label} href={item.href}
                className="relative flex items-center gap-1 px-4 py-2 rounded-full text-sm text-white/60 transition-all duration-300 hover:text-white hover:bg-white/5 backdrop-blur-sm group">
                {item.label}
                {item.chevron && <ChevronDown className="h-3.5 w-3.5 opacity-40 transition-transform group-hover:rotate-180" strokeWidth={2.5} />}
              </a>
            ))}
          </div>
          <Link to="/scan" className="inline-flex items-center gap-2 rounded-full bg-white/[0.08] border border-white/15 px-5 py-2.5 text-sm font-medium text-white backdrop-blur-md transition-all duration-300 hover:bg-white/[0.14] hover:border-white/25">
            <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.5)]" />
            Start Analysis
          </Link>
        </nav>

        <div className="mx-auto h-px w-full max-w-[calc(100%-3rem)] bg-gradient-to-r from-transparent via-white/10 to-transparent" />

        {/* Hero text — LEFT BOTTOM corner */}
        <div className="flex flex-1 items-end px-6 md:px-10 lg:px-16 pb-28">
          <div className="max-w-2xl">
            {/* Badge */}
            <div className={`mb-6 inline-flex items-center gap-2.5 rounded-full border border-white/15 bg-white/[0.06] px-5 py-2.5 text-sm backdrop-blur-md transition-all duration-700 ${step >= 1 ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-3'}`}>
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-purple-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-purple-500" />
              </span>
              <span className="text-white/80 font-medium">Track. Train. Recover.</span>
            </div>

            {/* Title */}
            <h1 className={`font-bold leading-[0.92] tracking-[-0.04em] transition-all duration-1000 ease-out ${step >= 2 ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}
              style={{ fontFamily: 'var(--font-heading)', fontSize: 'clamp(3rem, 8vw, 7.5rem)' }}>
              <span className="text-[#e8f4fc] drop-shadow-[0_2px_20px_rgba(0,0,0,0.5)]">Rehab</span>
              <span className="text-[#2dd4bf] drop-shadow-[0_2px_20px_rgba(0,0,0,0.35)]">Twin</span>
            </h1>

            {/* Subtitle */}
            <p className={`mt-5 max-w-lg text-lg leading-relaxed transition-all duration-700 ${step >= 3 ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6'}`}>
              <span className="text-white/70 drop-shadow-[0_1px_8px_rgba(0,0,0,0.6)]">Recovery isn't one-size-fits-all. </span>
              <span className="text-white font-semibold drop-shadow-[0_1px_8px_rgba(0,0,0,0.6)]">Your healthy hand teaches the other.</span>
            </p>

            {/* Buttons */}
            <div className={`mt-8 flex flex-wrap items-center gap-4 transition-all duration-700 ${step >= 4 ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6'}`}>
              <Link to="/scan"
                className="group relative inline-flex items-center gap-2.5 rounded-2xl px-8 py-4 text-base font-semibold text-white overflow-hidden transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_8px_40px_rgba(139,92,246,0.4)]"
                style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6, #a855f7)' }}>
                <div className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/20 to-white/0 -translate-x-full group-hover:translate-x-full transition-transform duration-700" />
                <Sparkles className="w-5 h-5 relative z-10" />
                <span className="relative z-10">Upload Brain Scan</span>
              </Link>
              <Link to="/session"
                className="group inline-flex items-center gap-2.5 rounded-2xl border border-white/15 bg-white/[0.06] backdrop-blur-md px-8 py-4 text-base font-medium text-white/80 transition-all duration-300 hover:bg-white/[0.12] hover:border-white/25 hover:-translate-y-0.5">
                <Play className="w-4 h-4 text-purple-400" />
                Start Rehab
              </Link>
            </div>
          </div>
        </div>

        {/* Marquee */}
        <div className="border-t border-white/[0.06]">
          <div className="mx-auto flex w-full max-w-7xl items-center gap-8 px-6 py-7 md:px-10 lg:px-16">
            <p className="text-[10px] uppercase tracking-[0.2em] text-foreground/20 font-bold shrink-0">Powered by</p>
            <div className="min-w-0 flex-1 overflow-hidden">
              <div className="flex w-max gap-14 animate-marquee">
                {[...MARQUEE_BRANDS, ...MARQUEE_BRANDS].map((name, i) => (
                  <LogoMarqueeItem key={`${name}-${i}`} name={name} />
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
