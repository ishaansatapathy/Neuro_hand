import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Brain, AlertTriangle, Zap, Target, ArrowRight, Activity, RefreshCw } from 'lucide-react'
import { BrainCanvas } from '../components/brain/BrainCanvas'
import { contralateralBodySide, lesionSummary, REGION_COLORS, type LesionSide, type StrokeAnalysis, type AffectedZone } from '../lib/brainRules'
import { getLatestScanAnalysis } from '../lib/api'
import { resetBrain } from '../lib/brainVisualizationController'
import { BrainArrowOverlay } from '../components/brain/BrainArrowOverlay'

function SeverityBar({ severity, color }: { severity: number; color: string }) {
  return (
    <div className="h-1.5 w-full rounded-full bg-white/5 overflow-hidden">
      <div
        className="h-full rounded-full transition-all duration-1000 ease-out"
        style={{ width: `${severity * 100}%`, background: color }}
      />
    </div>
  )
}

function ZoneCard({ zone }: { zone: AffectedZone }) {
  const color = REGION_COLORS[zone.region] || '#888'
  return (
    <div className="liquid-glass rounded-xl p-4 border border-white/5 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full shrink-0" style={{ background: color }} />
          <h4 className="text-sm font-semibold text-foreground">{zone.zone}</h4>
        </div>
        <span className="text-xs px-2 py-0.5 rounded-full border shrink-0"
          style={{
            borderColor: color + '40',
            background: color + '15',
            color: color,
          }}>
          {(zone.severity * 100).toFixed(0)}% severity
        </span>
      </div>
      <SeverityBar severity={zone.severity} color={color} />
      <ul className="space-y-1">
        {zone.effects.map((effect, i) => (
          <li key={i} className="text-xs text-foreground/60 flex items-start gap-2">
            <span className="text-foreground/30 mt-0.5">•</span>
            {effect}
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function BrainVisualization() {
  const [lesionSide, setLesionSide] = useState<LesionSide>(null)
  const [analysis, setAnalysis] = useState<StrokeAnalysis | null>(null)
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState(false)

  const loadAnalysis = useCallback(async (withSpinner?: boolean) => {
    if (withSpinner) setLoading(true)
    try {
      const data = await getLatestScanAnalysis()
      setFetchError(false)
      if (data.has_scan && data.stroke_analysis) {
        setAnalysis(data.stroke_analysis)
        const st: string = data.stroke_analysis.stroke_type ?? ''
        if (st.includes('Hemorrhagic')) setLesionSide('right')
        else if (st.includes('Ischemic')) setLesionSide('left')
        else if ((data.stroke_analysis.affected_zones?.length ?? 0) > 0) setLesionSide('left')
        resetBrain()
      } else {
        setAnalysis(null)
        resetBrain()
      }
    } catch {
      setFetchError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadAnalysis()
  }, [loadAnalysis])

  useEffect(() => () => resetBrain(), [])

  const zones = analysis?.affected_zones ?? []
  const hasStroke = analysis && analysis.stroke_type !== 'None' && zones.length > 0

  return (
    <div className="min-h-screen bg-background pb-24 pt-8 relative overflow-hidden">
      <div className="ambient-glow w-[600px] h-[600px] bg-red-600/6 -top-40 -right-40" />
      <div className="ambient-glow w-[400px] h-[400px] bg-purple-600/6 bottom-20 -left-32" style={{ animationDelay: '3s' }} />
      <div className="relative z-10 mx-auto max-w-5xl px-6 md:px-8">
        <header className="mb-8 space-y-2">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-red-500/20 bg-red-500/5 text-sm text-red-300/80 mb-3">
            <span className="relative flex h-2 w-2"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" /><span className="relative inline-flex rounded-full h-2 w-2 bg-red-500" /></span>
            Patient Scan Analysis
          </div>
          <div className="flex items-start justify-between gap-4">
            <h1 className="text-3xl font-bold tracking-tight text-foreground md:text-4xl" style={{ fontFamily: 'var(--font-heading)', letterSpacing: '-0.03em' }}>
              <span className="text-foreground">3D Brain — </span><span className="text-gradient-brand">Stroke Effect Zones</span>
            </h1>
            <button
              type="button"
              onClick={() => void loadAnalysis(true)}
              disabled={loading}
              className="shrink-0 mt-1 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-white/10 bg-white/5 hover:bg-white/10 text-foreground/60 transition-colors disabled:opacity-40"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
          <p className="text-sm leading-relaxed text-foreground/65">
            {fetchError
              ? 'Server not reachable — make sure server.py is running on port 8000.'
              : analysis
              ? `Showing affected brain regions based on ${analysis.predicted_class} classification. Rotate the model to explore.`
              : 'Upload a brain scan to see affected zones highlighted on the 3D model.'}
          </p>
          {fetchError && (
            <p className="text-xs text-red-400/80 mt-1">
              Run: <code className="bg-white/8 px-1.5 py-0.5 rounded">py server.py</code> then click Refresh
            </p>
          )}
        </header>

        {/* 3D Brain + Controls */}
        <section className="liquid-glass flex flex-col gap-4 rounded-3xl border border-white/8 p-5 md:p-6">
          <p className="text-[11px] text-foreground/45">
            Arrows = educational mapping only. Pink highlight removed — use hemisphere toggle below if needed.
          </p>
          <div className="relative w-full">
            <BrainCanvas lesionSide={lesionSide} affectedZones={zones} />
            <BrainArrowOverlay analysis={analysis} />
          </div>

          <div className="flex flex-wrap gap-2">
            {([
              { value: null as LesionSide, label: 'None' },
              { value: 'left' as const, label: 'Lesion → left hemisphere' },
              { value: 'right' as const, label: 'Lesion → right hemisphere' },
            ] as const).map((opt) => (
              <button
                key={String(opt.value)}
                type="button"
                onClick={() => setLesionSide(opt.value)}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                  lesionSide === opt.value
                    ? 'border-sky-500/50 bg-sky-500/10 text-foreground'
                    : 'border-white/10 bg-white/4 text-foreground/70 hover:border-white/20'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {lesionSide && (
            <p className="text-xs leading-relaxed text-foreground/70">
              {lesionSummary(lesionSide, 'Patient scan')} Body side to watch:{' '}
              <span className="font-medium text-foreground">{contralateralBodySide(lesionSide)}</span>.
            </p>
          )}
        </section>

        {/* Stroke Analysis Results */}
        {hasStroke && analysis && (
          <div className="mt-8 space-y-6">
            {/* Stroke Type Header */}
            <div className="liquid-glass rounded-2xl border border-white/6 p-6">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-red-500/15 border border-red-500/20 flex items-center justify-center shrink-0">
                  <AlertTriangle className="w-6 h-6 text-red-400" />
                </div>
                <div className="flex-1">
                  <h2 className="text-xl font-bold text-gradient mb-1">
                    {analysis.stroke_type} Detected
                  </h2>
                  <p className="text-sm text-foreground/60 leading-relaxed">
                    {analysis.description}
                  </p>
                  <div className="mt-3 flex items-center gap-2">
                    <span className="text-xs px-2.5 py-1 rounded-full bg-red-500/10 border border-red-500/20 text-red-400">
                      Confidence: {(analysis.confidence * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Affected Brain Zones */}
            <div>
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2 text-foreground">
                <Target className="w-5 h-5 text-orange-400" />
                Affected Brain Zones
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {zones.map((zone, i) => (
                  <ZoneCard key={i} zone={zone} />
                ))}
              </div>
            </div>

            {/* Zone Legend */}
            <div className="liquid-glass rounded-xl border border-white/6 p-4">
              <p className="text-xs font-medium text-foreground/50 uppercase tracking-wider mb-3">Zone Color Legend</p>
              <div className="flex flex-wrap gap-3">
                {zones.map((zone, i) => (
                  <div key={i} className="flex items-center gap-1.5">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ background: REGION_COLORS[zone.region] }} />
                    <span className="text-xs text-foreground/60">{zone.zone.split('—')[0].split('(')[0].trim()}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Neuroplasticity Guidance */}
            <div className="liquid-glass rounded-2xl border border-white/6 p-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2 text-foreground">
                <Zap className="w-5 h-5 text-yellow-400" />
                Neuroplasticity Rehabilitation Targets
              </h3>
              <div className="space-y-3 mb-6">
                {analysis.neuroplasticity_targets.map((target, i) => (
                  <div key={i} className="flex items-start gap-3 text-sm">
                    <div className="w-6 h-6 rounded-lg bg-yellow-500/10 border border-yellow-500/20 flex items-center justify-center shrink-0 mt-0.5">
                      <span className="text-xs font-bold text-yellow-400">{i + 1}</span>
                    </div>
                    <span className="text-foreground/70">{target}</span>
                  </div>
                ))}
              </div>
              <div className="p-4 rounded-xl bg-green-500/5 border border-green-500/15">
                <p className="text-sm text-green-400 font-medium mb-1 flex items-center gap-2">
                  <Activity className="w-4 h-4" /> Recovery Potential
                </p>
                <p className="text-xs text-foreground/60 leading-relaxed">{analysis.recovery_potential}</p>
              </div>
            </div>

            {/* CTA */}
            <div className="flex justify-center">
              <Link
                to="/session"
                className="inline-flex items-center gap-2 px-8 py-3.5 rounded-xl font-semibold text-foreground transition-all hover:brightness-110 bg-linear-to-br from-sky-600 to-indigo-700"
              >
                <Brain className="w-5 h-5" />
                Start Rehabilitation Session
                <ArrowRight className="w-5 h-5" />
              </Link>
            </div>
          </div>
        )}

        {!hasStroke && !loading && (
          <div className="mt-8 text-center liquid-glass rounded-2xl border border-white/6 p-10">
            <Brain className="w-12 h-12 text-foreground/15 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-foreground/70 mb-2">No Stroke Analysis Available</h3>
            <p className="text-sm text-foreground/40 mb-6">
              Upload a brain scan first to see stroke effects highlighted on the 3D model.
            </p>
            <Link
              to="/scan"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-foreground border border-white/15 hover:border-white/30 transition-all"
            >
              Upload Brain Scan <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        )}

        <p className="mt-8 text-center text-[11px] text-foreground/40">
          Illustrative visualization. Not a medical diagnosis. Consult a healthcare professional for clinical decisions.
        </p>
      </div>
    </div>
  )
}
