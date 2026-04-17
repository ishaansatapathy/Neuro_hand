import { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import {
  Brain,
  Upload,
  Activity,
  ArrowRight,
  FileImage,
  X,
  Clock,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from 'lucide-react'
import { uploadScan, getScans } from '../lib/api'
import { saveScanForSession } from '../lib/sessionGate'

interface StrokeZone {
  zone: string
  region: string
  severity: number
  effects: string[]
}

interface StrokeAnalysisData {
  stroke_type: string
  description: string
  affected_zones: StrokeZone[]
  neuroplasticity_targets: string[]
  recovery_potential: string
}

interface ClassificationPayload {
  prediction: string
  confidence: number
  top_predictions: { label: string; probability: number }[]
  uncertain?: boolean
  rejected?: boolean
  reject_reason?: string
  backend?: string
}

interface BrainRegionPayload {
  region: string
  side: string
  description: string
  confidence?: number
}

interface ScanResult {
  predicted_class: string
  confidence: number
  all_predictions: Record<string, number>
  warning?: string
  is_low_confidence?: boolean
  stroke_analysis?: StrokeAnalysisData
  classification?: ClassificationPayload
  brain_region?: BrainRegionPayload
}

interface PreviousScan {
  scan_id?: string
  id?: string
  filename: string
  predicted_class: string
  confidence: number
  uploaded_at?: string
  created_at?: string
}

function ConfidenceGauge({ value }: { value: number }) {
  const radius = 54
  const stroke = 8
  const circumference = 2 * Math.PI * radius
  const progress = circumference - (value / 100) * circumference

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width="140" height="140" className="-rotate-90">
        <circle
          cx="70"
          cy="70"
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={stroke}
        />
        <circle
          cx="70"
          cy="70"
          r={radius}
          fill="none"
          stroke="url(#gaugeGradient)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={progress}
          className="transition-all duration-1000 ease-out"
        />
        <defs>
          <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#60a5fa" />
            <stop offset="50%" stopColor="#a78bfa" />
            <stop offset="100%" stopColor="#f472b6" />
          </linearGradient>
        </defs>
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-3xl font-bold text-foreground">{value.toFixed(1)}%</span>
        <span className="text-xs text-foreground/50 uppercase tracking-wider">Confidence</span>
      </div>
    </div>
  )
}

function PredictionBar({ label, value, isTop }: { label: string; value: number; isTop: boolean }) {
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-sm">
        <span className={isTop ? 'text-foreground font-semibold' : 'text-foreground/60'}>{label}</span>
        <span className={isTop ? 'text-foreground font-semibold' : 'text-foreground/40'}>
          {(value * 100).toFixed(1)}%
        </span>
      </div>
      <div className="h-2 rounded-full bg-white/5 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{
            width: `${value * 100}%`,
            background: isTop
              ? 'linear-gradient(90deg, #60a5fa, #a78bfa, #f472b6)'
              : 'rgba(255,255,255,0.15)',
          }}
        />
      </div>
    </div>
  )
}

export default function ScanUpload() {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<ScanResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const [previousScans, setPreviousScans] = useState<PreviousScan[]>([])
  const [scansLoading, setScansLoading] = useState(true)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    getScans()
      .then((data) => setPreviousScans(Array.isArray(data) ? data : []))
      .catch(() => setPreviousScans([]))
      .finally(() => setScansLoading(false))
  }, [result])

  const handleFile = useCallback((f: File) => {
    setFile(f)
    setResult(null)
    setError(null)
    const reader = new FileReader()
    reader.onload = (e) => setPreview(e.target?.result as string)
    reader.readAsDataURL(f)
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragActive(false)
      const dropped = e.dataTransfer.files[0]
      if (dropped) handleFile(dropped)
    },
    [handleFile],
  )

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      const data = await uploadScan(file)
      if (data.error) throw new Error(data.error)
      setResult(data)
      saveScanForSession(data as Record<string, unknown>)
    } catch (err: unknown) {
      const raw = err instanceof Error ? err.message : String(err)
      const hint =
        raw === 'Failed to fetch' || raw.includes('NetworkError')
          ? ' Backend not reachable. In a terminal at the project root run: python server.py (keeps API on port 8000), then click Analyze again.'
          : ''
      setError((raw || 'Upload failed.') + hint)
    } finally {
      setUploading(false)
    }
  }

  const clearFile = () => {
    setFile(null)
    setPreview(null)
    setResult(null)
    setError(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  const sortedPredictions = result?.all_predictions
    ? Object.entries(result.all_predictions).sort(([, a], [, b]) => b - a)
    : []

  return (
    <div className="min-h-screen bg-background relative overflow-hidden">
      <div className="glow-blob w-[500px] h-[500px] bg-blue-500/30 -top-48 -left-48 fixed" />
      <div className="glow-blob w-[400px] h-[400px] bg-purple-500/20 -bottom-32 -right-32 fixed" />

      <div className="relative z-10 max-w-4xl mx-auto px-4 sm:px-6 py-12 sm:py-20">
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full liquid-glass text-sm text-foreground/70 mb-6">
            <Brain className="w-4 h-4 text-blue-400" />
            AI-Powered Brain Scan Analysis
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold text-gradient mb-4">
            Upload Brain Scan
          </h1>
          <p className="text-foreground/50 text-lg max-w-xl mx-auto">
            Upload an MRI scan for instant AI classification. Our model detects stroke patterns
            with high accuracy to guide your rehabilitation.
          </p>
        </div>

        <div className="liquid-glass card-spotlight rounded-2xl p-6 sm:p-8 mb-8">
          {!result ? (
            <>
              <div
                className={`relative border-2 border-dashed rounded-xl transition-all duration-200 ${
                  dragActive
                    ? 'border-blue-400 bg-blue-400/5'
                    : 'border-white/10 hover:border-white/20'
                } ${preview ? 'p-4' : 'p-10 sm:p-16'}`}
                onDragOver={(e) => {
                  e.preventDefault()
                  setDragActive(true)
                }}
                onDragLeave={() => setDragActive(false)}
                onDrop={handleDrop}
                onClick={() => !preview && inputRef.current?.click()}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && !preview && inputRef.current?.click()}
              >
                <input
                  ref={inputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
                />

                {preview ? (
                  <div className="flex flex-col sm:flex-row gap-6 items-center">
                    <div className="relative group shrink-0">
                      <img
                        src={preview}
                        alt="Scan preview"
                        className="w-48 h-48 object-cover rounded-lg border border-white/10"
                      />
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          clearFile()
                        }}
                        className="absolute -top-2 -right-2 w-7 h-7 rounded-full bg-red-500/80 hover:bg-red-500 flex items-center justify-center transition-colors"
                      >
                        <X className="w-4 h-4 text-foreground" />
                      </button>
                    </div>
                    <div className="flex-1 text-center sm:text-left">
                      <p className="text-foreground font-medium text-lg truncate max-w-xs">
                        {file?.name}
                      </p>
                      <p className="text-foreground/40 text-sm mt-1">
                        {file && (file.size / 1024 / 1024).toFixed(2)} MB
                      </p>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          handleUpload()
                        }}
                        disabled={uploading}
                        className="mt-4 inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-foreground transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                        style={{
                          background: 'linear-gradient(135deg, #60a5fa, #a78bfa, #f472b6)',
                        }}
                      >
                        {uploading ? (
                          <>
                            <Loader2 className="w-5 h-5 animate-spin" />
                            Analyzing…
                          </>
                        ) : (
                          <>
                            <Upload className="w-5 h-5" />
                            Analyze Scan
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-4 cursor-pointer">
                    <div className="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center">
                      <FileImage className="w-8 h-8 text-foreground/30" />
                    </div>
                    <div className="text-center">
                      <p className="text-foreground/70 text-lg font-medium">
                        Drop your brain scan here or click to browse
                      </p>
                      <p className="text-foreground/30 text-sm mt-1">
                        Supports JPEG, PNG, DICOM — up to 50 MB
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {error && (
                <div className="mt-4 flex items-center gap-3 px-4 py-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                  <AlertCircle className="w-5 h-5 shrink-0" />
                  {error}
                </div>
              )}
            </>
          ) : (
            <div className="space-y-8">
              <div className="flex flex-col md:flex-row items-center gap-8">
                {preview && (
                  <img
                    src={preview}
                    alt="Analyzed scan"
                    className="w-40 h-40 object-cover rounded-xl border border-white/10 shrink-0"
                  />
                )}
                <div className="flex-1 text-center md:text-left">
                  <p className="text-foreground/40 text-sm uppercase tracking-wider mb-1">
                    Predicted Classification
                  </p>
                  <h2 className="text-3xl sm:text-4xl font-bold text-gradient-brand mb-2">
                    {result.classification?.prediction ?? result.predicted_class}
                  </h2>
                  {result.classification &&
                    result.classification.prediction !== result.predicted_class && (
                    <p className="text-xs text-foreground/40 mb-1">
                      Clinical mapping: {result.predicted_class}
                    </p>
                  )}
                  <div className="flex items-center gap-2 justify-center md:justify-start text-foreground/50 text-sm">
                    {result.is_low_confidence ? (
                      <>
                        <AlertCircle className="w-4 h-4 text-yellow-400" />
                        <span className="text-yellow-400">Low confidence</span>
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="w-4 h-4 text-green-400" />
                        Analysis complete
                      </>
                    )}
                  </div>
                </div>
                <ConfidenceGauge
                  value={(result.classification?.confidence ?? result.confidence) * 100}
                />
              </div>

              {result.brain_region && (
                <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/5 px-4 py-3 text-sm">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-cyan-400/90 mb-1">
                    Rule-based brain region
                  </p>
                  <p className="text-foreground font-medium">{result.brain_region.region}</p>
                  <p className="text-foreground/50 text-xs mt-1">
                    Side hint: <span className="text-foreground/70">{result.brain_region.side}</span>
                    {' · '}
                    {result.brain_region.description}
                  </p>
                </div>
              )}

              {result.classification?.top_predictions &&
                result.classification.top_predictions.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-foreground/40">
                      Top predictions (API)
                    </p>
                    <div className="grid gap-2 sm:grid-cols-3">
                      {result.classification.top_predictions.slice(0, 3).map((row) => (
                        <div
                          key={row.label}
                          className="rounded-lg border border-white/8 bg-white/3 px-3 py-2 text-center"
                        >
                          <p className="text-xs font-medium text-foreground">{row.label}</p>
                          <p className="text-lg font-semibold text-foreground/80">
                            {(row.probability * 100).toFixed(1)}%
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

              {result.warning && (
                <div className="flex items-start gap-3 px-5 py-4 rounded-xl bg-yellow-500/10 border border-yellow-500/20">
                  <AlertCircle className="w-5 h-5 text-yellow-400 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-yellow-300 font-medium text-sm">Warning</p>
                    <p className="text-yellow-200/70 text-sm mt-1">{result.warning}</p>
                  </div>
                </div>
              )}

              <div className="gradient-divider" />

              <div>
                <h3 className="text-foreground/70 text-sm font-semibold uppercase tracking-wider mb-4 flex items-center gap-2">
                  <Activity className="w-4 h-4" />
                  All Class Predictions
                </h3>
                <div className="space-y-3">
                  {sortedPredictions.map(([label, value], i) => (
                    <PredictionBar key={label} label={label} value={value} isTop={i === 0} />
                  ))}
                </div>
              </div>

              {result.stroke_analysis && result.stroke_analysis.stroke_type !== 'None' && (
                <div className="space-y-4">
                  <div className="gradient-divider" />
                  <div className="p-5 rounded-xl bg-red-500/5 border border-red-500/15">
                    <h3 className="text-sm font-semibold text-red-400 mb-2 flex items-center gap-2">
                      <AlertCircle className="w-4 h-4" />
                      {result.stroke_analysis.stroke_type} — Stroke Analysis
                    </h3>
                    <p className="text-xs text-foreground/60 leading-relaxed mb-3">
                      {result.stroke_analysis.description}
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {result.stroke_analysis.affected_zones.slice(0, 4).map((zone, i) => (
                        <div key={i} className="flex items-center gap-2 text-xs text-foreground/50">
                          <div className="w-2 h-2 rounded-full bg-red-400/60 shrink-0" />
                          <span>{zone.zone}</span>
                          <span className="ml-auto text-foreground/30">{(zone.severity * 100).toFixed(0)}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              <div className="flex flex-col sm:flex-row gap-3">
                <Link
                  to="/brain"
                  className="flex-1 inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl font-semibold text-foreground transition-all duration-200 hover:brightness-110"
                  style={{
                    background: 'linear-gradient(135deg, #60a5fa, #a78bfa, #f472b6)',
                  }}
                >
                  <Brain className="w-5 h-5" />
                  View 3D Brain Analysis
                  <ArrowRight className="w-5 h-5" />
                </Link>
                <Link
                  to="/session"
                  className="flex-1 inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl font-semibold text-foreground border border-white/15 hover:border-white/25 transition-all duration-200"
                >
                  Start Rehab Session
                  <ArrowRight className="w-5 h-5" />
                </Link>
                <button
                  onClick={clearFile}
                  className="px-6 py-3.5 rounded-xl font-semibold text-foreground/70 hover:text-foreground border border-white/10 hover:border-white/20 transition-all duration-200"
                >
                  Upload Another Scan
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="liquid-glass card-spotlight rounded-2xl p-6 sm:p-8">
          <h3 className="text-xl font-bold text-gradient mb-6 flex items-center gap-2">
            <Clock className="w-5 h-5 text-blue-400" />
            Previous Scans
          </h3>

          {scansLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 text-foreground/30 animate-spin" />
            </div>
          ) : previousScans.length === 0 ? (
            <div className="text-center py-12">
              <Brain className="w-10 h-10 text-foreground/10 mx-auto mb-3" />
              <p className="text-foreground/30">No previous scans found</p>
              <p className="text-foreground/20 text-sm mt-1">
                Upload your first brain scan above to get started
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {previousScans.map((scan) => (
                <div
                  key={scan.scan_id || scan.id || scan.filename}
                  className="flex items-center gap-4 p-4 rounded-xl bg-white/3 hover:bg-white/6 border border-white/5 transition-colors"
                >
                  <div className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center shrink-0">
                    <FileImage className="w-5 h-5 text-foreground/30" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-foreground/80 font-medium truncate">{scan.filename}</p>
                    <p className="text-foreground/30 text-sm">
                      {new Date(scan.uploaded_at || scan.created_at || 0).toLocaleDateString(undefined, {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric',
                      })}
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-sm font-semibold text-gradient-brand">
                      {scan.predicted_class}
                    </p>
                    <p className="text-foreground/30 text-xs">
                      {(scan.confidence * 100).toFixed(1)}% conf
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
