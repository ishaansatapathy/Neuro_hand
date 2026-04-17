import { useEffect, useState } from 'react'

interface AnimatedCounterProps {
  value: string
  inView: boolean
  duration?: number
}

export default function AnimatedCounter({ value, inView, duration = 1500 }: AnimatedCounterProps) {
  const [display, setDisplay] = useState(value)

  useEffect(() => {
    if (!inView) return

    const numericMatch = value.match(/^([\d,.]+)(.*)$/)
    if (!numericMatch) {
      setDisplay(value)
      return
    }

    const target = parseFloat(numericMatch[1].replace(/,/g, ''))
    const suffix = numericMatch[2]
    const prefix = value.match(/^([^\d]*)/)?.[1] ?? ''
    const hasComma = numericMatch[1].includes(',')
    const steps = 40
    const stepTime = duration / steps

    let current = 0
    let step = 0
    const timer = setInterval(() => {
      step++
      const progress = step / steps
      const eased = 1 - Math.pow(1 - progress, 3)
      current = Math.round(eased * target)

      const formatted = hasComma ? current.toLocaleString() : String(current)
      setDisplay(`${prefix}${formatted}${suffix}`)

      if (step >= steps) {
        setDisplay(value)
        clearInterval(timer)
      }
    }, stepTime)

    return () => clearInterval(timer)
  }, [inView, value, duration])

  return <>{display}</>
}
