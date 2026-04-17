import { useCallback, type MouseEvent } from 'react'

export default function useSpotlight() {
  const onMouseMove = useCallback((e: MouseEvent<HTMLDivElement>) => {
    const el = e.currentTarget
    const rect = el.getBoundingClientRect()
    el.style.setProperty('--mouse-x', `${e.clientX - rect.left}px`)
    el.style.setProperty('--mouse-y', `${e.clientY - rect.top}px`)
  }, [])

  return { onMouseMove }
}
