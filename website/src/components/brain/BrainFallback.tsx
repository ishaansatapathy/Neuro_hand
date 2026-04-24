/* eslint-disable react-hooks/purity -- point cloud uses Monte Carlo sampling */
import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { Html } from '@react-three/drei'
import * as THREE from 'three'
import type { AffectedZone, BrainRegion } from '../../lib/brainRules'
import { REGION_POSITIONS, REGION_COLORS } from '../../lib/brainRules'

const REGION_DAMAGE_LABEL: Record<BrainRegion, string> = {
  frontal:   'Motor Cortex Damage',
  parietal:  'Sensory Cortex Damage',
  temporal:  'Language / Memory',
  occipital: 'Vision Area',
  deep:      'Clot / Hemorrhage',
  lateral:   'Ischemia Zone',
  brainstem: 'Vital Functions',
}

interface BrainFallbackProps {
  lesionSide: 'left' | 'right' | null
  affectedZones?: AffectedZone[]
}

function getRegionForPoint(x: number, y: number, z: number): BrainRegion {
  if (y > 0.12 && z > 0.12) return 'frontal'
  if (y > 0.18 && z < 0.12 && z > -0.15) return 'parietal'
  if (Math.abs(x) > 0.25 && y < 0.1) return 'temporal'
  if (z < -0.2 && y > 0.0) return 'occipital'
  if (Math.abs(x) < 0.15 && Math.abs(y) < 0.15 && Math.abs(z) < 0.15) return 'deep'
  if (y < -0.15) return 'brainstem'
  return 'lateral'
}

export function BrainFallbackPoints({ lesionSide, affectedZones = [] }: BrainFallbackProps) {
  const { geometry, regionMap } = useMemo(() => {
    const count = 6400
    const positions = new Float32Array(count * 3)
    const regions: BrainRegion[] = []

    for (let i = 0; i < count; i++) {
      const u = Math.random()
      const v = Math.random()
      const theta = 2 * Math.PI * u
      const phi = Math.acos(2 * v - 1)
      const r = 0.42 + Math.random() * 0.12
      const x = r * Math.sin(phi) * Math.cos(theta)
      const y = r * Math.sin(phi) * Math.sin(theta) * 0.72
      const z = r * Math.cos(phi) * 0.88
      positions[i * 3] = x
      positions[i * 3 + 1] = y
      positions[i * 3 + 2] = z
      regions.push(getRegionForPoint(x, y, z))
    }
    const geom = new THREE.BufferGeometry()
    geom.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    return { geometry: geom, regionMap: regions }
  }, [])

  const zoneRegions = useMemo(() => {
    const map = new Map<BrainRegion, number>()
    for (const z of affectedZones) {
      const existing = map.get(z.region) ?? 0
      map.set(z.region, Math.max(existing, z.severity))
    }
    return map
  }, [affectedZones])

  const geomRef = useRef<THREE.BufferGeometry>(null)

  const initGeom = useMemo(() => {
    const g = geometry.clone()
    const c = new Float32Array(regionMap.length * 3)
    for (let i = 0; i < regionMap.length; i++) {
      c[i * 3] = 0.39
      c[i * 3 + 1] = 0.45
      c[i * 3 + 2] = 0.55
    }
    g.setAttribute('color', new THREE.BufferAttribute(c, 3))
    return g
  }, [geometry, regionMap])

  useFrame(({ clock }) => {
    const geom = geomRef.current
    if (!geom?.attributes.color) return

    const pulse = Math.sin(clock.getElapsedTime() * 2.0) * 0.15 + 0.85
    const c = geom.attributes.color.array as Float32Array
    const count = regionMap.length
    const hasZones = zoneRegions.size > 0
    const showLeftLesion = lesionSide === 'left'
    const showRightLesion = lesionSide === 'right'
    const positions = geometry.attributes.position.array as Float32Array

    for (let i = 0; i < count; i++) {
      const region = regionMap[i]
      const x = positions[i * 3]
      const isLeft = x < 0
      const zoneSeverity = zoneRegions.get(region)

      if (hasZones && zoneSeverity !== undefined) {
        const color = new THREE.Color(REGION_COLORS[region])
        const intensity = zoneSeverity * pulse
        c[i * 3] = color.r * intensity + 0.15
        c[i * 3 + 1] = color.g * intensity * 0.5
        c[i * 3 + 2] = color.b * intensity * 0.3
      } else if (lesionSide !== null) {
        const lesion = showLeftLesion ? isLeft : showRightLesion ? !isLeft : false
        if (lesion) {
          /* muted amber — avoid pink */
          c[i * 3] = 0.92 * pulse
          c[i * 3 + 1] = 0.58 * pulse
          c[i * 3 + 2] = 0.28 * pulse
        } else {
          c[i * 3] = 0.39
          c[i * 3 + 1] = 0.45
          c[i * 3 + 2] = 0.55
        }
      } else {
        c[i * 3] = 0.39
        c[i * 3 + 1] = 0.45
        c[i * 3 + 2] = 0.55
      }
    }

    geom.attributes.color.needsUpdate = true
  })

  return (
    <points
      ref={(mesh) => {
        if (mesh) geomRef.current = mesh.geometry as THREE.BufferGeometry
      }}
      geometry={initGeom as THREE.BufferGeometry}
    >
      <pointsMaterial
        vertexColors
        size={0.02}
        sizeAttenuation
        transparent
        opacity={0.95}
        depthWrite={false}
      />
    </points>
  )
}

export function StrokeZoneMarkers({ affectedZones }: { affectedZones: AffectedZone[] }) {
  const groupRef = useRef<THREE.Group>(null)

  useFrame(({ clock }) => {
    if (!groupRef.current) return
    const t = clock.getElapsedTime()
    groupRef.current.children.forEach((child, i) => {
      const scale = 1.0 + Math.sin(t * 1.5 + i * 0.7) * 0.15
      child.scale.setScalar(scale)
    })
  })

  if (!affectedZones.length) return null

  return (
    <group ref={groupRef}>
      {affectedZones.map((zone, i) => {
        const pos = REGION_POSITIONS[zone.region] || [0, 0, 0]
        const color = REGION_COLORS[zone.region] || '#ffffff'
        const size = 0.04 + zone.severity * 0.06
        const labelOffset: [number, number, number] = [pos[0] + 0.08, pos[1] + 0.08, pos[2]]

        return (
          <group key={i}>
            <mesh position={pos as [number, number, number]}>
              <sphereGeometry args={[size, 16, 16]} />
              <meshStandardMaterial
                color={color}
                emissive={color}
                emissiveIntensity={0.25}
                transparent
                opacity={0.45 + zone.severity * 0.2}
              />
            </mesh>
            <Html position={labelOffset} center distanceFactor={3} zIndexRange={[0, 10]}>
              <div
                style={{
                  background: 'rgba(15, 23, 42, 0.88)',
                  border: '1px solid rgba(56, 189, 248, 0.35)',
                  borderRadius: '6px',
                  padding: '4px 8px',
                  pointerEvents: 'none',
                  minWidth: '110px',
                }}
              >
                <div
                  style={{
                    color: 'rgb(56 189 248)',
                    fontSize: '9px',
                    fontWeight: 700,
                    letterSpacing: '0.06em',
                    textTransform: 'uppercase',
                    marginBottom: '1px',
                  }}
                >
                  {REGION_DAMAGE_LABEL[zone.region]}
                </div>
                <div style={{ color: 'rgba(255,255,255,0.78)', fontSize: '10px', lineHeight: 1.3 }}>
                  {zone.zone.split('—')[0].split('(')[0].trim()}
                </div>
                <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: '9px', marginTop: '2px' }}>
                  Severity: {(zone.severity * 100).toFixed(0)}%
                </div>
              </div>
            </Html>
          </group>
        )
      })}
    </group>
  )
}
