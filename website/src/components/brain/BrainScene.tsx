import { Suspense, Component, type ErrorInfo, type ReactNode } from 'react'
import { Bounds, Center, Html } from '@react-three/drei'
import { BrainModel, GLB_PATH } from './BrainModel'
import { BrainFallbackPoints, StrokeZoneMarkers } from './BrainFallback'
import { useGlbAvailable } from './glbPresence'
import type { LesionSide, AffectedZone } from '../../lib/brainRules'

interface SceneProps {
  lesionSide: LesionSide
  affectedZones?: AffectedZone[]
}

function SceneLoading() {
  return (
    <Html center>
      <div className="rounded-lg border border-white/15 bg-black/70 px-3 py-2 text-xs text-white/80 backdrop-blur-sm">
        Loading GLB…
      </div>
    </Html>
  )
}

function FramedFallback({ lesionSide, affectedZones = [], showHtml }: SceneProps & { showHtml?: boolean }) {
  return (
    <Bounds fit clip margin={1.35} observe>
      <Center>
        <BrainFallbackPoints lesionSide={lesionSide} affectedZones={affectedZones} />
        <StrokeZoneMarkers affectedZones={affectedZones} />
      </Center>
      {showHtml ? <SceneLoading /> : null}
    </Bounds>
  )
}

type BoundaryProps = { children: ReactNode; lesionSide: LesionSide; affectedZones?: AffectedZone[] }
type BoundaryState = { err: Error | null }

class BrainErrorBoundary extends Component<BoundaryProps, BoundaryState> {
  state: BoundaryState = { err: null }

  static getDerivedStateFromError(err: Error): BoundaryState {
    return { err }
  }

  componentDidCatch(err: Error, info: ErrorInfo) {
    console.warn('[BrainScene] GLB render failed, using fallback:', err?.message, info)
  }

  render() {
    if (this.state.err) {
      return <FramedFallback lesionSide={this.props.lesionSide} affectedZones={this.props.affectedZones} />
    }
    return this.props.children
  }
}

function BrainSceneLoaded({ lesionSide, affectedZones = [] }: SceneProps) {
  return (
    <BrainErrorBoundary lesionSide={lesionSide} affectedZones={affectedZones}>
      <Suspense fallback={<FramedFallback lesionSide={lesionSide} affectedZones={affectedZones} showHtml />}>
        <Bounds fit clip margin={1.35} observe>
          <Center>
            <BrainModel lesionSide={lesionSide} />
            <StrokeZoneMarkers affectedZones={affectedZones} />
          </Center>
        </Bounds>
      </Suspense>
    </BrainErrorBoundary>
  )
}

export function BrainScene({ lesionSide, affectedZones = [] }: SceneProps) {
  const glb = useGlbAvailable(GLB_PATH)

  if (glb === 'checking') {
    return <FramedFallback lesionSide={lesionSide} affectedZones={affectedZones} showHtml />
  }

  if (glb === 'no') {
    return <FramedFallback lesionSide={lesionSide} affectedZones={affectedZones} />
  }

  return <BrainSceneLoaded lesionSide={lesionSide} affectedZones={affectedZones} />
}
