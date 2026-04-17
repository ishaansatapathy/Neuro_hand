/**
 * Heuristic gesture + match score from MediaPipe hand landmarks (21 points, normalized).
 * Not clinical-grade — tuned for webcam rehab UX.
 */
import type { Gesture } from '../config/gestures'
import { ARM_EXERCISE_IDS } from '../config/gestures'

export type Landmark = { x: number; y: number; z?: number }

const dist = (a: Landmark, b: Landmark) =>
  Math.hypot(a.x - b.x, a.y - b.y)

/** Thumb, index, middle, ring, pinky — true ≈ extended / open along the finger */
export function fingerStates(lm: Landmark[]): {
  thumb: boolean
  index: boolean
  middle: boolean
  ring: boolean
  pinky: boolean
  pinchDist: number
} {
  const T = (tip: number, pip: number, mcp: number) => {
    const dTipPip = dist(lm[tip], lm[pip])
    const dPipMcp = dist(lm[pip], lm[mcp])
    const dWristTip = dist(lm[0], lm[tip])
    const dWristMcp = dist(lm[0], lm[mcp])
    return dTipPip > dPipMcp * 0.78 && dWristTip > dWristMcp * 1.02
  }

  const thumbExt = dist(lm[4], lm[0]) > dist(lm[3], lm[0]) * 1.06
  const indexExt = T(8, 6, 5)
  const middleExt = T(12, 10, 9)
  const ringExt = T(16, 14, 13)
  const pinkyExt = T(20, 18, 17)

  const pinchDist = dist(lm[4], lm[8])

  return {
    thumb: thumbExt,
    index: indexExt,
    middle: middleExt,
    ring: ringExt,
    pinky: pinkyExt,
    pinchDist,
  }
}

function bitsSimilarity(
  a: { thumb: boolean; index: boolean; middle: boolean; ring: boolean; pinky: boolean },
  b: { thumb: boolean; index: boolean; middle: boolean; ring: boolean; pinky: boolean },
): number {
  let s = 0
  const keys: (keyof typeof a)[] = ['thumb', 'index', 'middle', 'ring', 'pinky']
  for (const k of keys) {
    if (a[k] === b[k]) s += 1
  }
  return s / 5
}

/** Ideal finger-open pattern per target gesture (thumb, index, middle, ring, pinky). */
const TARGET_BITS: Partial<
  Record<Gesture, { thumb: boolean; index: boolean; middle: boolean; ring: boolean; pinky: boolean }>
> = {
  open_hand: { thumb: true, index: true, middle: true, ring: true, pinky: true },
  fist: { thumb: false, index: false, middle: false, ring: false, pinky: false },
  point: { thumb: false, index: true, middle: false, ring: false, pinky: false },
  thumbs_up: { thumb: true, index: false, middle: false, ring: false, pinky: false },
  peace_sign: { thumb: false, index: true, middle: true, ring: false, pinky: false },
  ok_sign: { thumb: true, index: true, middle: false, ring: false, pinky: false },
  pinch: { thumb: true, index: true, middle: false, ring: false, pinky: false },
  flat_hand: { thumb: true, index: true, middle: true, ring: true, pinky: true },
  shaka: { thumb: true, index: false, middle: false, ring: false, pinky: true },
  rock_on: { thumb: false, index: true, middle: false, ring: false, pinky: true },
  stop_hand: { thumb: true, index: true, middle: true, ring: true, pinky: true },
  claw: { thumb: false, index: false, middle: false, ring: false, pinky: false },
  pinch_wide: { thumb: true, index: true, middle: false, ring: false, pinky: false },
  tripod_grasp: { thumb: true, index: true, middle: true, ring: false, pinky: false },
  lateral_pinch: { thumb: true, index: true, middle: false, ring: false, pinky: false },
  number_one: { thumb: false, index: true, middle: false, ring: false, pinky: false },
  number_two: { thumb: false, index: true, middle: true, ring: false, pinky: false },
  number_three: { thumb: false, index: true, middle: true, ring: true, pinky: false },
  number_four: { thumb: false, index: true, middle: true, ring: true, pinky: true },
  number_five: { thumb: true, index: true, middle: true, ring: true, pinky: true },
  relaxed_spread: { thumb: true, index: true, middle: true, ring: true, pinky: true },
  half_fist: { thumb: false, index: false, middle: false, ring: false, pinky: false },
  index_only: { thumb: false, index: true, middle: false, ring: false, pinky: false },
  thumb_out: { thumb: true, index: false, middle: false, ring: false, pinky: false },
  spread_wide: { thumb: true, index: true, middle: true, ring: true, pinky: true },
}

export function classifyGestureFromLandmarks(lm: Landmark[]): Gesture | null {
  const f = fingerStates(lm)
  const { thumb, index, middle, ring, pinky, pinchDist } = f

  if (pinchDist < 0.09 && thumb && index) return 'pinch'
  if (thumb && index && middle && !ring && !pinky && pinchDist > 0.12) return 'ok_sign'
  if (!thumb && index && middle && !ring && !pinky) return 'peace_sign'
  if (!thumb && index && !middle && !ring && !pinky) return 'point'
  if (thumb && !index && !middle && !ring && !pinky) return 'thumbs_up'
  if (thumb && index && middle && ring && pinky) return 'open_hand'
  if (!thumb && !index && !middle && !ring && !pinky) return 'fist'
  if (thumb && index && middle && !ring && pinky) return 'shaka'
  if (!thumb && index && !middle && ring && pinky) return 'rock_on'
  if (index && middle && ring && pinky && !thumb) return 'number_four'
  if (index && middle && ring && !pinky && !thumb) return 'number_three'
  if (index && middle && !ring && !pinky && !thumb) return 'number_two'
  if (index && !middle && !ring && !pinky && !thumb) return 'number_one'

  return null
}

export function matchGesture(
  target: Gesture,
  lm: Landmark[] | undefined,
): {
  matchPct: number
  detected: Gesture | null
  label: string
  handPresent: boolean
} {
  if (!lm || lm.length < 21) {
    return { matchPct: 0, detected: null, label: 'No hand detected', handPresent: false }
  }

  if (ARM_EXERCISE_IDS.includes(target)) {
    return {
      matchPct: 55,
      detected: null,
      label: 'Hand visible — follow arm motion (pose not scored from camera)',
      handPresent: true,
    }
  }

  const f = fingerStates(lm)
  const detected = classifyGestureFromLandmarks(lm)

  if (detected === target) {
    return {
      matchPct: 98,
      detected,
      label: 'Match',
      handPresent: true,
    }
  }

  const ideal = TARGET_BITS[target]
  if (ideal) {
    const base = bitsSimilarity(f, ideal) * 100
    const pinchBoost =
      target === 'pinch' || target === 'ok_sign' || target === 'tripod_grasp'
        ? Math.max(0, 1 - f.pinchDist / 0.35) * 25
        : 0
    const pct = Math.min(99, Math.round(base * 0.85 + pinchBoost))
    return {
      matchPct: pct,
      detected,
      label: detected ? `Seen: ${detected.replace(/_/g, ' ')}` : 'Adjust fingers',
      handPresent: true,
    }
  }

  return {
    matchPct: detected === target ? 90 : 40,
    detected,
    label: detected ? `Seen: ${detected.replace(/_/g, ' ')}` : 'Hold the pose',
    handPresent: true,
  }
}

/** MediaPipe hand skeleton edges for canvas overlay */
export const HAND_EDGES: [number, number][] = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [0, 9], [9, 10], [10, 11], [11, 12],
  [0, 13], [13, 14], [14, 15], [15, 16],
  [0, 17], [17, 18], [18, 19], [19, 20],
  [5, 9], [9, 13], [13, 17],
]
