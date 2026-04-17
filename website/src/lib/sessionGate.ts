/**
 * Session is only allowed after a completed brain scan (client-side gate + UX).
 */
const KEY = 'nh_scan_session'

export interface ScanSnapshot {
  ts: number
  predicted_class?: string
  classification_prediction?: string
  stroke_type?: string
  brain_region?: string
  confidence?: number
}

export function saveScanForSession(data: Record<string, unknown>): void {
  const classification = data.classification as { prediction?: string } | undefined
  const sa = data.stroke_analysis as { stroke_type?: string } | undefined
  const br = data.brain_region as { region?: string } | undefined
  const snap: ScanSnapshot = {
    ts: Date.now(),
    predicted_class: String(data.predicted_class ?? ''),
    classification_prediction: classification?.prediction,
    stroke_type: sa?.stroke_type,
    brain_region: br?.region,
    confidence: typeof data.confidence === 'number' ? data.confidence : undefined,
  }
  try {
    localStorage.setItem(KEY, JSON.stringify(snap))
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new Event('nh-scan-saved'))
    }
  } catch {
    /* ignore */
  }
}

export function loadScanSnapshot(): ScanSnapshot | null {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    return JSON.parse(raw) as ScanSnapshot
  } catch {
    return null
  }
}

export function hasCompletedScan(): boolean {
  return loadScanSnapshot() !== null
}

export function clearScanGate(): void {
  try {
    localStorage.removeItem(KEY)
  } catch {
    /* ignore */
  }
}
