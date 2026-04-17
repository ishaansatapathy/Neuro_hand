/**
 * Imperative API for 3D brain region highlight (optional — BrainScene may not subscribe).
 * highlightRegion('motor_cortex' | 'deep_brain' | 'none')
 * resetBrain()
 */
export type BrainRegionName = 'motor_cortex' | 'deep_brain' | 'none'

type Listener = (region: BrainRegionName | null) => void

const listeners = new Set<Listener>()

export function subscribeBrainHighlight(fn: Listener): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export function highlightRegion(regionName: BrainRegionName): void {
  const r = regionName === 'none' ? null : regionName
  listeners.forEach((l) => l(r))
}

export function resetBrain(): void {
  listeners.forEach((l) => l(null))
}
