import { useEffect, useState } from 'react'

/** Avoids hanging Suspense when the GLB in `public/` is missing (dev server returns 404). */
export function useGlbAvailable(url: string): 'checking' | 'yes' | 'no' {
  const [state, setState] = useState<'checking' | 'yes' | 'no'>('checking')

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        let r = await fetch(url, { method: 'HEAD' })
        if (cancelled) return
        if (r.ok) {
          setState('yes')
          return
        }
        // Some static hosts don't support HEAD; try a tiny ranged GET.
        r = await fetch(url, { headers: { Range: 'bytes=0-0' } })
        if (cancelled) return
        setState(r.ok || r.status === 206 ? 'yes' : 'no')
      } catch {
        if (!cancelled) setState('no')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [url])

  return state
}
