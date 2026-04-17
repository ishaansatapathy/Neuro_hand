interface SectionHeadingProps {
  label: string
  title: string
  subtitle?: string
  inView: boolean
}

export default function SectionHeading({ label, title, subtitle, inView }: SectionHeadingProps) {
  return (
    <div className="mb-16 text-center">
      <span
        className={`mb-4 inline-block rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs font-medium uppercase tracking-widest text-foreground/50 transition-all duration-700 ${
          inView ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0'
        }`}
      >
        {label}
      </span>
      <h2
        className={`mb-4 text-3xl font-semibold tracking-tight text-foreground transition-all delay-200 duration-700 md:text-4xl lg:text-5xl ${
          inView ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'
        }`}
        style={{ letterSpacing: '-0.03em' }}
      >
        {title}
      </h2>
      {subtitle && (
        <p
          className={`mx-auto max-w-2xl text-base text-hero-sub transition-all delay-400 duration-700 md:text-lg ${
            inView ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'
          }`}
        >
          {subtitle}
        </p>
      )}
    </div>
  )
}
