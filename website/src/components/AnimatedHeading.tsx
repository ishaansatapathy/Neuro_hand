import { useEffect, useState } from 'react'

interface AnimatedHeadingProps {
  text: string
  className?: string
  initialDelay?: number
  charDelay?: number
  charDuration?: number
}

export default function AnimatedHeading({
  text,
  className = '',
  initialDelay = 200,
  charDelay = 30,
  charDuration = 500,
}: AnimatedHeadingProps) {
  const [triggered, setTriggered] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => setTriggered(true), initialDelay)
    return () => clearTimeout(timer)
  }, [initialDelay])

  const lines = text.split('\n')

  return (
    <h1 className={className} style={{ letterSpacing: '-0.04em' }}>
      {lines.map((line, lineIndex) => {
        const chars = line.split('')

        const rendered = chars.map((char, charIndex) => {
          const delay = (lineIndex * line.length * charDelay) + (charIndex * charDelay)

          return (
            <span
              key={`${lineIndex}-${charIndex}`}
              className="inline-block"
              style={{
                opacity: triggered ? 1 : 0,
                transform: triggered ? 'translateX(0)' : 'translateX(-18px)',
                transition: `opacity ${charDuration}ms ease, transform ${charDuration}ms ease`,
                transitionDelay: `${delay}ms`,
              }}
            >
              {char === ' ' ? '\u00A0' : char}
            </span>
          )
        })

        return (
          <span key={lineIndex} className="block">
            {rendered}
          </span>
        )
      })}
    </h1>
  )
}
