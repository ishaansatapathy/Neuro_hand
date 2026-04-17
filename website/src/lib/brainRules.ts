export type LesionSide = 'left' | 'right' | null

export type BrainRegion = 'frontal' | 'parietal' | 'temporal' | 'occipital' | 'deep' | 'lateral' | 'brainstem'

export interface AffectedZone {
  zone: string
  region: BrainRegion
  severity: number
  effects: string[]
}

export interface StrokeAnalysis {
  stroke_type: string
  description: string
  affected_zones: AffectedZone[]
  neuroplasticity_targets: string[]
  recovery_potential: string
  predicted_class: string
  confidence: number
}

export function contralateralBodySide(lesion: 'left' | 'right'): 'right' | 'left' {
  return lesion === 'left' ? 'right' : 'left'
}

export function lesionSummary(lesion: 'left' | 'right', profileLabel: string): string {
  const body = contralateralBodySide(lesion)
  return `${profileLabel}: lesion shown on the ${lesion} hemisphere (illustrative). Many motor/sensory effects can appear on the ${body} side of the body (contralateral to the lesion).`
}

export const REGION_COLORS: Record<BrainRegion, string> = {
  frontal: '#ef4444',
  parietal: '#f59e0b',
  temporal: '#10b981',
  occipital: '#6366f1',
  deep: '#ec4899',
  lateral: '#f97316',
  brainstem: '#8b5cf6',
}

export const REGION_POSITIONS: Record<BrainRegion, [number, number, number]> = {
  frontal:   [ 0,    0.25,  0.3 ],
  parietal:  [ 0,    0.35, -0.05],
  temporal:  [ 0.35, -0.1,   0.05],
  occipital: [ 0,    0.1,  -0.35],
  deep:      [ 0,    0.0,   0.0 ],
  lateral:   [ 0.3,  0.15,  0.15],
  brainstem: [ 0,   -0.3,  -0.15],
}
