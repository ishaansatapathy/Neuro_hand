/* Procedural layout: Math.random in useMemo is intentional. */
/* eslint-disable react-hooks/purity -- sphere/graph geometry sampling */
import { useRef, useMemo } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { Float, OrbitControls, Line } from '@react-three/drei'
import * as THREE from 'three'

/* ── Animated Neural-Network Sphere ── */
function NeuralNodes({ count = 120 }: { count?: number }) {
  const meshRef = useRef<THREE.InstancedMesh>(null!)
  const dummy = useMemo(() => new THREE.Object3D(), [])

  const nodes = useMemo(() => {
    const arr: { pos: THREE.Vector3; speed: number; phase: number }[] = []
    for (let i = 0; i < count; i++) {
      // distribute on a sphere surface
      const phi = Math.acos(2 * Math.random() - 1)
      const theta = Math.random() * Math.PI * 2
      const r = 1.8 + Math.random() * 0.6
      arr.push({
        pos: new THREE.Vector3(
          r * Math.sin(phi) * Math.cos(theta),
          r * Math.sin(phi) * Math.sin(theta),
          r * Math.cos(phi)
        ),
        speed: 0.3 + Math.random() * 0.7,
        phase: Math.random() * Math.PI * 2,
      })
    }
    return arr
  }, [count])

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    nodes.forEach((node, i) => {
      const s = 0.02 + 0.015 * Math.sin(t * node.speed + node.phase)
      dummy.position.copy(node.pos)
      dummy.position.y += Math.sin(t * 0.5 + node.phase) * 0.08
      dummy.scale.setScalar(s)
      dummy.updateMatrix()
      meshRef.current.setMatrixAt(i, dummy.matrix)
    })
    meshRef.current.instanceMatrix.needsUpdate = true
  })

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, count]}>
      <sphereGeometry args={[1, 8, 8]} />
      <meshBasicMaterial color="#a78bfa" transparent opacity={0.9} />
    </instancedMesh>
  )
}

/* ── Glowing connections ── */
function Connections({ count = 60 }: { count?: number }) {
  const linesRef = useRef<THREE.Group>(null!)

  const lines = useMemo(() => {
    const arr: { points: THREE.Vector3[]; color: string }[] = []
    const colors = ['#818cf8', '#c084fc', '#f0abfc', '#22d3ee', '#60a5fa']
    for (let i = 0; i < count; i++) {
      const phi1 = Math.acos(2 * Math.random() - 1)
      const theta1 = Math.random() * Math.PI * 2
      const r1 = 1.8 + Math.random() * 0.5
      const phi2 = phi1 + (Math.random() - 0.5) * 0.8
      const theta2 = theta1 + (Math.random() - 0.5) * 0.8
      const r2 = 1.8 + Math.random() * 0.5
      arr.push({
        points: [
          new THREE.Vector3(r1 * Math.sin(phi1) * Math.cos(theta1), r1 * Math.sin(phi1) * Math.sin(theta1), r1 * Math.cos(phi1)),
          new THREE.Vector3(r2 * Math.sin(phi2) * Math.cos(theta2), r2 * Math.sin(phi2) * Math.sin(theta2), r2 * Math.cos(phi2)),
        ],
        color: colors[Math.floor(Math.random() * colors.length)],
      })
    }
    return arr
  }, [count])

  useFrame(({ clock }) => {
    if (linesRef.current) {
      linesRef.current.rotation.y = clock.getElapsedTime() * 0.05
      linesRef.current.rotation.x = Math.sin(clock.getElapsedTime() * 0.03) * 0.1
    }
  })

  return (
    <group ref={linesRef}>
      {lines.map((seg, i) => (
        <Line
          key={i}
          points={seg.points}
          color={seg.color}
          lineWidth={1}
          transparent
          opacity={0.15}
        />
      ))}
    </group>
  )
}

/* ── Core sphere with glow ── */
function CoreSphere() {
  const ref = useRef<THREE.Mesh>(null!)

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    ref.current.scale.setScalar(1 + Math.sin(t * 0.8) * 0.05)
  })

  return (
    <Float speed={1.5} rotationIntensity={0.3} floatIntensity={0.5}>
      <mesh ref={ref}>
        <sphereGeometry args={[1.2, 32, 32]} />
        <meshBasicMaterial color="#1e1b4b" transparent opacity={0.3} wireframe />
      </mesh>
      <mesh>
        <sphereGeometry args={[0.6, 16, 16]} />
        <meshBasicMaterial color="#6366f1" transparent opacity={0.15} />
      </mesh>
    </Float>
  )
}

/* ── Outer ring ── */
function OrbitalRing() {
  const ref = useRef<THREE.Mesh>(null!)
  useFrame(({ clock }) => {
    ref.current.rotation.z = clock.getElapsedTime() * 0.15
    ref.current.rotation.x = 1.2
  })
  return (
    <mesh ref={ref}>
      <torusGeometry args={[2.8, 0.008, 16, 100]} />
      <meshBasicMaterial color="#a78bfa" transparent opacity={0.25} />
    </mesh>
  )
}

export default function NeuralNetwork3D() {
  return (
    <div className="absolute inset-0 z-0" style={{ pointerEvents: 'none' }}>
      <Canvas
        camera={{ position: [0, 0, 6], fov: 45 }}
        style={{ pointerEvents: 'auto' }}
        gl={{ antialias: true, alpha: true }}
      >
        <ambientLight intensity={0.5} />
        <pointLight position={[5, 5, 5]} intensity={0.3} color="#a78bfa" />
        <pointLight position={[-5, -5, 5]} intensity={0.2} color="#f472b6" />

        <group>
          <CoreSphere />
          <NeuralNodes count={100} />
          <Connections count={50} />
          <OrbitalRing />
        </group>

        <OrbitControls
          enableZoom={false}
          enablePan={false}
          autoRotate
          autoRotateSpeed={0.4}
          maxPolarAngle={Math.PI / 1.5}
          minPolarAngle={Math.PI / 3}
        />
      </Canvas>
    </div>
  )
}
