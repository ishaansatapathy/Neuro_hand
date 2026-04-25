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
import { saveScanForSession, armSession } from '../lib/sessionGate'
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from 'recharts'

interface StrokeZone {
  zone: string
  region: string
  severity: number
  effects: string[]
}

interface ScanMetrics {
  lesion_coverage_pct: number
  hemisphere_asymmetry: number
  affected_side: string
  mean_intensity: number
  intensity_std: number
  zones_affected: number
  avg_severity: number
}

interface StrokeAnalysisData {
  stroke_type: string
  description: string
  affected_zones: StrokeZone[]
  neuroplasticity_targets: string[]
  recovery_potential: string
  scan_metrics?: ScanMetrics
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
      <div className="ambient-glow w-[600px] h-[600px] bg-blue-600/10 -top-48 -left-48" />
      <div className="ambient-glow w-[500px] h-[500px] bg-purple-600/8 -bottom-32 -right-32" style={{ animationDelay: '3s' }} />
      <div className="ambient-glow w-[400px] h-[400px] bg-pink-600/6 top-[40%] right-[5%]" style={{ animationDelay: '5s' }} />

      <div className="relative z-10 max-w-4xl mx-auto px-4 sm:px-6 py-12 sm:py-20">
        <div className="text-center mb-14">
          <div className="inline-flex items-center gap-2 px-5 py-2 rounded-full border border-blue-500/20 bg-blue-500/5 text-sm text-blue-300/80 mb-8">
            <span className="relative flex h-2 w-2"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" /><span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" /></span>
            <Brain className="w-4 h-4 text-blue-400" />
            AI-Powered Brain Scan Analysis
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold mb-5" style={{ fontFamily: 'var(--font-heading)', letterSpacing: '-0.03em' }}>
            <span className="text-foreground">Upload </span><span className="text-gradient-brand">Brain Scan</span>
          </h1>
          <p className="text-foreground/45 text-lg max-w-xl mx-auto leading-relaxed">
            Upload an MRI scan for instant AI classification. Our model detects stroke patterns
            with high accuracy to guide your rehabilitation.
          </p>
        </div>

        <div className="liquid-glass card-spotlight rounded-3xl p-6 sm:p-8 mb-8 border border-white/8">
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
                        className="mt-4 group/btn relative inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-white transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(139,92,246,0.3)] overflow-hidden"
                        style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6, #a855f7)' }}
                      >
                        <div className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/20 to-white/0 -translate-x-full group-hover/btn:translate-x-full transition-transform duration-700" />
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
                  <div className="flex flex-col items-center gap-5 cursor-pointer">
                    <div className="relative">
                      <div className="w-18 h-18 rounded-2xl bg-gradient-to-br from-blue-500/15 to-purple-500/10 border border-white/8 flex items-center justify-center animate-float">
                        <FileImage className="w-9 h-9 text-blue-400/70" />
                      </div>
                      <div className="absolute -inset-2 rounded-3xl bg-blue-500/5 animate-ping opacity-30" style={{ animationDuration: '3s' }} />
                    </div>
                    <div className="text-center">
                      <p className="text-foreground/60 text-lg font-medium">
                        Drop your brain scan here or click to browse
                      </p>
                      <p className="text-foreground/25 text-sm mt-1.5">
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
                <div className="space-y-6">
                  <div className="gradient-divider" />

                  {/* ── Section Header ── */}
                  <div className="p-5 rounded-xl bg-red-500/5 border border-red-500/15">
                    <h3 className="text-base font-bold text-red-400 mb-1.5 flex items-center gap-2">
                      <AlertCircle className="w-5 h-5" />
                      {result.stroke_analysis.stroke_type} — Detailed Neuro Analysis
                    </h3>
                    <p className="text-sm text-foreground/60 leading-relaxed">
                      {result.stroke_analysis.description}
                    </p>
                  </div>

                  {/* ── Scan Metrics Cards ── */}
                  {result.stroke_analysis.scan_metrics && (
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      {[
                        {
                          label: 'Lesion Coverage',
                          value: `${result.stroke_analysis.scan_metrics.lesion_coverage_pct.toFixed(1)}%`,
                          color: '#f472b6',
                        },
                        {
                          label: 'Asymmetry Index',
                          value: result.stroke_analysis.scan_metrics.hemisphere_asymmetry.toFixed(3),
                          color: '#a78bfa',
                        },
                        {
                          label: 'Zones Affected',
                          value: String(result.stroke_analysis.scan_metrics.zones_affected),
                          color: '#60a5fa',
                        },
                        {
                          label: 'Avg Severity',
                          value: `${(result.stroke_analysis.scan_metrics.avg_severity * 100).toFixed(0)}%`,
                          color: '#fb923c',
                        },
                      ].map((stat) => (
                        <div
                          key={stat.label}
                          className="rounded-xl border border-white/8 ' bg-white/[0.02]' p-4 text-center"
                        >
                          <p
                            className="text-2xl font-bold tabular-nums"
                            style={{ color: stat.color }}
                          >
                            {stat.value}
                          </p>
                          <p className="text-[10px] uppercase tracking-wider text-foreground/40 mt-1">
                            {stat.label}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* ── Radar Chart + Zone Severity Bars ── */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

                    {/* Radar Chart */}
                    <div className="rounded-xl border border-white/8 'bg-white/[0.02]' p-5">
                      <h4 className="text-xs font-semibold uppercase tracking-wider text-foreground/40 mb-4 flex items-center gap-2">
                        <Activity className="w-3.5 h-3.5" />
                        Affected Brain Regions
                      </h4>
                      <div className="w-full" style={{ height: 260 }}>
                        <ResponsiveContainer width="100%" height="100%">
                          <RadarChart
                            data={result.stroke_analysis.affected_zones.map((z) => ({
                              zone: z.zone.length > 20 ? z.zone.slice(0, 18) + '…' : z.zone,
                              severity: Math.round(z.severity * 100),
                              fullMark: 100,
                            }))}
                          >
                            <PolarGrid stroke="rgba(255,255,255,0.06)" />
                            <PolarAngleAxis
                              dataKey="zone"
                              tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 10 }}
                            />
                            <PolarRadiusAxis
                              angle={90}
                              domain={[0, 100]}
                              tick={{ fill: 'rgba(255,255,255,0.2)', fontSize: 9 }}
                              axisLine={false}
                            />
                            <Radar
                              name="Severity"
                              dataKey="severity"
                              stroke="#f472b6"
                              fill="url(#radarFill)"
                              fillOpacity={0.5}
                              strokeWidth={2}
                              dot={{ r: 4, fill: '#f472b6', strokeWidth: 0 }}
                              isAnimationActive={true}
                              animationDuration={1200}
                            />
                            <defs>
                              <linearGradient id="radarFill" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#a78bfa" stopOpacity={0.6} />
                                <stop offset="100%" stopColor="#f472b6" stopOpacity={0.15} />
                              </linearGradient>
                            </defs>
                          </RadarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    {/* Zone-by-zone severity bars with effects */}
                    <div className="rounded-xl border border-white/8 'bg-white/[0.02]' p-5">
                      <h4 className="text-xs font-semibold uppercase tracking-wider text-foreground/40 mb-4">
                        Zone Severity Breakdown
                      </h4>
                      <div className="space-y-4">
                        {result.stroke_analysis.affected_zones.map((zone, i) => {
                          const pct = Math.round(zone.severity * 100)
                          const color =
                            pct >= 80
                              ? 'linear-gradient(90deg, #ef4444, #f472b6)'
                              : pct >= 50
                              ? 'linear-gradient(90deg, #f59e0b, #fb923c)'
                              : 'linear-gradient(90deg, #60a5fa, #a78bfa)'
                          return (
                            <div key={i} className="space-y-1.5">
                              <div className="flex justify-between items-baseline">
                                <span className="text-sm text-foreground/80 font-medium leading-tight">
                                  {zone.zone}
                                </span>
                                <span
                                  className="text-xs font-bold tabular-nums"
                                  style={{
                                    color: pct >= 80 ? '#f472b6' : pct >= 50 ? '#fb923c' : '#a78bfa',
                                  }}
                                >
                                  {pct}%
                                </span>
                              </div>
                              <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                                <div
                                  className="h-full rounded-full transition-all duration-1000 ease-out"
                                  style={{ width: `${pct}%`, background: color }}
                                />
                              </div>
                              <div className="flex flex-wrap gap-1.5 mt-1">
                                {zone.effects.map((eff, j) => (
                                  <span
                                    key={j}
                                    className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 text-foreground/40 border border-white/5"
                                  >
                                    {eff}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  </div>

                  {/* ── Neuroplasticity Targets ── */}
                  {result.stroke_analysis.neuroplasticity_targets &&
                    result.stroke_analysis.neuroplasticity_targets.length > 0 && (
                      <div className="rounded-xl border border-emerald-500/15 'bg-emerald-500/[0.03]' p-5">
                        <h4 className="text-sm font-semibold text-emerald-400 mb-3 flex items-center gap-2">
                          <Brain className="w-4 h-4" />
                          Recommended Neuroplasticity Exercises
                        </h4>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                          {result.stroke_analysis.neuroplasticity_targets.map(
                            (target: string, i: number) => (
                              <div
                                key={i}
                                className="flex items-start gap-2.5 p-3 rounded-lg 'bg-white/[0.03]' border border-white/5 hover:border-emerald-500/20 transition-colors"
                              >
                                <div className="mt-0.5 w-5 h-5 rounded-md bg-emerald-500/15 flex items-center justify-center shrink-0">
                                  <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                                </div>
                                <span className="text-xs text-foreground/60 leading-relaxed">
                                  {target}
                                </span>
                              </div>
                            ),
                          )}
                        </div>
                      </div>
                    )}

                  {/* ── Recovery Potential ── */}
                  {result.stroke_analysis.recovery_potential && (
                    <div
                      className="rounded-xl p-5 border border-blue-500/15"
                      style={{
                        background:
                          'linear-gradient(135deg, rgba(96,165,250,0.06), rgba(167,139,250,0.04), rgba(244,114,182,0.03))',
                      }}
                    >
                      <h4 className="text-sm font-semibold text-blue-400 mb-2 flex items-center gap-2">
                        <Activity className="w-4 h-4" />
                        Recovery Potential
                      </h4>
                      <p className="text-sm text-foreground/60 leading-relaxed">
                        {result.stroke_analysis.recovery_potential}
                      </p>
                    </div>
                  )}
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
                  onClick={() => armSession()}
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

        <div className="liquid-glass card-spotlight rounded-3xl p-6 sm:p-8 border border-white/8">
          <h3 className="text-xl font-bold text-gradient-brand mb-6 flex items-center gap-2">
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
