import { useEffect, useState } from 'react'

interface AnimatedTextProps {
  text: string
  className?: string
  delay?: number
  stagger?: number
  as?: 'h1' | 'h2' | 'h3' | 'p' | 'span'
}

export default function AnimatedText({
  text,
  className = '',
  delay = 200,
  stagger = 40,
  as: Tag = 'h2',
}: AnimatedTextProps) {
  const [triggered, setTriggered] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => setTriggered(true), delay)
    return () => clearTimeout(timer)
  }, [delay])

  const words = text.split(' ')

  return (
    <Tag className={className}>
      {words.map((word, i) => (
        <span key={i} className="inline-block overflow-hidden mr-[0.3em]">
          <span
            className="inline-block transition-all"
            style={{
              opacity: triggered ? 1 : 0,
              transform: triggered ? 'translateY(0)' : 'translateY(110%)',
              transitionDuration: '600ms',
              transitionTimingFunction: 'cubic-bezier(0.16, 1, 0.3, 1)',
              transitionDelay: `${i * stagger}ms`,
            }}
          >
            {word}
          </span>
        </span>
      ))}
    </Tag>
  )
}
