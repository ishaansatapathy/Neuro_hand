import { Suspense } from 'react'
import * as THREE from 'three'
import { Canvas } from '@react-three/fiber'
import { Environment, OrbitControls } from '@react-three/drei'
import { BrainScene } from './BrainScene'
import type { LesionSide, AffectedZone } from '../../lib/brainRules'

interface BrainCanvasProps {
  lesionSide: LesionSide
  affectedZones?: AffectedZone[]
  compact?: boolean
}

export function BrainCanvas({ lesionSide, affectedZones = [], compact = false }: BrainCanvasProps) {
  return (
    <div className={`relative w-full overflow-hidden rounded-xl border border-white/10 bg-[#eceae8] ${
      compact ? 'h-[240px] min-h-[200px]' : 'h-[min(360px,45vh)] min-h-[280px]'
    }`}>
      <Canvas
        camera={{ position: [0, 0, 1.35], fov: 50 }}
        gl={{ antialias: true, alpha: false, powerPreference: 'high-performance' }}
        dpr={[1, 2]}
        shadows="soft"
        onCreated={({ gl }) => {
          gl.toneMapping = THREE.ACESFilmicToneMapping
          gl.toneMappingExposure = 1.05
          gl.outputColorSpace = THREE.SRGBColorSpace
        }}
      >
        <color attach="background" args={['#eceae8']} />
        <ambientLight intensity={0.28} />
        <directionalLight position={[4.5, 6, 5]} intensity={0.85} castShadow />
        <directionalLight position={[-3.5, -2, -4]} intensity={0.22} color="#b8c5e0" />
        <Suspense fallback={null}>
          <Environment preset="studio" environmentIntensity={0.92} />
        </Suspense>
        <BrainScene lesionSide={lesionSide} affectedZones={affectedZones} />
        <OrbitControls
          enablePan
          minDistance={0.08}
          maxDistance={4}
          enableDamping
          dampingFactor={0.08}
          makeDefault
        />
      </Canvas>
    </div>
  )
}
