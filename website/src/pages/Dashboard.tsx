import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  Activity,
  Trophy,
  Star,
  TrendingUp,
  Clock,
  ChevronDown,
  ChevronUp,
  Dumbbell,
  Play,
  Brain,
  AlertTriangle,
  Zap,
  Target,
  ArrowRight,
  type LucideIcon,
} from 'lucide-react'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  ReferenceLine,
  Cell,
} from 'recharts'
import { getSessions, getLatestScanAnalysis } from '../lib/api'
import { BrainCanvas } from '../components/brain/BrainCanvas'
import { REGION_COLORS, type StrokeAnalysis, type AffectedZone } from '../lib/brainRules'

interface SessionData {
  id: string
  date: string
  duration_minutes: number
  score: number
  exercises: string[]
  avg_match: number
  status: string
  difficulty?: string
  affected_hand?: string
}

function StatCard({ icon: Icon, label, value, color }: {
  icon: LucideIcon
  label: string
  value: string | number
  color: string
}) {
  return (
    <div className="liquid-glass rounded-2xl p-5 card-spotlight">
      <div className="flex items-center gap-3 mb-3">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color}`}>
          <Icon className="w-5 h-5" />
        </div>
        <span className="text-sm text-gray-400">{label}</span>
      </div>
      <p className="text-3xl font-bold text-gradient">{value}</p>
    </div>
  )
}

function CustomTooltip({ active, payload, label }: {
  active?: boolean
  payload?: Array<{ name?: string; value?: number; color?: string; dataKey?: string }>
  label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="liquid-glass rounded-xl px-4 py-3 text-sm border border-white/10 shadow-lg min-w-[140px]">
      <p className="text-foreground/50 text-xs uppercase tracking-wider mb-2">Session {label}</p>
      {payload.map((p, i) => {
        const isPct = String(p.dataKey) === 'match' || String(p.name).includes('Match')
        const val = typeof p.value === 'number' ? p.value : 0
        return (
          <p key={i} style={{ color: p.color }} className="font-semibold tabular-nums flex justify-between gap-4">
            <span className="text-foreground/70 font-normal">{p.name}</span>
            <span>
              {val}
              {isPct ? '%' : ''}
            </span>
          </p>
        )
      })}
    </div>
  )
}

const cursorStyle = { stroke: 'rgba(96, 165, 250, 0.35)', strokeWidth: 1, strokeDasharray: '4 4' }

function SessionRow({ session }: { session: SessionData }) {
  const [expanded, setExpanded] = useState(false)

  const statusColor = session.status === 'completed'
    ? 'bg-green-500/20 text-green-400 border-green-500/30'
    : session.status === 'active'
    ? 'bg-blue-500/20 text-blue-400 border-blue-500/30'
    : 'bg-gray-500/20 text-gray-400 border-gray-500/30'

  return (
    <div className="liquid-glass rounded-xl overflow-hidden transition-all duration-300">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-5 py-4 flex items-center gap-4 text-left hover:bg-white/5 transition-colors"
      >
        <div className="w-10 h-10 rounded-xl bg-blue-600/15 flex items-center justify-center shrink-0">
          <Dumbbell className="w-5 h-5 text-blue-400" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-medium text-foreground truncate">
            {session.exercises?.map(e => e.replace('_', ' ')).join(', ') || 'Session'}
          </p>
          <p className="text-sm text-gray-500">
            {new Date(session.date).toLocaleDateString('en-US', {
              month: 'short', day: 'numeric', year: 'numeric',
              hour: '2-digit', minute: '2-digit',
            })}
          </p>
        </div>
        <div className="text-right shrink-0 hidden sm:block">
          <p className="font-semibold text-foreground">{session.score} pts</p>
          <p className="text-sm text-gray-500">{session.duration_minutes} min</p>
        </div>
        <span className={`text-xs px-2.5 py-1 rounded-full border capitalize shrink-0 ${statusColor}`}>
          {session.status}
        </span>
        {expanded
          ? <ChevronUp className="w-4 h-4 text-gray-500 shrink-0" />
          : <ChevronDown className="w-4 h-4 text-gray-500 shrink-0" />
        }
      </button>

      {expanded && (
        <div className="px-5 pb-4 pt-0 border-t border-white/5">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3">
            <div>
              <p className="text-xs text-gray-500">Duration</p>
              <p className="text-sm font-medium text-foreground">{session.duration_minutes} min</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Score</p>
              <p className="text-sm font-medium text-blue-400">{session.score}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Avg Match</p>
              <p className="text-sm font-medium text-purple-400">{session.avg_match}%</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Difficulty</p>
              <p className="text-sm font-medium text-yellow-400 capitalize">{session.difficulty || '—'}</p>
            </div>
          </div>
          <div className="mt-3">
            <p className="text-xs text-gray-500 mb-1">Exercises</p>
            <div className="flex gap-2 flex-wrap">
              {session.exercises?.map(ex => (
                <span key={ex} className="text-xs bg-white/5 border border-white/10 px-2.5 py-1 rounded-lg text-gray-300 capitalize">
                  {ex.replace('_', ' ')}
                </span>
              ))}
            </div>
          </div>
          {session.affected_hand && (
            <div className="mt-2">
              <p className="text-xs text-gray-500">Affected Hand</p>
              <p className="text-sm font-medium text-gray-300 capitalize">{session.affected_hand}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function StrokeZoneMini({ zone }: { zone: AffectedZone }) {
  const color = REGION_COLORS[zone.region] || '#888'
  return (
    <div className="rounded-xl bg-white/3 border border-white/5 p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
          <span className="text-xs font-semibold text-foreground">{zone.zone}</span>
        </div>
        <span className="text-[10px] px-2 py-0.5 rounded-full" style={{
          background: color + '15', border: `1px solid ${color}30`, color,
        }}>
          {(zone.severity * 100).toFixed(0)}%
        </span>
      </div>
      <div className="h-1 rounded-full bg-white/5 overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700" style={{
          width: `${zone.severity * 100}%`, background: color,
        }} />
      </div>
      <div className="flex flex-wrap gap-1">
        {zone.effects.slice(0, 2).map((e, i) => (
          <span key={i} className="text-[10px] text-foreground/50">{i > 0 && '•'} {e}</span>
        ))}
        {zone.effects.length > 2 && (
          <span className="text-[10px] text-foreground/30">+{zone.effects.length - 2} more</span>
        )}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [sessions, setSessions] = useState<SessionData[]>([])
  const [loading, setLoading] = useState(true)
  const [scanAnalysis, setScanAnalysis] = useState<StrokeAnalysis | null>(null)
  const [scanLoading, setScanLoading] = useState(true)

  useEffect(() => {
    getSessions()
      .then(data => {
        const list = Array.isArray(data) ? data : data.sessions ?? []
        setSessions(list)
      })
      .catch(() => setSessions([]))
      .finally(() => setLoading(false))

    getLatestScanAnalysis()
      .then(data => {
        if (data.has_scan && data.stroke_analysis) {
          setScanAnalysis(data.stroke_analysis)
        }
      })
      .catch(() => {})
      .finally(() => setScanLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="min-h-screen bg-background text-foreground flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-white/20 border-t-blue-400 rounded-full animate-spin" />
      </div>
    )
  }

  if (sessions.length === 0) {
    return (
      <div className="min-h-screen bg-background text-foreground flex items-center justify-center px-4">
        <div className="text-center max-w-md">
          <div className="w-20 h-20 mx-auto rounded-full bg-blue-600/15 border border-blue-500/20 flex items-center justify-center mb-6">
            <Activity className="w-10 h-10 text-blue-400" />
          </div>
          <h1 className="text-3xl font-bold text-gradient mb-3">No Sessions Yet</h1>
          <p className="text-gray-400 mb-8">
            Complete your first rehabilitation session to start tracking your progress.
          </p>
          <a
            href="/session"
            className="inline-flex items-center gap-2 px-8 py-3 rounded-xl font-semibold gradient-border bg-blue-600/20 hover:bg-blue-600/30 transition-all text-foreground"
          >
            <Play className="w-5 h-5" /> Start Your First Session
          </a>
        </div>
      </div>
    )
  }

  const totalSessions = sessions.length
  const totalScore = sessions.reduce((s, x) => s + (x.score || 0), 0)
  const bestScore = Math.max(...sessions.map(s => s.score || 0))
  const avgMatch = Math.round(sessions.reduce((s, x) => s + (x.avg_match || 0), 0) / totalSessions)

  const chartData = sessions.map((s, i) => ({
    name: `#${i + 1}`,
    score: s.score || 0,
    match: s.avg_match || 0,
  }))

  const avgScoreLine = totalSessions > 0 ? totalScore / totalSessions : 0

  return (
    <div className="min-h-screen bg-background text-foreground px-4 py-20">
      <div className="max-w-6xl mx-auto space-y-8">
        <div>
          <h1 className="text-4xl font-bold text-gradient mb-2">Dashboard</h1>
          <p className="text-gray-400">Track your rehabilitation progress</p>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard icon={Activity} label="Total Sessions" value={totalSessions} color="bg-blue-600/20 text-blue-400" />
          <StatCard icon={Trophy} label="Total Score" value={totalScore} color="bg-purple-600/20 text-purple-400" />
          <StatCard icon={Star} label="Best Score" value={bestScore} color="bg-yellow-600/20 text-yellow-400" />
          <StatCard icon={TrendingUp} label="Avg Match %" value={`${avgMatch}%`} color="bg-green-600/20 text-green-400" />
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Score Line Chart */}
          <div className="liquid-glass rounded-2xl p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-blue-400" /> Score Over Sessions
            </h2>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart
                data={chartData}
                margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
                syncId="rehabDash"
              >
                <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                <XAxis dataKey="name" stroke="#555" tick={{ fill: '#888', fontSize: 11 }} tickLine={false} />
                <YAxis stroke="#555" tick={{ fill: '#888', fontSize: 11 }} tickLine={false} domain={[0, 'auto']} />
                <Tooltip content={<CustomTooltip />} cursor={cursorStyle} />
                <Legend
                  wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
                  formatter={v => <span className="text-foreground/70">{v}</span>}
                />
                {avgScoreLine > 0 && (
                  <ReferenceLine
                    y={avgScoreLine}
                    stroke="rgba(96, 165, 250, 0.35)"
                    strokeDasharray="5 5"
                    label={{ value: 'Avg', position: 'right', fill: '#64748b', fontSize: 11 }}
                  />
                )}
                <Line
                  type="monotone"
                  dataKey="score"
                  name="Score"
                  stroke="#60a5fa"
                  strokeWidth={2.5}
                  dot={{ fill: '#60a5fa', r: 4, stroke: '#0f172a', strokeWidth: 1 }}
                  activeDot={{ r: 8, fill: '#93c5fd', stroke: '#fff', strokeWidth: 2 }}
                  isAnimationActive
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Match Bar Chart */}
          <div className="liquid-glass rounded-2xl p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5 text-purple-400" /> Match % Per Session
            </h2>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart
                data={chartData}
                margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
                syncId="rehabDash"
              >
                <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                <XAxis dataKey="name" stroke="#555" tick={{ fill: '#888', fontSize: 11 }} tickLine={false} />
                <YAxis stroke="#555" tick={{ fill: '#888', fontSize: 11 }} tickLine={false} domain={[0, 100]} />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(167, 139, 250, 0.12)' }} />
                <Legend
                  wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
                  formatter={v => <span className="text-foreground/70">{v}</span>}
                />
                {avgMatch > 0 && (
                  <ReferenceLine
                    y={avgMatch}
                    stroke="rgba(167, 139, 250, 0.4)"
                    strokeDasharray="5 5"
                    label={{ value: 'Avg', position: 'right', fill: '#64748b', fontSize: 11 }}
                  />
                )}
                <Bar
                  dataKey="match"
                  name="Match %"
                  fill="#a78bfa"
                  radius={[6, 6, 0, 0]}
                  maxBarSize={44}
                  isAnimationActive
                  activeBar={{ fill: '#c4b5fd', stroke: '#e9d5ff', strokeWidth: 1 }} 
                >
                  {chartData.map((_, i) => (
                    <Cell key={i} fill={i % 2 === 0 ? '#a78bfa' : '#8b5cf6'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Brain Scan Analysis */}
        {!scanLoading && scanAnalysis && scanAnalysis.stroke_type !== 'None' && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <Brain className="w-5 h-5 text-red-400" /> Brain Scan Analysis
            </h2>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* 3D Brain View */}
              <div className="liquid-glass rounded-2xl p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-red-400" />
                      {scanAnalysis.stroke_type} Detected
                    </h3>
                    <p className="text-xs text-foreground/50 mt-1">
                      {(scanAnalysis.confidence * 100).toFixed(1)}% confidence
                    </p>
                  </div>
                  <Link to="/brain" className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1">
                    Full View <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>

                <BrainCanvas
                  lesionSide="left"
                  affectedZones={scanAnalysis.affected_zones}
                  compact
                />

                <p className="text-xs text-foreground/40 leading-relaxed">
                  {scanAnalysis.description}
                </p>

                {/* Zone Legend */}
                <div className="flex flex-wrap gap-2">
                  {scanAnalysis.affected_zones.map((zone, i) => (
                    <div key={i} className="flex items-center gap-1.5">
                      <div className="w-2 h-2 rounded-full" style={{ background: REGION_COLORS[zone.region] }} />
                      <span className="text-[10px] text-foreground/50">
                        {zone.zone.split('—')[0].split('(')[0].trim()}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Affected Zones + Neuroplasticity */}
              <div className="space-y-4">
                {/* Affected Zones */}
                <div className="liquid-glass rounded-2xl p-5">
                  <h3 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
                    <Target className="w-4 h-4 text-orange-400" />
                    Affected Brain Zones
                  </h3>
                  <div className="space-y-2">
                    {scanAnalysis.affected_zones.map((zone, i) => (
                      <StrokeZoneMini key={i} zone={zone} />
                    ))}
                  </div>
                </div>

                {/* Neuroplasticity Targets */}
                <div className="liquid-glass rounded-2xl p-5">
                  <h3 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
                    <Zap className="w-4 h-4 text-yellow-400" />
                    Neuroplasticity Targets
                  </h3>
                  <div className="space-y-2">
                    {scanAnalysis.neuroplasticity_targets.slice(0, 3).map((target, i) => (
                      <div key={i} className="flex items-start gap-2 text-xs">
                        <div className="w-5 h-5 rounded bg-yellow-500/10 border border-yellow-500/20 flex items-center justify-center shrink-0 mt-0.5">
                          <span className="text-[10px] font-bold text-yellow-400">{i + 1}</span>
                        </div>
                        <span className="text-foreground/60 leading-relaxed">{target}</span>
                      </div>
                    ))}
                  </div>
                  <div className="mt-3 p-2.5 rounded-lg bg-green-500/5 border border-green-500/15">
                    <p className="text-[10px] text-green-400 font-medium mb-0.5">Recovery Potential</p>
                    <p className="text-[10px] text-foreground/50 leading-relaxed">
                      {scanAnalysis.recovery_potential}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {!scanLoading && !scanAnalysis && (
          <div className="liquid-glass rounded-2xl p-6 text-center">
            <Brain className="w-10 h-10 text-foreground/10 mx-auto mb-3" />
            <p className="text-foreground/40 text-sm mb-1">No brain scan analysis available</p>
            <p className="text-foreground/25 text-xs mb-4">Upload a brain scan to see stroke effects and neuroplasticity guidance</p>
            <Link to="/scan" className="inline-flex items-center gap-2 text-xs text-blue-400 hover:text-blue-300">
              Upload Brain Scan <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
        )}

        {/* Recent Sessions */}
        <div>
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Clock className="w-5 h-5 text-cyan-400" /> Recent Sessions
          </h2>
          <div className="space-y-3">
            {sessions.slice().reverse().map(session => (
              <SessionRow key={session.id || session.date} session={session} />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
