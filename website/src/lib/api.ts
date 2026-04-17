/**
 * Base URL for API calls. In Vite dev, default '' uses same-origin `/api` (proxied to FastAPI).
 * Set VITE_API_URL in `.env` for production or if the backend runs elsewhere.
 */
const API = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? '' : 'http://localhost:8000')

function apiUrl(path: string) {
  const p = path.startsWith('/') ? path : `/${path}`
  return `${API}${p}`
}

export async function uploadScan(file: File) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(apiUrl('/api/scan/upload'), { method: 'POST', body: form })
  if (!res.ok) {
    const t = await res.text()
    let detail = t
    try {
      const j = JSON.parse(t)
      detail = j.detail ?? t
    } catch {
      /* use text */
    }
    throw new Error(typeof detail === 'string' ? detail : `Upload failed (${res.status})`)
  }
  return res.json()
}

export async function getScans() {
  const res = await fetch(apiUrl('/api/scans'))
  return res.json()
}

export async function getLatestScanAnalysis() {
  const res = await fetch(apiUrl('/api/scan/latest-analysis'))
  return res.json()
}

export async function getHandReference() {
  const res = await fetch(apiUrl('/api/hand/reference'))
  return res.json()
}

export async function saveHandReference(payload: { angles: number[]; wrist: number }) {
  const res = await fetch(apiUrl('/api/hand/reference'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return res.json()
}

export async function startSession(config: {
  affected_hand: string
  exercises: string[]
  difficulty: string
  duration_minutes: number
}) {
  const res = await fetch(apiUrl('/api/session/start'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  })
  return res.json()
}

export async function endSession(id: string) {
  const res = await fetch(apiUrl(`/api/session/${id}/end`), { method: 'POST' })
  return res.json()
}

export async function getSessions() {
  const res = await fetch(apiUrl('/api/sessions'))
  return res.json()
}

export async function getPatient() {
  const res = await fetch(apiUrl('/api/patient'))
  return res.json()
}

export async function updatePatient(profile: any) {
  const res = await fetch(apiUrl('/api/patient'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profile),
  })
  return res.json()
}

export async function generateVoices() {
  const res = await fetch(apiUrl('/api/voice/generate'), { method: 'POST' })
  return res.json()
}

export async function getVoiceStatus() {
  const res = await fetch(apiUrl('/api/voice/status'))
  return res.json()
}

export function voiceUrl(key: string) {
  return apiUrl(`/api/voice/play/${key}`)
}
