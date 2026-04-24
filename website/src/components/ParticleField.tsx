/* eslint-disable react-hooks/purity -- particle field uses random layout */
import { useMemo } from 'react'

interface ParticleFieldProps {
  count?: number
  className?: string
}

export default function ParticleField({ count = 20, className = '' }: ParticleFieldProps) {
  const particles = useMemo(() => {
    return Array.from({ length: count }, (_, i) => ({
      id: i,
      size: Math.random() * 4 + 1,
      x: Math.random() * 100,
      y: Math.random() * 100,
      duration: Math.random() * 10 + 6,
      delay: Math.random() * 5,
      opacity: Math.random() * 0.3 + 0.05,
      color: ['#6366f1', '#a855f7', '#f472b6', '#fcd34d', '#22d3ee'][
        Math.floor(Math.random() * 5)
      ],
    }))
  }, [count])

  return (
    <div className={`absolute inset-0 overflow-hidden pointer-events-none ${className}`} aria-hidden>
      {particles.map((p) => (
        <div
          key={p.id}
          className="particle"
          style={{
            width: p.size,
            height: p.size,
            left: `${p.x}%`,
            top: `${p.y}%`,
            background: p.color,
            opacity: p.opacity,
            '--duration': `${p.duration}s`,
            '--delay': `${p.delay}s`,
            boxShadow: `0 0 ${p.size * 3}px ${p.color}40`,
          } as React.CSSProperties}
        />
      ))}
    </div>
  )
}
