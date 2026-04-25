/**
 * Maps brain scan / MRI-derived signals to distinct rehab pose sequences.
 * Each plan draws from a larger candidate pool and picks a per-scan subset so
 * two scans of the same stroke type still yield visibly different sessions.
 */
import type { Gesture } from '../config/gestures'

export type ScanPlanId =
  | 'hemorrhagic_grasp'
  | 'ischemic_motor'
  | 'normal_mobility'
  | 'uncertain_gentle'
  | 'rejected_screening'
  | 'region_motor_frontal'
  | 'region_parietal_sensory'
  | 'region_occipital'
  | 'region_deep'
  | 'legacy_stroke_fallback'

export type ScanExercisePlan = {
  planId: ScanPlanId
  /** Short label for judges / UI */
  label: string
  /** One-line description */
  description: string
  exercises: Gesture[]
}

/** Raw scan payload (subset of what /api/scan/upload returns). */
export interface ScanSignals {
  scanId?: string
  strokeType?: string
  classification?: string
  predictedClass?: string
  brainRegion?: string
  affectedSide?: string
  avgSeverity?: number
  lesionCoveragePct?: number
  zonesAffected?: number
  affectedZoneNames?: string[]
  confidence?: number
}

type PlanTemplate = {
  label: string
  description: string
  /** Candidate pool — the concrete session picks a subset. Order matters: earlier = higher priority. */
  pool: Gesture[]
  /** Ideal number of poses per session (capped by pool length). */
  target: number
  /** Gestures that MUST appear in every session for this plan (the "signature" poses). */
  anchors?: Gesture[]
}

function norm(s: string) {
  return s.toLowerCase().trim()
}

const PLANS: Record<ScanPlanId, PlanTemplate> = {
  hemorrhagic_grasp: {
    label: 'Hemorrhagic stroke — control & grasp',
    description: 'Low-load grasps, stability, shoulder control (avoid wide extension early).',
    anchors: ['fist', 'half_fist'],
    pool: [
      'fist', 'half_fist', 'tripod_grasp', 'lateral_pinch', 'claw',
      'relaxed_spread', 'flat_hand', 'ok_sign',
      'arm_raise', 'shoulder_abduct', 'elbow_flex',
    ],
    target: 6,
  },
  ischemic_motor: {
    label: 'Ischemic stroke — fine motor & extension',
    description: 'Fine pinch, pointing, wrist — typical MCA territory rehab emphasis.',
    anchors: ['pinch', 'point'],
    pool: [
      'point', 'pinch', 'pinch_wide', 'thumb_out', 'open_hand',
      'number_three', 'number_two', 'index_only', 'peace_sign', 'ok_sign',
      'elbow_flex', 'wrist_circle',
    ],
    target: 6,
  },
  normal_mobility: {
    label: 'No acute stroke pattern — maintenance',
    description: 'Light mobility & dexterity; no stroke-specific loading.',
    pool: [
      'peace_sign', 'thumbs_up', 'shaka', 'rock_on', 'spread_wide',
      'open_hand', 'number_five', 'stop_hand',
    ],
    target: 5,
  },
  uncertain_gentle: {
    label: 'Uncertain scan — gentle range',
    description: 'Safe, low-complexity poses until imaging is clearer.',
    pool: [
      'open_hand', 'relaxed_spread', 'fist', 'point', 'flat_hand', 'thumb_out', 'half_fist',
    ],
    target: 5,
  },
  rejected_screening: {
    label: 'Non-brain scan image — screening only',
    description: 'Generic hand screening; upload a brain MRI for a tailored list.',
    pool: ['open_hand', 'fist', 'point', 'stop_hand'],
    target: 4,
  },
  region_motor_frontal: {
    label: 'Motor region emphasis — reach & pinch',
    description: 'Frontal / motor cortical involvement — combine reach with fine motor.',
    anchors: ['arm_raise'],
    pool: [
      'open_hand', 'fist', 'point', 'pinch', 'tripod_grasp',
      'arm_raise', 'elbow_flex', 'shoulder_abduct', 'number_three',
    ],
    target: 6,
  },
  region_parietal_sensory: {
    label: 'Sensory / parietal emphasis — tactile grasps',
    description: 'Pinch variants and tactile discrimination style tasks.',
    anchors: ['lateral_pinch'],
    pool: [
      'thumb_out', 'pinch', 'tripod_grasp', 'lateral_pinch', 'pinch_wide',
      'ok_sign', 'point', 'index_only',
    ],
    target: 6,
  },
  region_occipital: {
    label: 'Visual / occipital guidance — pointing & fixation',
    description: 'Visually guided finger targets (no heavy load).',
    anchors: ['point'],
    pool: [
      'point', 'thumb_out', 'peace_sign', 'ok_sign',
      'number_one', 'number_two', 'number_three', 'index_only',
    ],
    target: 5,
  },
  region_deep: {
    label: 'Deep territory — compact control',
    description: 'Smaller amplitude hand movements; proximal shoulder control.',
    anchors: ['half_fist'],
    pool: [
      'fist', 'half_fist', 'tripod_grasp', 'claw', 'relaxed_spread',
      'arm_raise', 'shoulder_abduct', 'wrist_circle',
    ],
    target: 6,
  },
  legacy_stroke_fallback: {
    label: 'Stroke analysis — mixed hand plan',
    description: 'Fallback when only legacy stroke_type text is available.',
    pool: [
      'open_hand', 'fist', 'point', 'pinch', 'flat_hand',
      'arm_raise', 'elbow_flex', 'thumb_out',
    ],
    target: 5,
  },
}

/** djb2 string hash → 32-bit unsigned int. Stable, tiny, no deps. */
function hashSeed(input: string): number {
  let h = 5381
  for (let i = 0; i < input.length; i++) h = (h * 33) ^ input.charCodeAt(i)
  return h >>> 0
}

/** mulberry32 PRNG — deterministic sequence from a seed. */
function mulberry32(seed: number) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function deterministicShuffle<T>(arr: T[], rand: () => number): T[] {
  const out = arr.slice()
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1))
    ;[out[i], out[j]] = [out[j], out[i]]
  }
  return out
}

function uniqGestures(g: Gesture[]): Gesture[] {
  const seen = new Set<string>()
  const out: Gesture[] = []
  for (const id of g) {
    if (!seen.has(id)) {
      seen.add(id)
      out.push(id)
    }
  }
  return out
}

function buildSeedKey(planId: ScanPlanId, sig: ScanSignals): string {
  // Anything that meaningfully varies between scans contributes to the seed.
  const parts: string[] = [
    planId,
    sig.scanId ?? '',
    sig.classification ?? '',
    sig.predictedClass ?? '',
    sig.brainRegion ?? '',
    sig.affectedSide ?? '',
    sig.avgSeverity != null ? sig.avgSeverity.toFixed(2) : '',
    sig.lesionCoveragePct != null ? sig.lesionCoveragePct.toFixed(1) : '',
    sig.zonesAffected != null ? String(sig.zonesAffected) : '',
    ...(sig.affectedZoneNames ?? []),
  ]
  return parts.join('|')
}

function pickPlanId(sig: ScanSignals): ScanPlanId {
  const st = norm(sig.strokeType ?? '')
  const cls = norm(sig.classification ?? '') || norm(sig.predictedClass ?? '')
  const pred = norm(sig.predictedClass ?? '')
  const reg = norm(sig.brainRegion ?? '')
  const combined = `${cls} ${pred} ${st} ${reg}`

  if (combined.includes('reject')) return 'rejected_screening'
  if (cls.includes('hemorrhagic') || pred.includes('hemorrhagic')) return 'hemorrhagic_grasp'
  if (cls.includes('ischemic') || pred.includes('ischemic')) return 'ischemic_motor'
  if (cls.includes('normal') || cls.includes('no stroke') || pred.includes('normal') || combined.includes('non_stroke')) {
    return 'normal_mobility'
  }
  if (cls.includes('uncertain') || pred.includes('uncertain')) return 'uncertain_gentle'

  if (reg.includes('occipital') || reg.includes('visual')) return 'region_occipital'
  if (reg.includes('parietal') || reg.includes('sensory') || reg.includes('somatosensory')) return 'region_parietal_sensory'
  if (reg.includes('deep') || reg.includes('basal') || reg.includes('ganglia') || reg.includes('putamen')) return 'region_deep'
  if (reg.includes('motor') || reg.includes('frontal') || reg.includes('m1')) return 'region_motor_frontal'

  if (st.includes('hemorrhagic')) return 'hemorrhagic_grasp'
  if (st.includes('ischemic')) return 'ischemic_motor'
  if (st.includes('normal')) return 'normal_mobility'

  return 'legacy_stroke_fallback'
}

/** Size the session by severity / coverage so a bad scan gets more reps. */
function scaleTarget(base: number, sig: ScanSignals, poolLen: number): number {
  let t = base
  if (sig.avgSeverity != null && sig.avgSeverity >= 0.7) t += 1
  if (sig.lesionCoveragePct != null && sig.lesionCoveragePct >= 15) t += 1
  if (sig.zonesAffected != null && sig.zonesAffected >= 4) t += 1
  return Math.min(Math.max(t, 3), poolLen)
}

export function getExercisePlanFromScanSignals(sig: ScanSignals): ScanExercisePlan {
  const planId = pickPlanId(sig)
  const tmpl = PLANS[planId]
  const rand = mulberry32(hashSeed(buildSeedKey(planId, sig)))

  const target = scaleTarget(tmpl.target, sig, tmpl.pool.length)
  const anchors = uniqGestures(tmpl.anchors ?? [])
  const rest = tmpl.pool.filter(g => !anchors.includes(g))
  const shuffledRest = deterministicShuffle(rest, rand)
  const picked = uniqGestures([...anchors, ...shuffledRest]).slice(0, target)

  return {
    planId,
    label: tmpl.label,
    description: tmpl.description,
    exercises: picked,
  }
}

/**
 * Legacy signature — still used by older call sites.
 * Prefer `getExercisePlanFromScanSignals` which varies the concrete list per scan.
 */
export function getExercisePlanFromScan(
  strokeType: string,
  opts?: { classification?: string; brainRegion?: string; predictedClass?: string },
): ScanExercisePlan {
  return getExercisePlanFromScanSignals({
    strokeType,
    classification: opts?.classification,
    predictedClass: opts?.predictedClass,
    brainRegion: opts?.brainRegion,
  })
}
