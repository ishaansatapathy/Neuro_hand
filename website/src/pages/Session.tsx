import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Hand, Play, Square, Volume2, ArrowRight, RotateCcw, Trophy, Clock, Target, Zap, Brain, ChevronLeft, ChevronRight, Camera, Loader2 } from 'lucide-react'
import { startSession, endSession, voiceUrl, getLatestScanAnalysis } from '../lib/api'
import { hasCompletedScan, loadScanSnapshot, canOpenSession, disarmSession } from '../lib/sessionGate'
import {
  GESTURE_LIST,
  GESTURE_MESSAGES,
  VOICE_KEYS,
  SKELETON_TEMPLATE,
  ARM_EXERCISE_IDS,
  type Gesture,
} from '../config/gestures'
import type { StrokeAnalysis } from '../lib/brainRules'
import {
  getExercisePlanFromScan,
  getExercisePlanFromScanSignals,
  type ScanExercisePlan,
  type ScanSignals,
} from '../lib/scanExercisePlan'
import { useHandPoseVerification } from '../hooks/useHandPoseVerification'

type SessionPhase = 'checking' | 'needs_scan' | 'analyzing' | 'setup' | 'start_analyzing' | 'active' | 'complete'
type Difficulty = 'easy' | 'medium' | 'hard'

interface SessionResult {
  total_score: number
  duration: number
  avg_match: number
}

const DURATIONS = [3, 5, 10]

const INTERVAL_MS: Record<Difficulty, number> = {
  easy: 8000,
  medium: 5000,
  hard: 3000,
}

// SVG templates (3 primitives) — all 25 gestures map via SKELETON_TEMPLATE
const HAND_POSES: Record<'open_hand' | 'fist' | 'point', { fingers: [number, number][][]; wrist: [number, number]; palm: [number, number] }> = {
  open_hand: {
    wrist: [150, 280],
    palm: [150, 210],
    fingers: [
      [[110, 190], [90, 140], [80, 95]],   // thumb
      [[120, 175], [110, 115], [105, 70]],  // index
      [[145, 170], [142, 105], [140, 55]],  // middle
      [[170, 175], [175, 115], [178, 70]],  // ring
      [[192, 190], [205, 140], [215, 100]], // pinky
    ],
  },
  fist: {
    wrist: [150, 280],
    palm: [150, 210],
    fingers: [
      [[110, 190], [100, 175], [120, 190]], // thumb curled
      [[120, 175], [115, 170], [125, 185]], // index curled
      [[145, 170], [142, 165], [148, 180]], // middle curled
      [[170, 175], [172, 168], [168, 182]], // ring curled
      [[192, 190], [195, 182], [190, 195]], // pinky curled
    ],
  },
  point: {
    wrist: [150, 280],
    palm: [150, 210],
    fingers: [
      [[110, 190], [100, 175], [120, 190]], // thumb curled
      [[120, 175], [110, 115], [105, 70]],  // index extended
      [[145, 170], [142, 165], [148, 180]], // middle curled
      [[170, 175], [172, 168], [168, 182]], // ring curled
      [[192, 190], [195, 182], [190, 195]], // pinky curled
    ],
  },
}

function ArmSkeleton({ gesture }: { gesture: Gesture }) {
  const label = GESTURE_MESSAGES[gesture]
  return (
    <svg viewBox="0 0 300 320" className="w-full h-full max-w-70 max-h-70">
      <defs>
        <filter id="armGlow">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>
      {/* Shoulder */}
      <circle cx="150" cy="60" r="14" fill="#60a5fa" opacity={0.5} filter="url(#armGlow)" />
      {/* Upper arm */}
      <line x1="150" y1="74" x2="150" y2="170" stroke="#60a5fa" strokeWidth="10" strokeLinecap="round" filter="url(#armGlow)" />
      {/* Elbow */}
      <circle cx="150" cy="170" r="10" fill="#a78bfa" opacity={0.8} filter="url(#armGlow)" />
      {/* Forearm */}
      <line x1="150" y1="180" x2="150" y2="265" stroke="#a78bfa" strokeWidth="8" strokeLinecap="round" filter="url(#armGlow)" />
      {/* Wrist */}
      <circle cx="150" cy="265" r="8" fill="#f472b6" opacity={0.8} filter="url(#armGlow)" />
      {/* Direction hint */}
      {gesture === 'arm_raise' && (
        <g>
          <line x1="150" y1="48" x2="150" y2="20" stroke="#f472b6" strokeWidth="3" strokeDasharray="4 3" />
          <polygon points="150,12 143,24 157,24" fill="#f472b6" />
        </g>
      )}
      {gesture === 'elbow_flex' && (
        <line x1="150" y1="180" x2="100" y2="220" stroke="#f472b6" strokeWidth="8" strokeLinecap="round" filter="url(#armGlow)" />
      )}
      {gesture === 'shoulder_abduct' && (
        <g>
          <line x1="150" y1="74" x2="230" y2="130" stroke="#60a5fa" strokeWidth="10" strokeLinecap="round" filter="url(#armGlow)" />
          <polygon points="240,124 222,122 232,138" fill="#f472b6" />
        </g>
      )}
      {gesture === 'wrist_circle' && (
        <ellipse cx="150" cy="265" rx="22" ry="14" fill="none" stroke="#f472b6" strokeWidth="2.5" strokeDasharray="5 3" />
      )}
      <text x="150" y="300" textAnchor="middle" fill="rgba(255,255,255,0.45)" fontSize="11" fontFamily="sans-serif">{label}</text>
    </svg>
  )
}

function SkeletonHand({ template }: { template: 'open_hand' | 'fist' | 'point' }) {
  const pose = HAND_POSES[template]

  return (
    <svg viewBox="0 0 300 320" className="w-full h-full max-w-[280px] max-h-[280px]">
      {/* Glow filter */}
      <defs>
        <filter id="glow">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Wrist to palm */}
      <line
        x1={pose.wrist[0]} y1={pose.wrist[1]}
        x2={pose.palm[0]} y2={pose.palm[1]}
        stroke="#60a5fa" strokeWidth="3" strokeLinecap="round"
        className="transition-all duration-700 ease-in-out"
        filter="url(#glow)"
      />

      {/* Fingers: bones and joints */}
      {pose.fingers.map((joints: [number, number][], fi: number) => (
        <g key={fi}>
          {/* Bone from palm to base */}
          <line
            x1={pose.palm[0]} y1={pose.palm[1]}
            x2={joints[0][0]} y2={joints[0][1]}
            stroke="#60a5fa" strokeWidth="2.5" strokeLinecap="round"
            className="transition-all duration-700 ease-in-out"
            filter="url(#glow)"
          />
          {/* Bones between joints */}
          {joints.slice(0, -1).map((j: [number, number], ji: number) => (
            <line
              key={ji}
              x1={j[0]} y1={j[1]}
              x2={joints[ji + 1][0]} y2={joints[ji + 1][1]}
              stroke="#a78bfa" strokeWidth="2" strokeLinecap="round"
              className="transition-all duration-700 ease-in-out"
              filter="url(#glow)"
            />
          ))}
          {/* Joints */}
          {joints.map((j: [number, number], ji: number) => (
            <circle
              key={ji}
              cx={j[0]} cy={j[1]} r={ji === 2 ? 4 : 5}
              fill={ji === 2 ? '#f472b6' : '#a78bfa'}
              className="transition-all duration-700 ease-in-out"
              filter="url(#glow)"
            />
          ))}
        </g>
      ))}

      {/* Palm joint */}
      <circle
        cx={pose.palm[0]} cy={pose.palm[1]} r={8}
        fill="#60a5fa" opacity={0.6}
        className="transition-all duration-700 ease-in-out"
      />

      {/* Wrist joint */}
      <circle
        cx={pose.wrist[0]} cy={pose.wrist[1]} r={6}
        fill="#60a5fa" opacity={0.4}
        className="transition-all duration-700 ease-in-out"
      />
    </svg>
  )
}

function CircularTimer({ remaining, total }: { remaining: number; total: number }) {
  const radius = 54
  const circumference = 2 * Math.PI * radius
  const progress = total > 0 ? remaining / total : 1
  const offset = circumference * (1 - progress)
  const minutes = Math.floor(remaining / 60)
  const seconds = remaining % 60

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width="140" height="140" className="-rotate-90">
        <circle cx="70" cy="70" r={radius} fill="none" stroke="#1e293b" strokeWidth="8" />
        <circle
          cx="70" cy="70" r={radius}
          fill="none" stroke="url(#timerGrad)" strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-1000 linear"
        />
        <defs>
          <linearGradient id="timerGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#60a5fa" />
            <stop offset="100%" stopColor="#a78bfa" />
          </linearGradient>
        </defs>
      </svg>
      <span className="absolute text-2xl font-bold text-foreground tabular-nums">
        {minutes}:{seconds.toString().padStart(2, '0')}
      </span>
    </div>
  )
}

export default function Session() {
  const navigate = useNavigate()
  const [sessionPhase, setSessionPhase] = useState<SessionPhase>('checking')
  const [showExercisePicker, setShowExercisePicker] = useState(false)
  /** gesture_id -> filename under /poses/ (from public/poses/manifest.json) */
  const [poseManifest, setPoseManifest] = useState<Record<string, string>>({})
  const [possesImages, setPossesImages] = useState<string[]>([])
  const [possesIndex, setPossesIndex] = useState(0)
  const [scanAnalysis, setScanAnalysis] = useState<StrokeAnalysis | null>(null)
  const [scanPlan, setScanPlan] = useState<ScanExercisePlan | null>(null)

  // Setup
  const [hand, setHand] = useState<'left' | 'right'>('right')
  // Start empty — the scan resolver populates this once it returns.
  // (Previously hardcoded to ['open_hand','fist','point'], which is why every
  // session looked identical when the API was slow or stale.)
  const [exercises, setExercises] = useState<Gesture[]>([])
  const [planLoaded, setPlanLoaded] = useState(false)
  const [userEditedExercises, setUserEditedExercises] = useState(false)
  const [difficulty, setDifficulty] = useState<Difficulty>('medium')
  const [duration, setDuration] = useState(5)
  const [loading, setLoading] = useState(false)

  // Active
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [timeLeft, setTimeLeft] = useState(0)
  const [totalTime, setTotalTime] = useState(0)
  const [score, setScore] = useState(0)
  const [currentGesture, setCurrentGesture] = useState<Gesture>('open_hand')
  const [message, setMessage] = useState('')
  const [, setGestureIndex] = useState(0)

  // Complete
  const [result, setResult] = useState<SessionResult | null>(null)

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const gestureTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const scoreCheckRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)

  const sessionSnapshotRef = useRef({
    sessionId: null as string | null,
    score: 0,
    timeLeft: 0,
    totalTime: 0,
    difficulty: 'medium' as Difficulty,
  })
  useEffect(() => {
    sessionSnapshotRef.current = { sessionId, score, timeLeft, totalTime, difficulty }
  }, [sessionId, score, timeLeft, totalTime, difficulty])

  // Canvas already has CSS `-scale-x-100`, so pass mirrored={false} to avoid
  // double-flipping the landmark coords (previously drew skeleton on the wrong side).
  const poseVerify = useHandPoseVerification(
    videoRef,
    canvasRef,
    currentGesture,
    sessionPhase === 'active',
    false,
  )
  const poseMatchRef = useRef(0)
  useEffect(() => {
    poseMatchRef.current = poseVerify.matchPct
  }, [poseVerify.matchPct])

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
      if (gestureTimerRef.current) clearInterval(gestureTimerRef.current)
      if (scoreCheckRef.current) clearTimeout(scoreCheckRef.current)
      if (audioRef.current) audioRef.current.pause()
      if (typeof window !== 'undefined' && window.speechSynthesis) {
        window.speechSynthesis.cancel()
      }
    }
  }, [])

  useEffect(() => {
    fetch('/poses/manifest.json')
      .then(r => (r.ok ? r.json() : {}))
      .then((data: unknown) => {
        if (data && typeof data === 'object' && !Array.isArray(data)) {
          setPoseManifest(data as Record<string, string>)
        }
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    // Strict gate: session opens ONLY when user has scanned AND explicitly
    // clicked "Start Rehab Session" on the results page. Direct URL, navbar
    // click, or returning after a tab reopen all show the "scan first" screen.
    if (!canOpenSession()) {
      setSessionPhase('needs_scan')
      return
    }
    const toAnalyzing = window.setTimeout(() => setSessionPhase('analyzing'), 0)
    const toSetup = window.setTimeout(() => setSessionPhase('setup'), 2600)
    return () => {
      window.clearTimeout(toAnalyzing)
      window.clearTimeout(toSetup)
    }
  }, [])

  useEffect(() => {
    if (!hasCompletedScan()) return // gated screen handles this case

    const snap = loadScanSnapshot()

    const applyFromSignals = (sig: ScanSignals) => {
      const plan = getExercisePlanFromScanSignals(sig)
      setScanPlan(plan)
      // Only replace exercises if the user hasn't started curating them.
      if (plan.exercises.length) {
        setExercises(prev => (userEditedExercises && prev.length ? prev : plan.exercises))
      }
      setPlanLoaded(true)
    }

    getLatestScanAnalysis()
      .then(data => {
        const sa = data.stroke_analysis ?? {}
        const metrics = sa.scan_metrics ?? {}
        const zones = Array.isArray(sa.affected_zones) ? sa.affected_zones : []

        const sig: ScanSignals = {
          scanId: data.scan_id ?? snap?.ts?.toString(),
          strokeType: sa.stroke_type ?? snap?.stroke_type ?? '',
          classification: (data.classification?.prediction as string | undefined) ?? '',
          predictedClass: String(data.predicted_class ?? snap?.predicted_class ?? '').trim(),
          brainRegion: (data.brain_region?.region as string | undefined) ?? snap?.brain_region ?? '',
          affectedSide: metrics.affected_side,
          avgSeverity: typeof metrics.avg_severity === 'number' ? metrics.avg_severity : undefined,
          lesionCoveragePct: typeof metrics.lesion_coverage_pct === 'number' ? metrics.lesion_coverage_pct : undefined,
          zonesAffected: typeof metrics.zones_affected === 'number' ? metrics.zones_affected : zones.length || undefined,
          affectedZoneNames: zones.map((z: { zone?: string }) => z?.zone ?? '').filter(Boolean),
          confidence: typeof data.confidence === 'number' ? data.confidence : snap?.confidence,
        }
        applyFromSignals(sig)

        if (data.has_scan && data.stroke_analysis) {
          setScanAnalysis(data.stroke_analysis)
          // Auto-suggest affected hand from the scan (opposite hemisphere rules).
          const side = String(metrics.affected_side ?? '').toLowerCase()
          if (side === 'left') setHand('right')
          else if (side === 'right') setHand('left')
        }
      })
      .catch(() => {
        if (snap) {
          applyFromSignals({
            scanId: snap.ts?.toString(),
            strokeType: snap.stroke_type ?? '',
            classification: snap.classification_prediction ?? '',
            predictedClass: snap.predicted_class ?? '',
            brainRegion: snap.brain_region,
            confidence: snap.confidence,
          })
        } else {
          // No scan + no snapshot → fall back to the legacy resolver's default
          // so the user isn't stuck with zero exercises.
          const plan = getExercisePlanFromScan('', {})
          setScanPlan(plan)
          setExercises(plan.exercises)
          setPlanLoaded(true)
        }
      })
    // `userEditedExercises` is intentionally not in deps: we only want the
    // plan fetched once per mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (sessionPhase !== 'active') {
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach(tr => tr.stop())
        mediaStreamRef.current = null
      }
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
          audio: false,
        })
        if (cancelled) {
          stream.getTracks().forEach(tr => tr.stop())
          return
        }
        mediaStreamRef.current = stream
        const el = videoRef.current
        if (el) {
          el.srcObject = stream
          el.play().catch(() => {})
        }
      } catch {
        /* camera unavailable */
      }
    })()
    return () => {
      cancelled = true
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach(tr => tr.stop())
        mediaStreamRef.current = null
      }
    }
  }, [sessionPhase])

  useEffect(() => {
    fetch('/api/posses')
      .then(r => (r.ok ? r.json() : { images: [] }))
      .then((d: { images: string[] }) => setPossesImages(d.images ?? []))
      .catch(() => {})
  }, [])

  const toggleExercise = (ex: Gesture) => {
    setUserEditedExercises(true)
    setExercises(prev =>
      prev.includes(ex) ? prev.filter(e => e !== ex) : [...prev, ex]
    )
  }

  const playVoice = useCallback((gesture: Gesture) => {
    const message = GESTURE_MESSAGES[gesture]

    // Prefer browser TTS — speaks the *exact* message per gesture.
    // Server-cached clips only cover 3 of 25 gestures so they'd lie about the pose.
    const synth = typeof window !== 'undefined' ? window.speechSynthesis : null
    if (synth) {
      try {
        synth.cancel()
        const u = new SpeechSynthesisUtterance(message)
        u.rate = 1
        u.pitch = 1.05
        u.volume = 1
        synth.speak(u)
        return
      } catch {
        // fall through to audio fallback
      }
    }

    try {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current.currentTime = 0
      }
      const audio = new Audio(voiceUrl(VOICE_KEYS[gesture]))
      audioRef.current = audio
      audio.play().catch(() => {})
    } catch {
      // audio not available
    }
  }, [])

  // Hold-time scoring: user gets +1 when they sustain ≥72% match for
  // HOLD_REQUIRED_MS cumulative during the gesture window. Much more forgiving
  // than a single-moment snapshot — and the progress bar gives live feedback.
  const HOLD_REQUIRED_MS = 800
  const MATCH_THRESHOLD = 72
  const holdMsRef = useRef(0)
  const gestureScoredRef = useRef(false)
  const [holdProgress, setHoldProgress] = useState(0)

  const scheduleScoreCheck = useCallback((delayMs = 2800) => {
    if (scoreCheckRef.current) clearTimeout(scoreCheckRef.current)
    holdMsRef.current = 0
    gestureScoredRef.current = false
    setHoldProgress(0)

    const lastTickRef = { t: performance.now() }
    const tick = () => {
      const now = performance.now()
      const dt = now - lastTickRef.t
      lastTickRef.t = now

      if (poseMatchRef.current >= MATCH_THRESHOLD) {
        holdMsRef.current = Math.min(HOLD_REQUIRED_MS, holdMsRef.current + dt)
      } else {
        // Decay so a flash doesn't carry the whole window
        holdMsRef.current = Math.max(0, holdMsRef.current - dt * 0.5)
      }
      setHoldProgress(holdMsRef.current / HOLD_REQUIRED_MS)

      if (holdMsRef.current >= HOLD_REQUIRED_MS && !gestureScoredRef.current) {
        gestureScoredRef.current = true
        setScore(s => s + 1)
        setMessage('Great! +1 — pose held ✓')
      }
    }

    const interval = setInterval(tick, 80)
    scoreCheckRef.current = setTimeout(() => {
      clearInterval(interval)
      scoreCheckRef.current = null
      if (!gestureScoredRef.current) {
        setMessage(
          poseMatchRef.current >= MATCH_THRESHOLD
            ? 'Close! Hold the pose a bit longer'
            : 'Match the target pose in frame'
        )
      }
    }, delayMs)
  }, [])

  const cycleGesture = useCallback(() => {
    if (exercises.length === 0) return
    setGestureIndex(prev => {
      const next = (prev + 1) % exercises.length
      const nextGesture = exercises[next]
      setCurrentGesture(nextGesture)
      setMessage(GESTURE_MESSAGES[nextGesture])
      playVoice(nextGesture)
      scheduleScoreCheck()
      return next
    })
  }, [exercises, playVoice, scheduleScoreCheck])

  const handleStart = async () => {
    if (exercises.length === 0) return
    setSessionPhase('start_analyzing')
    await new Promise(r => setTimeout(r, 1600))
    setLoading(true)
    try {
      const res = await startSession({
        affected_hand: hand,
        exercises,
        difficulty,
        duration_minutes: duration,
      })
      setSessionId(res.session_id || res.id || 'local')
    } catch {
      setSessionId('local')
    }

    const totalSec = duration * 60
    setTimeLeft(totalSec)
    setTotalTime(totalSec)
    setScore(0)
    setGestureIndex(0)

    // Show the first target immediately, but DON'T speak or score until the
    // pose tracker finishes loading (see `firstGesturePrimed` effect below).
    const firstGesture = exercises[0]
    setCurrentGesture(firstGesture)
    setMessage('Get ready…')

    setSessionPhase('active')
    setLoading(false)
  }

  // Cue the first gesture (voice + score check) only once the pose tracker
  // is actually ready. This is what was causing "voice plays while camera
  // still shows Loading…" on slow first loads.
  const firstGesturePrimed = useRef(false)
  useEffect(() => {
    if (sessionPhase !== 'active') {
      firstGesturePrimed.current = false
      return
    }
    if (firstGesturePrimed.current) return
    if (!poseVerify.ready) return
    firstGesturePrimed.current = true
    setMessage(GESTURE_MESSAGES[currentGesture])
    playVoice(currentGesture)
    scheduleScoreCheck()
  }, [sessionPhase, poseVerify.ready, currentGesture, playVoice, scheduleScoreCheck])

  const handleEnd = useCallback(async () => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    if (gestureTimerRef.current) {
      clearInterval(gestureTimerRef.current)
      gestureTimerRef.current = null
    }
    if (scoreCheckRef.current) {
      clearTimeout(scoreCheckRef.current)
      scoreCheckRef.current = null
    }
    if (audioRef.current) audioRef.current.pause()
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel()
    }

    const { sessionId: sid, score: sc, timeLeft: tl, totalTime: tt, difficulty: diff } =
      sessionSnapshotRef.current

    try {
      if (sid && sid !== 'local') {
        await endSession(sid)
      }
    } catch {
      // continue to results
    }

    const elapsed = Math.max(0, tt - tl)
    const intervalSec = INTERVAL_MS[diff] / 1000
    // Session ended — require another Scan → Start click to re-arm.
    disarmSession()
    setResult({
      total_score: sc,
      duration: elapsed,
      avg_match:
        sc > 0
          ? Math.min(
              Math.round((sc / Math.max(1, Math.floor(elapsed / intervalSec))) * 100),
              100,
            )
          : 0,
    })
    setSessionPhase('complete')
  }, [])

  // Countdown timer
  useEffect(() => {
    if (sessionPhase !== 'active') return

    timerRef.current = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) {
          void handleEnd()
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [sessionPhase, handleEnd])

  // Gesture cycling — only after the pose tracker is actually up, so the
  // first few gestures aren't wasted while mediapipe is still downloading.
  useEffect(() => {
    if (sessionPhase !== 'active') return
    if (!poseVerify.ready) return

    gestureTimerRef.current = setInterval(cycleGesture, INTERVAL_MS[difficulty])

    return () => {
      if (gestureTimerRef.current) clearInterval(gestureTimerRef.current)
    }
  }, [sessionPhase, cycleGesture, difficulty, poseVerify.ready])

  const handleReset = () => {
    // "New Session" from the complete screen: user must Scan → Start again,
    // so fall back to the gated screen rather than re-entering setup directly.
    disarmSession()
    setSessionId(null)
    setResult(null)
    setScore(0)
    setTimeLeft(0)
    setMessage('')
    setSessionPhase('needs_scan')
  }

  // ─── Gate / analyzing ─────────────────────────────
  if (sessionPhase === 'checking') {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="w-10 h-10 text-violet-400 animate-spin" />
      </div>
    )
  }

  if (sessionPhase === 'needs_scan') {
    return (
      <div className="min-h-screen bg-background text-foreground px-4 py-20 flex items-center justify-center relative overflow-hidden">
        <div className="ambient-glow w-[500px] h-[500px] bg-violet-600/8 -top-32 -right-32" />
        <div className="ambient-glow w-[400px] h-[400px] bg-blue-600/6 bottom-20 -left-32" style={{ animationDelay: '3s' }} />
        <div className="relative z-10 max-w-md w-full">
          <div className="liquid-glass rounded-3xl p-8 sm:p-10 border border-white/8 text-center">
            <div className="w-20 h-20 mx-auto rounded-2xl bg-gradient-to-br from-violet-500/20 to-blue-500/15 border border-violet-500/25 flex items-center justify-center mb-6 animate-float">
              <Brain className="w-10 h-10 text-violet-300" />
            </div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-yellow-500/25 bg-yellow-500/10 text-xs text-yellow-300/90 mb-4">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-yellow-500" />
              </span>
              Scan required
            </div>
            <h1 className="text-3xl font-bold mb-3" style={{ fontFamily: 'var(--font-heading)', letterSpacing: '-0.03em' }}>
              <span className="text-foreground">Go for a </span>
              <span className="text-gradient-brand">scan first</span>
            </h1>
            <p className="text-foreground/55 leading-relaxed mb-8">
              Sessions are tailored to your latest brain MRI — pose selection, affected hand,
              and difficulty all come from the scan analysis.
              Upload a brain scan and we'll build your rehab plan.
            </p>
            <div className="flex flex-col sm:flex-row gap-3">
              <button
                onClick={() => navigate('/scan')}
                className="group flex-1 inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl font-semibold text-white transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(139,92,246,0.3)] relative overflow-hidden"
                style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6, #a855f7)' }}
              >
                <div className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/20 to-white/0 -translate-x-full group-hover:translate-x-full transition-transform duration-700" />
                <Brain className="w-5 h-5" />
                Upload Brain Scan
                <ArrowRight className="w-5 h-5" />
              </button>
              <button
                onClick={() => navigate('/')}
                className="px-6 py-3.5 rounded-xl font-semibold text-foreground/60 hover:text-foreground border border-white/10 hover:border-white/25 transition-all duration-200"
              >
                Back home
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (sessionPhase === 'analyzing' || sessionPhase === 'start_analyzing') {
    const title = sessionPhase === 'analyzing' ? 'Analyzing your scan…' : 'Preparing your session…'
    const sub =
      sessionPhase === 'analyzing'
        ? 'Matching MRI findings to your hand exercises'
        : 'Loading camera and session plan'
    return (
      <div className="min-h-screen bg-background text-foreground flex flex-col items-center justify-center px-6">
        <div className="relative w-24 h-24 mb-8">
          <div className="absolute inset-0 rounded-full border-2 border-violet-500/20" />
          <div className="absolute inset-0 rounded-full border-2 border-t-violet-400 border-transparent animate-spin" />
          <Brain className="absolute inset-0 m-auto w-10 h-10 text-violet-400 opacity-90" />
        </div>
        <h2 className="text-2xl font-bold text-foreground mb-2">{title}</h2>
        <p className="text-foreground/50 text-sm text-center max-w-md">{sub}</p>
        <div className="mt-8 flex gap-2">
          {[0, 1, 2].map(i => (
            <span
              key={i}
              className="w-2.5 h-2.5 rounded-full bg-violet-500/50 animate-pulse"
              style={{ animationDelay: `${i * 180}ms` }}
            />
          ))}
        </div>
      </div>
    )
  }

  // ─── Setup ─────────────────────────────────────────
  if (sessionPhase === 'setup') {
    return (
      <div className="min-h-screen bg-background text-foreground px-4 py-20 relative overflow-hidden">
        <div className="ambient-glow w-[500px] h-[500px] bg-violet-600/8 -top-32 -right-32" />
        <div className="ambient-glow w-[400px] h-[400px] bg-blue-600/6 bottom-20 -left-32" style={{ animationDelay: '3s' }} />
        <div className="relative z-10 max-w-2xl mx-auto space-y-8">
          <div className="text-center">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-violet-500/20 bg-violet-500/5 text-sm text-violet-300/80 mb-4">
              <span className="relative flex h-2 w-2"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-violet-400 opacity-75" /><span className="relative inline-flex rounded-full h-2 w-2 bg-violet-500" /></span>
              Rehab Configuration
            </div>
            <h1 className="text-4xl font-bold mb-2" style={{ fontFamily: 'var(--font-heading)', letterSpacing: '-0.03em' }}>
              <span className="text-foreground">New </span><span className="text-gradient-brand">Session</span>
            </h1>
            <p className="text-foreground/40">Configure your rehabilitation — based on your latest scan</p>
          </div>

          {/* MRI → distinct pose plan (for demo / judges) */}
          {scanPlan && (
            <div className="liquid-glass rounded-2xl p-4 border border-cyan-500/25 bg-cyan-500/5">
              <div className="flex items-start gap-3">
                <div className="w-9 h-9 rounded-xl bg-cyan-500/15 border border-cyan-500/25 flex items-center justify-center shrink-0">
                  <Target className="w-5 h-5 text-cyan-400" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-cyan-200 mb-0.5">{scanPlan.label}</p>
                  <p className="text-xs text-foreground/55 leading-relaxed">{scanPlan.description}</p>
                  <p className="text-[10px] font-mono text-foreground/35 mt-2 tabular-nums">
                    Plan ID: {scanPlan.planId} · {scanPlan.exercises.length} poses
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Brain Scan Recommendation Banner */}
          {scanAnalysis && scanAnalysis.stroke_type !== 'None' && (
            <div className="liquid-glass rounded-2xl p-4 border border-violet-500/20 bg-violet-500/5">
              <div className="flex items-start gap-3">
                <div className="w-9 h-9 rounded-xl bg-violet-500/15 border border-violet-500/25 flex items-center justify-center shrink-0">
                  <Brain className="w-5 h-5 text-violet-400" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-violet-300 mb-0.5">
                    Brain scan detected: {scanAnalysis.stroke_type} Stroke
                  </p>
                  <p className="text-xs text-foreground/55 leading-relaxed">
                    Each MRI type maps to a different pose list above — compare scans side-by-side for your demo.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Hand Selection */}
          <div className="liquid-glass rounded-2xl p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Hand className="w-5 h-5 text-blue-400" /> Affected Hand
            </h2>
            <div className="flex gap-3">
              {(['left', 'right'] as const).map(h => (
                <button
                  key={h}
                  onClick={() => setHand(h)}
                  className={`flex-1 py-3 rounded-xl font-medium transition-all duration-300 ${
                    hand === h
                      ? 'bg-blue-600/30 border border-blue-500/50 text-blue-300'
                      : 'bg-white/5 border border-white/10 text-foreground/40 hover:bg-white/10'
                  }`}
                >
                  <Hand className={`w-5 h-5 mx-auto mb-1 ${h === 'left' ? 'scale-x-[-1]' : ''}`} />
                  {h.charAt(0).toUpperCase() + h.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Exercises — scan-first list + optional full picker */}
          <div className="liquid-glass rounded-2xl p-6">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <Target className="w-5 h-5 text-purple-400" /> Selected poses
              </h2>
              <button
                type="button"
                onClick={() => setShowExercisePicker(p => !p)}
                className="text-xs font-medium text-violet-300 hover:text-violet-200 underline-offset-2 hover:underline"
              >
                {showExercisePicker ? 'Hide library' : 'Add / change exercises'}
              </button>
            </div>
            <div className="flex flex-wrap gap-2 mb-4">
              {exercises.map(id => {
                const g = GESTURE_LIST.find(x => x.id === id)
                return (
                  <button
                    key={id}
                    type="button"
                    onClick={() => toggleExercise(id)}
                    className="inline-flex items-center gap-2 pl-3 pr-2 py-1.5 rounded-full bg-purple-600/20 border border-purple-500/40 text-sm text-purple-200 hover:bg-purple-600/30"
                  >
                    <span>{g?.icon ?? '•'}</span>
                    <span>{g?.label ?? id}</span>
                    <span className="text-foreground/40 text-lg leading-none">×</span>
                  </button>
                )
              })}
            </div>
            {showExercisePicker && (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-[min(320px,45vh)] overflow-y-auto pr-1 pt-2 border-t border-white/10">
                {GESTURE_LIST.map(ex => (
                  <button
                    key={ex.id}
                    type="button"
                    onClick={() => toggleExercise(ex.id)}
                    className={`p-3 rounded-xl text-center transition-all duration-300 ${
                      exercises.includes(ex.id)
                        ? 'bg-purple-600/25 border border-purple-500/50 text-purple-300'
                        : 'bg-white/5 border border-white/10 text-foreground/40 hover:bg-white/10'
                    }`}
                  >
                    <span className="text-xl block mb-0.5">{ex.icon}</span>
                    <span className="text-xs">{ex.label}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Difficulty */}
          <div className="liquid-glass rounded-2xl p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Zap className="w-5 h-5 text-yellow-400" /> Difficulty
            </h2>
            <div className="flex gap-3">
              {(['easy', 'medium', 'hard'] as const).map(d => (
                <button
                  key={d}
                  onClick={() => setDifficulty(d)}
                  className={`flex-1 py-3 rounded-xl font-medium capitalize transition-all duration-300 ${
                    difficulty === d
                      ? d === 'easy' ? 'bg-green-600/25 border border-green-500/50 text-green-300'
                        : d === 'medium' ? 'bg-yellow-600/25 border border-yellow-500/50 text-yellow-300'
                        : 'bg-red-600/25 border border-red-500/50 text-red-300'
                      : 'bg-white/5 border border-white/10 text-foreground/40 hover:bg-white/10'
                  }`}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>

          {/* Duration */}
          <div className="liquid-glass rounded-2xl p-6 border border-white/[0.06]">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Clock className="w-5 h-5 text-cyan-400" /> Duration
            </h2>
            <div className="flex gap-3">
              {DURATIONS.map(d => (
                <button
                  key={d}
                  onClick={() => setDuration(d)}
                  className={`flex-1 py-3 rounded-xl font-medium transition-all duration-300 ${
                    duration === d
                      ? 'bg-cyan-600/25 border border-cyan-500/50 text-cyan-300'
                      : 'bg-white/5 border border-white/10 text-foreground/40 hover:bg-white/10'
                  }`}
                >
                  {d} min
                </button>
              ))}
            </div>
          </div>

          {/* Start Button */}
          <button
            onClick={handleStart}
            disabled={exercises.length === 0 || loading || !planLoaded}
            className="group w-full py-4 rounded-2xl font-bold text-lg transition-all duration-300 text-white disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-3 relative overflow-hidden hover:-translate-y-0.5 hover:shadow-[0_8px_40px_rgba(139,92,246,0.3)]"
            style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6, #a855f7)' }}
          >
            <div className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/20 to-white/0 -translate-x-full group-hover:translate-x-full transition-transform duration-700" />
            {loading ? (
              <div className="w-6 h-6 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : !planLoaded ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" /> Loading scan plan…
              </>
            ) : (
              <>
                <Play className="w-6 h-6" /> Start Session
              </>
            )}
          </button>
        </div>
      </div>
    )
  }

  // ─── Active ────────────────────────────────────────
  if (sessionPhase === 'active') {
    return (
      <div className="min-h-screen bg-background text-foreground px-4 py-12 flex flex-col items-center relative overflow-hidden">
        <div className="ambient-glow w-[500px] h-[500px] bg-purple-600/6 -top-32 -right-32" />
        <div className="ambient-glow w-[400px] h-[400px] bg-blue-600/5 bottom-20 -left-32" style={{ animationDelay: '3s' }} />
        <div className="relative z-10 max-w-5xl w-full space-y-6">
          {/* Target gesture label */}
          <div className="text-center">
            <p className="text-xs text-foreground/30 uppercase tracking-[0.2em] font-bold mb-2">Target Gesture</p>
            <h2 className="text-3xl font-bold text-gradient-brand capitalize">
              {currentGesture.replace('_', ' ')}
            </h2>
          </div>

          {/* Reference + guide vs live camera */}
          <div className="liquid-glass rounded-3xl p-4 sm:p-6 relative">
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="w-48 h-48 rounded-full bg-blue-500/5 pulse-ring" />
            </div>
            <div className="relative grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch">
              <div className="space-y-2">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-violet-300/90 flex items-center gap-2">
                  <Target className="w-3.5 h-3.5" /> Target — match this
                </p>
                <div className="flex flex-col sm:flex-row items-center justify-center gap-4 rounded-2xl border border-white/10 bg-black/15 p-3">
                  {poseManifest[currentGesture] && (
                    <div className="shrink-0 rounded-xl border border-white/10 bg-black/25 p-2 w-full sm:w-[42%] max-w-[220px]">
                      <img
                        src={`/poses/${poseManifest[currentGesture]}`}
                        alt={`Reference: ${currentGesture}`}
                        className="w-full h-auto max-h-44 object-contain rounded-lg"
                      />
                      <p className="text-center text-[10px] text-foreground/25 mt-1 uppercase tracking-wider">Reference photo</p>
                    </div>
                  )}
                  <div className="flex items-center justify-center min-w-0 flex-1">
                    {SKELETON_TEMPLATE[currentGesture] === 'arm'
                      ? <ArmSkeleton gesture={currentGesture} />
                      : (
                        <SkeletonHand
                          template={SKELETON_TEMPLATE[currentGesture] as 'open_hand' | 'fist' | 'point'}
                        />
                      )
                    }
                  </div>
                </div>
              </div>
              <div className="space-y-2 flex flex-col">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-cyan-300/90 flex items-center gap-2">
                  <Camera className="w-3.5 h-3.5" /> You — live camera
                </p>
                <div className="flex-1 rounded-2xl border border-white/10 bg-black/30 overflow-hidden min-h-[200px] flex flex-col relative">
                  <div className="relative flex-1 min-h-[200px] max-h-80">
                    <video
                      ref={videoRef}
                      autoPlay
                      playsInline
                      muted
                      className="absolute inset-0 w-full h-full object-cover -scale-x-100"
                    />
                    <canvas
                      ref={canvasRef}
                      className="absolute inset-0 w-full h-full object-cover pointer-events-none -scale-x-100"
                      aria-hidden
                    />
                    <div className="absolute top-2 left-2 right-2 flex flex-wrap items-start justify-between gap-2 pointer-events-none">
                      <div
                        className={`rounded-lg px-2.5 py-1.5 text-[11px] font-medium backdrop-blur-sm border ${
                          poseVerify.error
                            ? 'bg-red-500/20 border-red-400/40 text-red-200'
                            : poseVerify.matchPct >= 75
                              ? 'bg-emerald-500/25 border-emerald-400/35 text-emerald-100'
                              : 'bg-black/50 border-white/15 text-foreground/90'
                        }`}
                      >
                        {poseVerify.error ? (
                          <span>Tracker: {poseVerify.error}</span>
                        ) : !poseVerify.ready ? (
                          <span>
                            {ARM_EXERCISE_IDS.includes(currentGesture)
                              ? 'Loading hand + arm trackers…'
                              : 'Loading hand tracker…'}
                          </span>
                        ) : (
                          <>
                            <span className="tabular-nums font-bold">{poseVerify.matchPct}%</span>
                            <span className="text-foreground/70"> match</span>
                            {ARM_EXERCISE_IDS.includes(currentGesture) && (
                              <span className="block text-[10px] text-cyan-300/80 mt-0.5">
                                {poseVerify.posePresent ? 'Arms tracked (cyan)' : 'Step back — show upper body'}
                              </span>
                            )}
                            {poseVerify.detected && poseVerify.detected !== currentGesture && (
                              <span className="block text-[10px] text-foreground/55 mt-0.5">
                                Camera sees: {poseVerify.detected.replace(/_/g, ' ')}
                              </span>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                  <p className="text-[10px] text-center text-foreground/25 py-2 px-2 border-t border-white/5">
                    {ARM_EXERCISE_IDS.includes(currentGesture)
                      ? 'Mirror view — cyan lines: shoulders & arms; blue/pink: hand. Match the target.'
                      : 'Mirror view — skeleton overlay tracks your hand; match the target'}
                  </p>
                </div>
              </div>
            </div>

            {/* Hold-time progress — fills when matching, rewards sustained pose */}
            <div className="mt-4 px-1">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-foreground/50">
                  Hold progress
                </span>
                <span className="text-[10px] tabular-nums text-foreground/40">
                  {Math.round(holdProgress * 100)}%
                </span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-white/5 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-100 ease-linear"
                  style={{
                    width: `${Math.min(100, holdProgress * 100)}%`,
                    background: holdProgress >= 1
                      ? 'linear-gradient(90deg, #34d399, #10b981)'
                      : 'linear-gradient(90deg, #60a5fa, #a78bfa)',
                  }}
                />
              </div>
            </div>
          </div>

          {/* Posses reference gallery */}
          {possesImages.length > 0 && (
            <div className="liquid-glass rounded-2xl p-4">
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs font-medium text-foreground/50 uppercase tracking-wider">Therapist Reference</p>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPossesIndex(i => (i - 1 + possesImages.length) % possesImages.length)}
                    className="w-7 h-7 rounded-lg bg-white/8 hover:bg-white/15 flex items-center justify-center transition-colors"
                  >
                    <ChevronLeft className="w-4 h-4 text-foreground/60" />
                  </button>
                  <span className="text-xs text-foreground/40 tabular-nums">{possesIndex + 1}/{possesImages.length}</span>
                  <button
                    onClick={() => setPossesIndex(i => (i + 1) % possesImages.length)}
                    className="w-7 h-7 rounded-lg bg-white/8 hover:bg-white/15 flex items-center justify-center transition-colors"
                  >
                    <ChevronRight className="w-4 h-4 text-foreground/60" />
                  </button>
                </div>
              </div>
              <img
                src={`/posses/${possesImages[possesIndex]}`}
                alt="Therapist reference pose"
                className="w-full max-h-56 object-contain rounded-xl bg-black/20"
              />
            </div>
          )}

          {/* Message */}
          <div className="text-center min-h-8">
            <p className={`text-lg font-semibold transition-all duration-300 ${
              message.includes('+1') ? 'text-green-400' : message.includes('Hold') ? 'text-yellow-400' : 'text-blue-300'
            }`}>
              {message}
            </p>
          </div>

          {/* Timer + Score row */}
          <div className="flex items-center justify-between gap-4">
            <CircularTimer remaining={timeLeft} total={totalTime} />

            <div className="liquid-glass rounded-2xl px-6 py-4 text-center flex-1 border border-white/[0.06]">
              <p className="text-xs text-foreground/30 uppercase tracking-[0.15em] font-bold mb-1">Score</p>
              <p className="text-4xl font-bold text-gradient-brand tabular-nums">{score}</p>
            </div>
          </div>

          {/* Voice + End buttons */}
          <div className="flex gap-3">
            <button
              onClick={() => playVoice(currentGesture)}
              className="flex-1 py-3 rounded-xl liquid-glass text-blue-300 hover:bg-white/10 transition-all flex items-center justify-center gap-2 font-medium"
            >
              <Volume2 className="w-5 h-5" /> Replay Voice
            </button>
            <button
              onClick={handleEnd}
              className="flex-1 py-3 rounded-xl bg-red-600/20 border border-red-500/30 text-red-300 hover:bg-red-600/30 transition-all flex items-center justify-center gap-2 font-medium"
            >
              <Square className="w-5 h-5" /> End Session
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ─── Complete ──────────────────────────────────────
  return (
    <div className="min-h-screen bg-background text-foreground px-4 py-20 flex items-center justify-center relative overflow-hidden">
      <div className="ambient-glow w-[500px] h-[500px] bg-emerald-600/8 top-[30%] left-[20%]" />
      <div className="ambient-glow w-[400px] h-[400px] bg-purple-600/6 bottom-[20%] right-[20%]" style={{ animationDelay: '3s' }} />
      <div className="relative z-10 max-w-md w-full space-y-8 text-center">
        <div>
          <div className="w-20 h-20 mx-auto rounded-full bg-gradient-to-br from-emerald-500/20 to-green-500/15 border border-emerald-500/30 flex items-center justify-center mb-5 animate-float">
            <Trophy className="w-10 h-10 text-emerald-400" />
          </div>
          <h1 className="text-3xl font-bold mb-2" style={{ fontFamily: 'var(--font-heading)', letterSpacing: '-0.03em' }}>
            <span className="text-foreground">Session </span><span className="text-gradient-brand">Complete!</span>
          </h1>
          <p className="text-foreground/40">Great work on your rehabilitation</p>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div className="liquid-glass rounded-2xl p-5 border border-white/[0.06]">
            <p className="text-xs text-foreground/30 uppercase tracking-wider font-bold mb-1">Score</p>
            <p className="text-2xl font-bold text-blue-400">{result?.total_score ?? 0}</p>
          </div>
          <div className="liquid-glass rounded-2xl p-5 border border-white/[0.06]">
            <p className="text-xs text-foreground/30 uppercase tracking-wider font-bold mb-1">Duration</p>
            <p className="text-2xl font-bold text-purple-400">
              {result ? `${Math.floor(result.duration / 60)}:${(result.duration % 60).toString().padStart(2, '0')}` : '0:00'}
            </p>
          </div>
          <div className="liquid-glass rounded-2xl p-5 border border-white/[0.06]">
            <p className="text-xs text-foreground/30 uppercase tracking-wider font-bold mb-1">Avg Match</p>
            <p className="text-2xl font-bold text-pink-400">{result?.avg_match ?? 0}%</p>
          </div>
        </div>

        <div className="flex gap-3">
          <a
            href="/dashboard"
            className="flex-1 py-3 rounded-xl liquid-glass text-blue-300 hover:bg-white/10 transition-all flex items-center justify-center gap-2 font-medium"
          >
            View Dashboard <ArrowRight className="w-4 h-4" />
          </a>
          <button
            onClick={handleReset}
            className="flex-1 py-3 rounded-xl bg-white/5 border border-white/10 text-foreground/50 hover:bg-white/10 transition-all flex items-center justify-center gap-2 font-medium"
          >
            <RotateCcw className="w-4 h-4" /> New Session
          </button>
        </div>
      </div>
    </div>
  )
}
