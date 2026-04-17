/**
 * Maps brain scan / MRI-derived signals to distinct rehab pose sequences.
 * Each plan uses a different gesture mix so demos (different scans) look clearly different.
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

function norm(s: string) {
  return s.toLowerCase().trim()
}

const PLANS: Record<ScanPlanId, Omit<ScanExercisePlan, 'planId'>> = {
  hemorrhagic_grasp: {
    label: 'Hemorrhagic stroke — control & grasp',
    description: 'Low-load grasps, stability, shoulder control (avoid wide extension early).',
    exercises: [
      'fist',
      'half_fist',
      'tripod_grasp',
      'lateral_pinch',
      'claw',
      'relaxed_spread',
      'arm_raise',
      'shoulder_abduct',
    ],
  },
  ischemic_motor: {
    label: 'Ischemic stroke — fine motor & extension',
    description: 'Fine pinch, pointing, wrist — typical MCA territory rehab emphasis.',
    exercises: [
      'point',
      'pinch',
      'pinch_wide',
      'thumb_out',
      'open_hand',
      'number_three',
      'elbow_flex',
      'wrist_circle',
    ],
  },
  normal_mobility: {
    label: 'No acute stroke pattern — maintenance',
    description: 'Light mobility & dexterity; no stroke-specific loading.',
    exercises: ['peace_sign', 'thumbs_up', 'shaka', 'rock_on', 'spread_wide', 'open_hand'],
  },
  uncertain_gentle: {
    label: 'Uncertain scan — gentle range',
    description: 'Safe, low-complexity poses until imaging is clearer.',
    exercises: ['open_hand', 'relaxed_spread', 'fist', 'point', 'flat_hand', 'thumb_out'],
  },
  rejected_screening: {
    label: 'Non-brain scan image — screening only',
    description: 'Generic hand screening; upload a brain MRI for a tailored list.',
    exercises: ['open_hand', 'fist', 'point', 'stop_hand'],
  },
  region_motor_frontal: {
    label: 'Motor region emphasis — reach & pinch',
    description: 'Frontal / motor cortical involvement — combine reach with fine motor.',
    exercises: ['open_hand', 'fist', 'point', 'pinch', 'tripod_grasp', 'arm_raise', 'elbow_flex'],
  },
  region_parietal_sensory: {
    label: 'Sensory / parietal emphasis — tactile grasps',
    description: 'Pinch variants and tactile discrimination style tasks.',
    exercises: ['thumb_out', 'pinch', 'tripod_grasp', 'lateral_pinch', 'pinch_wide', 'ok_sign', 'point'],
  },
  region_occipital: {
    label: 'Visual / occipital guidance — pointing & fixation',
    description: 'Visually guided finger targets (no heavy load).',
    exercises: ['point', 'thumb_out', 'peace_sign', 'ok_sign', 'number_one', 'number_two'],
  },
  region_deep: {
    label: 'Deep territory — compact control',
    description: 'Smaller amplitude hand movements; proximal shoulder control.',
    exercises: ['fist', 'half_fist', 'tripod_grasp', 'claw', 'arm_raise', 'shoulder_abduct', 'wrist_circle'],
  },
  legacy_stroke_fallback: {
    label: 'Stroke analysis — mixed hand plan',
    description: 'Fallback when only legacy stroke_type text is available.',
    exercises: ['open_hand', 'fist', 'point', 'pinch', 'flat_hand', 'arm_raise', 'elbow_flex'],
  },
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

function withPlan(planId: ScanPlanId): ScanExercisePlan {
  const p = PLANS[planId]
  return {
    planId,
    label: p.label,
    description: p.description,
    exercises: uniqGestures(p.exercises),
  }
}

/**
 * Resolve MRI scan fields → distinct exercise plan.
 * Priority: classification API → predicted_class string → brain region → stroke_type.
 */
export function getExercisePlanFromScan(
  strokeType: string,
  opts?: { classification?: string; brainRegion?: string; predictedClass?: string },
): ScanExercisePlan {
  const st = norm(strokeType)
  const clsRaw = norm(opts?.classification ?? '')
  const predRaw = norm(opts?.predictedClass ?? '')
  /** Prefer compact API label; fall back to full legacy string e.g. "Hemorrhagic Stroke" */
  const cls = clsRaw || predRaw
  const reg = norm(opts?.brainRegion ?? '')

  const combined = `${clsRaw} ${predRaw} ${st} ${reg}`

  if (combined.includes('rejected') || combined.includes('reject')) {
    return withPlan('rejected_screening')
  }
  if (cls.includes('hemorrhagic') || predRaw.includes('hemorrhagic')) {
    return withPlan('hemorrhagic_grasp')
  }
  if (cls.includes('ischemic') || predRaw.includes('ischemic')) {
    return withPlan('ischemic_motor')
  }
  if (
    cls.includes('normal')
    || cls.includes('no stroke')
    || predRaw.includes('normal')
    || combined.includes('non_stroke')
  ) {
    return withPlan('normal_mobility')
  }
  if (cls.includes('uncertain') || predRaw.includes('uncertain')) {
    return withPlan('uncertain_gentle')
  }

  if (reg.includes('occipital') || reg.includes('visual')) {
    return withPlan('region_occipital')
  }
  if (reg.includes('parietal') || reg.includes('sensory') || reg.includes('somatosensory')) {
    return withPlan('region_parietal_sensory')
  }
  if (reg.includes('deep') || reg.includes('basal') || reg.includes('ganglia') || reg.includes('putamen')) {
    return withPlan('region_deep')
  }
  if (reg.includes('motor') || reg.includes('frontal') || reg.includes('m1')) {
    return withPlan('region_motor_frontal')
  }

  if (st.includes('hemorrhagic') || predRaw.includes('hemorrhagic')) {
    return withPlan('hemorrhagic_grasp')
  }
  if (st.includes('ischemic') || predRaw.includes('ischemic')) {
    return withPlan('ischemic_motor')
  }
  if (st.includes('normal') || predRaw.includes('normal')) {
    return withPlan('normal_mobility')
  }

  return withPlan('legacy_stroke_fallback')
}
