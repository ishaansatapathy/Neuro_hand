interface SectionHeadingProps {
  label: string
  title: string
  subtitle?: string
  inView: boolean
}

export default function SectionHeading({ label, title, subtitle, inView }: SectionHeadingProps) {
  return (
    <div className="mb-16 max-w-2xl">
      {/* Pill badge */}
      <span
        className={`mb-5 inline-flex items-center gap-2 rounded-full border border-purple-500/20 bg-purple-500/[0.06] px-4 py-1.5 text-[11px] font-bold uppercase tracking-[0.2em] text-purple-300/70 transition-all duration-700 ${
          inView ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0'
        }`}
      >
        <span className="relative flex h-1.5 w-1.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-purple-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-purple-500" />
        </span>
        {label}
      </span>

      {/* Title */}
      <h2
        className={`mb-4 text-3xl font-bold tracking-tight text-foreground transition-all delay-200 duration-700 md:text-4xl lg:text-[2.75rem] ${
          inView ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'
        }`}
        style={{ fontFamily: 'var(--font-heading)', letterSpacing: '-0.03em', lineHeight: '1.1' }}
      >
        {title}
      </h2>

      {/* Accent line */}
      <div
        className={`mb-5 h-0.5 rounded-full bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 transition-all delay-300 duration-1000 ${
          inView ? 'w-16 opacity-100' : 'w-0 opacity-0'
        }`}
      />

      {subtitle && (
        <p
          className={`max-w-xl text-base leading-relaxed text-foreground/40 transition-all delay-400 duration-700 ${
            inView ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'
          }`}
        >
          {subtitle}
        </p>
      )}
    </div>
  )
}
