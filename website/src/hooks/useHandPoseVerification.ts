import { useEffect, useRef, useState } from 'react'
import type { Gesture } from '../config/gestures'
import { ARM_EXERCISE_IDS } from '../config/gestures'
import { HAND_EDGES, matchGesture, type Landmark } from '../lib/gestureFromLandmarks'

const WASM_VER = '0.10.34'
const WASM_URL = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${WASM_VER}/wasm`
const HAND_MODEL_URL =
  'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task'
/** BlazePose — upper body (arms) for rehab exercises */
const POSE_MODEL_URL =
  'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task'

/** Shoulders + arms: 11 L shoulder, 12 R shoulder, 13 L elbow, 14 R elbow, 15 L wrist, 16 R wrist */
const UPPER_BODY_EDGES: [number, number][] = [
  [11, 12],
  [11, 13],
  [13, 15],
  [12, 14],
  [14, 16],
]

const ARM_JOINT_IDX = [11, 12, 13, 14, 15, 16]

export type PoseVerifyState = {
  ready: boolean
  error: string | null
  matchPct: number
  detected: Gesture | null
  hint: string
  handPresent: boolean
  landmarks: Landmark[] | null
  posePresent: boolean
}

function drawAll(
  canvas: HTMLCanvasElement,
  video: HTMLVideoElement,
  poseLm: Landmark[] | undefined,
  handLm: Landmark[] | undefined,
  mirrored: boolean,
  drawPose: boolean,
) {
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const w = video.videoWidth || canvas.clientWidth
  const h = video.videoHeight || canvas.clientHeight
  if (w < 2 || h < 2) return

  canvas.width = w
  canvas.height = h
  ctx.clearRect(0, 0, w, h)

  const px = (p: Landmark) => ({
    x: mirrored ? (1 - p.x) * w : p.x * w,
    y: p.y * h,
  })

  if (drawPose && poseLm && poseLm.length > 16) {
    ctx.strokeStyle = 'rgba(34, 211, 238, 0.92)'
    ctx.lineWidth = Math.max(3.5, w / 140)
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    for (const [a, b] of UPPER_BODY_EDGES) {
      const pa = px(poseLm[a])
      const pb = px(poseLm[b])
      ctx.beginPath()
      ctx.moveTo(pa.x, pa.y)
      ctx.lineTo(pb.x, pb.y)
      ctx.stroke()
    }
    ctx.fillStyle = 'rgba(251, 191, 36, 0.98)'
    for (const i of ARM_JOINT_IDX) {
      const p = px(poseLm[i])
      ctx.beginPath()
      ctx.arc(p.x, p.y, Math.max(4, w / 150), 0, Math.PI * 2)
      ctx.fill()
    }
  }

  if (!handLm?.length) return

  ctx.strokeStyle = 'rgba(96, 165, 250, 0.88)'
  ctx.lineWidth = Math.max(2, w / 200)
  for (const [a, b] of HAND_EDGES) {
    const pa = px(handLm[a])
    const pb = px(handLm[b])
    ctx.beginPath()
    ctx.moveTo(pa.x, pa.y)
    ctx.lineTo(pb.x, pb.y)
    ctx.stroke()
  }

  ctx.fillStyle = 'rgba(244, 114, 182, 0.95)'
  for (let i = 0; i < handLm.length; i++) {
    const p = px(handLm[i])
    ctx.beginPath()
    ctx.arc(p.x, p.y, Math.max(2, w / 220), 0, Math.PI * 2)
    ctx.fill()
  }
}

export function useHandPoseVerification(
  videoRef: React.RefObject<HTMLVideoElement | null>,
  canvasRef: React.RefObject<HTMLCanvasElement | null>,
  targetGesture: Gesture,
  active: boolean,
  mirrored: boolean,
): PoseVerifyState {
  const [state, setState] = useState<PoseVerifyState>({
    ready: false,
    error: null,
    matchPct: 0,
    detected: null,
    hint: '',
    handPresent: false,
    landmarks: null,
    posePresent: false,
  })

  const smoothRef = useRef(0)
  const isArmExercise = ARM_EXERCISE_IDS.includes(targetGesture)

  useEffect(() => {
    smoothRef.current = 0
  }, [targetGesture])

  useEffect(() => {
    if (!active) {
      setState({
        ready: false,
        error: null,
        matchPct: 0,
        detected: null,
        hint: '',
        handPresent: false,
        landmarks: null,
        posePresent: false,
      })
      return
    }

    let cancelled = false
    let raf = 0
    let handLandmarker: import('@mediapipe/tasks-vision').HandLandmarker | null = null
    let poseLandmarker: import('@mediapipe/tasks-vision').PoseLandmarker | null = null

    const loop = () => {
      const video = videoRef.current
      const canvas = canvasRef.current
      if (!cancelled && handLandmarker && video && video.readyState >= 2) {
        try {
          const ts = performance.now()
          let poseLm: Landmark[] | undefined
          if (isArmExercise && poseLandmarker) {
            const pr = poseLandmarker.detectForVideo(video, ts)
            poseLm = pr.landmarks[0] as Landmark[] | undefined
          }

          const hr = handLandmarker.detectForVideo(video, ts)
          const raw = hr.landmarks[0] as Landmark[] | undefined
          const m = matchGesture(targetGesture, raw)

          const smoothed = smoothRef.current * 0.65 + m.matchPct * 0.35
          smoothRef.current = smoothed

          const poseOk = Boolean(isArmExercise && poseLm && poseLm.length > 16)

          setState({
            ready: true,
            error: null,
            matchPct: Math.round(smoothed),
            detected: m.detected,
            hint: m.label,
            handPresent: m.handPresent,
            landmarks: raw ?? null,
            posePresent: poseOk,
          })

          if (canvas) {
            drawAll(canvas, video, poseLm, raw, mirrored, isArmExercise)
          }
        } catch {
          /* skip frame */
        }
      }
      raf = requestAnimationFrame(loop)
    }

    ;(async () => {
      try {
        const { FilesetResolver, HandLandmarker, PoseLandmarker } = await import('@mediapipe/tasks-vision')
        const wasm = await FilesetResolver.forVisionTasks(WASM_URL)

        if (isArmExercise) {
          try {
            poseLandmarker = await PoseLandmarker.createFromOptions(wasm, {
              baseOptions: { modelAssetPath: POSE_MODEL_URL, delegate: 'CPU' },
              runningMode: 'VIDEO',
              numPoses: 1,
              minPoseDetectionConfidence: 0.35,
              minPosePresenceConfidence: 0.35,
              minTrackingConfidence: 0.35,
            })
          } catch {
            poseLandmarker = null
          }
        }

        handLandmarker = await HandLandmarker.createFromOptions(wasm, {
          baseOptions: { modelAssetPath: HAND_MODEL_URL, delegate: 'CPU' },
          runningMode: 'VIDEO',
          numHands: 1,
          minHandDetectionConfidence: 0.45,
          minHandPresenceConfidence: 0.45,
          minTrackingConfidence: 0.45,
        })

        if (cancelled) {
          handLandmarker.close()
          poseLandmarker?.close()
          return
        }
        setState(s => ({ ...s, ready: true, error: null }))
        raf = requestAnimationFrame(loop)
      } catch (e) {
        const msg = e instanceof Error ? e.message : 'Vision model failed to load'
        setState(s => ({ ...s, ready: false, error: msg }))
      }
    })()

    return () => {
      cancelled = true
      cancelAnimationFrame(raf)
      if (handLandmarker) {
        try {
          handLandmarker.close()
        } catch {
          /* ignore */
        }
      }
      if (poseLandmarker) {
        try {
          poseLandmarker.close()
        } catch {
          /* ignore */
        }
      }
    }
  }, [active, targetGesture, videoRef, canvasRef, mirrored, isArmExercise])

  return state
}
