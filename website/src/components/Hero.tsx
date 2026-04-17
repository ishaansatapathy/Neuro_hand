import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown } from 'lucide-react'
import logoMark from '../assets/logo.svg'

const VIDEO_URL =
  'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260328_065045_c44942da-53c6-4804-b734-f9e07fc22e08.mp4'

const FADE_SEC = 0.5

const NAV_ITEMS: { label: string; href: string; chevron?: boolean }[] = [
  { label: 'How it works', href: '#how-it-works' },
  { label: 'Features', href: '#features', chevron: true },
  { label: 'Stack', href: '#tech', chevron: true },
  { label: 'Impact', href: '#stats' },
]

const MARQUEE_BRANDS = ['Vortex', 'Nimbus', 'Prysma', 'Cirrus', 'Kynder', 'Halcyn']

function LogoMarqueeItem({ name }: { name: string }) {
  const letter = name[0] ?? '?'
  return (
    <div className="flex shrink-0 items-center gap-3">
      <div className="liquid-glass flex h-6 w-6 items-center justify-center rounded-lg text-xs font-semibold text-foreground">
        {letter}
      </div>
      <span className="text-base font-semibold text-foreground">{name}</span>
    </div>
  )
}

export default function Hero() {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [videoOpacity, setVideoOpacity] = useState(0)

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

    const onLoaded = () => {
      video.play().catch(() => {})
    }

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

  return (
    <section className="relative flex min-h-screen flex-col overflow-visible bg-background text-foreground">
      {/* Video (no gradient overlays) */}
      <div className="absolute inset-0 overflow-hidden">
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

      {/* Blurred center shape — behind content */}
      <div
        className="pointer-events-none absolute left-1/2 top-1/2 z-1 h-[527px] w-[984px] max-w-[95vw] -translate-x-1/2 -translate-y-1/2 bg-gray-950 opacity-90 blur-[82px]"
        aria-hidden
      />

      <div className="relative z-10 flex min-h-screen flex-col">
        {/* Navbar */}
        <nav className="flex w-full flex-row items-center justify-between px-8 py-5">
          <Link to="/" className="flex items-center gap-2.5">
            <img src={logoMark} alt="NeuroHand" className="h-8 w-auto" />
          </Link>

          <div className="hidden items-center gap-8 md:flex">
            {NAV_ITEMS.map((item) => (
              <a
                key={item.label}
                href={item.href}
                className="flex items-center gap-1 text-sm text-foreground/90 transition-colors hover:text-foreground"
              >
                {item.label}
                {item.chevron && <ChevronDown className="h-4 w-4 opacity-70" strokeWidth={2} />}
              </a>
            ))}
          </div>

          <Link to="/scan" className="btn-hero-secondary rounded-full px-4 py-2 text-sm font-medium">
            Brain scan
          </Link>
        </nav>

        {/* Divider under navbar */}
        <div
          className="mx-auto mt-[3px] h-px w-full max-w-[calc(100%-4rem)] bg-linear-to-r from-transparent via-foreground/20 to-transparent"
          aria-hidden
        />

        {/* Hero copy — vertically centered */}
        <div className="flex flex-1 flex-col items-center justify-center px-6 pt-4 pb-8 md:px-8">
          <h1
            className="font-heading max-w-[100vw] text-center font-normal leading-[1.02] tracking-[-0.024em] text-[clamp(3rem,14vw,13.75rem)]"
            style={{ fontFamily: "'General Sans', var(--font-heading), sans-serif" }}
          >
            <span className="text-foreground">Neuro</span>
            <span
              className="bg-clip-text text-transparent"
              style={{
                backgroundImage: 'linear-gradient(to left, #6366f1, #a855f7, #fcd34d)',
              }}
            >
              Hand
            </span>
          </h1>

          <p className="text-hero-sub mt-[9px] max-w-xl text-center text-lg leading-8 opacity-80">
            Brain CT classification → guided 3D regions → hand rehab with MediaPipe,
            <br />
            personalized sessions, and haptic feedback. Built for neuro recovery.
          </p>

          <div className="mt-[25px] flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
            <Link
              to="/scan"
              className="btn-hero-secondary px-[29px] py-[20px] text-base font-medium"
            >
              Upload brain scan
            </Link>
            <Link
              to="/session"
              className="rounded-full border border-white/20 bg-white/5 px-8 py-[20px] text-base font-medium text-foreground/90 transition-colors hover:border-white/35 hover:bg-white/10"
            >
              Start rehab
            </Link>
          </div>
        </div>

        {/* Logo marquee — bottom */}
        <div className="mx-auto flex w-full max-w-5xl flex-col items-stretch gap-6 px-6 pb-10 md:flex-row md:items-center md:justify-between md:gap-12">
          <p className="text-sm text-foreground/50 md:max-w-[220px]">
            Stack &amp; partners
            <br />
            we build on
          </p>

          <div className="min-w-0 flex-1 overflow-hidden">
            <div className="flex w-max gap-16 animate-marquee">
              {[...MARQUEE_BRANDS, ...MARQUEE_BRANDS].map((name, i) => (
                <LogoMarqueeItem key={`${name}-${i}`} name={name} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
