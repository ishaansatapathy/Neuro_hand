import { useMemo } from 'react'
import * as THREE from 'three'
import { useGLTF } from '@react-three/drei'
import type { LesionSide } from '../../lib/brainRules'

export const GLB_PATH = '/human_brain_cerebrum__brainstem.glb'

/** Material name from Sketchfab / Blender export — adjust if your GLB differs. */
const MATERIAL_KEY = 'Hj__rna3_1'

function applyLesionTint(base: THREE.Material, lesionSide: LesionSide): THREE.Material {
  if (!lesionSide) return base
  const m = base.clone()
  const tint = lesionSide === 'left' ? new THREE.Color('#eab308') : new THREE.Color('#38bdf8')
  if (m instanceof THREE.MeshStandardMaterial || m instanceof THREE.MeshPhysicalMaterial) {
    m.emissive = tint
    m.emissiveIntensity = Math.max(m.emissiveIntensity ?? 0, 0.18)
    return m
  }
  if (m instanceof THREE.MeshLambertMaterial || m instanceof THREE.MeshPhongMaterial) {
    m.emissive = tint
    m.emissiveIntensity = 0.35
    return m
  }
  if (m instanceof THREE.MeshBasicMaterial) {
    m.color.lerp(tint, 0.55)
    return m
  }
  return m
}

export function BrainModel({ lesionSide }: { lesionSide: LesionSide }) {
  const { nodes, materials } = useGLTF(GLB_PATH)

  const meshNode = nodes.defaultMaterial as THREE.Mesh | undefined
  const baseMat = materials[MATERIAL_KEY] as THREE.Material | undefined

  const material = useMemo(() => {
    if (!baseMat) return new THREE.MeshStandardMaterial({ color: '#888888' })
    return applyLesionTint(baseMat, lesionSide)
  }, [baseMat, lesionSide])

  if (!meshNode?.geometry) {
    return null
  }

  return (
    <group dispose={null}>
      <group position={[-0.039, 0, 0.016]} rotation={[-Math.PI / 2, 0, -0.889]} scale={0.093}>
        <mesh
          castShadow
          receiveShadow
          geometry={meshNode.geometry}
          material={material}
          rotation={[Math.PI / 2, 0, 0]}
        />
      </group>
    </group>
  )
}

useGLTF.preload(GLB_PATH)
