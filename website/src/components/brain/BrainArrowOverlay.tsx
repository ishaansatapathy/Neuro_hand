/**
 * Illustrative arrow callouts on top of the brain viewport (not medical imaging).
 * Positions in viewBox 0–100 so arrows scale with container.
 */
import type { StrokeAnalysis } from '../../lib/brainRules'

type Calout = { lx: number; ly: number; ax: number; ay: number; title: string; sub: string }

function caloutsForAnalysis(a: StrokeAnalysis | null): Calout[] {
  const st = (a?.stroke_type ?? '').toLowerCase()
  if (st.includes('hemorrhagic')) {
    return [
      { lx: 8, ly: 10, ax: 38, ay: 42, title: 'गहरा ज़ोन — clot / bleed', sub: 'Deep structures (illustrative)' },
      { lx: 62, ly: 14, ax: 52, ay: 38, title: 'दबाव / swelling', sub: 'Adjacent tissue' },
      { lx: 12, ly: 72, ax: 35, ay: 58, title: 'Neuron stress zone', sub: 'Damaged pathways (edu only)' },
    ]
  }
  if (st.includes('ischemic')) {
    return [
      { lx: 6, ly: 12, ax: 40, ay: 36, title: 'रक्त बहाव कम — ischemia', sub: 'Clot blocks vessel (illustrative)' },
      { lx: 58, ly: 8, ax: 48, ay: 32, title: 'Motor cortex side', sub: 'Possible weakness side' },
      { lx: 70, ly: 70, ax: 55, ay: 52, title: 'Neuron injury', sub: 'Oxygen loss region' },
    ]
  }
  return [
    { lx: 10, ly: 12, ax: 42, ay: 38, title: 'Possible clot zone', sub: 'Educational overlay' },
    { lx: 65, ly: 16, ax: 52, ay: 40, title: 'Cortex / neurons', sub: 'Illustrative mapping' },
  ]
}

export function BrainArrowOverlay({ analysis }: { analysis: StrokeAnalysis | null }) {
  const items = caloutsForAnalysis(analysis)

  return (
    <div className="pointer-events-none absolute inset-0 z-10 overflow-hidden rounded-xl">
      <svg className="h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
        <defs>
          <marker id="brain-arrow" markerWidth="4" markerHeight="4" refX="3" refY="2" orient="auto">
            <polygon points="0 0, 4 2, 0 4" fill="rgb(56 189 248 / 0.95)" />
          </marker>
        </defs>
        {items.map((c, i) => (
          <line
            key={i}
            x1={c.lx}
            y1={c.ly + 5}
            x2={c.ax}
            y2={c.ay}
            stroke="rgb(56 189 248 / 0.55)"
            strokeWidth={0.35}
            markerEnd="url(#brain-arrow)"
            vectorEffect="non-scaling-stroke"
          />
        ))}
      </svg>

      {items.map((c, i) => (
        <div
          key={i}
          className="absolute max-w-[min(150px,42%)] rounded-md border border-sky-500/35 bg-zinc-950/80 px-2 py-1.5 text-[10px] leading-tight text-zinc-100 shadow-md backdrop-blur-sm"
          style={{ left: `${c.lx}%`, top: `${c.ly}%`, transform: 'translate(0, 0)' }}
        >
          <span className="font-semibold text-sky-300">{c.title}</span>
          <p className="mt-0.5 text-[9px] text-zinc-400">{c.sub}</p>
        </div>
      ))}
    </div>
  )
}
