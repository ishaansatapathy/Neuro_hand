"""
=============================================================================
 DOCTOR STRANGE MAGIC OVERLAY — Animated ring guidance for hand rehab
=============================================================================

 Draws mystical rotating rings, pulsing arcs, energy traces, and glowing
 halos around hand landmarks.  Fully real-time using only OpenCV primitives.

 Effects:
   - Mandala rings around wrist (multi-layer, counter-rotating)
   - Pulsing arc segments around fingertips
   - Energy lines connecting fingers to wrist
   - Glowing aura via Gaussian blur compositing
   - Rune tick marks along outer rings

 Colors:
   Incorrect / guidance:  orange-amber + electric blue
   Correct:               emerald green + soft gold

 Usage:
   from magic_overlay import MagicOverlay
   magic = MagicOverlay()
   frame = magic.draw(frame, hand_landmarks, severity="warning")
=============================================================================
"""
from __future__ import annotations

import math
import time
from typing import Any

import cv2
import numpy as np


# -- Colour palettes ---------------------------------------------------------

# Guidance mode (orange/blue — Doctor Strange portal feel)
GUIDE_ORANGE    = (50, 140, 255)    # warm amber-orange
GUIDE_GOLD      = (60, 200, 255)    # bright gold
GUIDE_BLUE      = (255, 180, 50)    # electric blue
GUIDE_CYAN      = (220, 220, 80)    # teal accent
GUIDE_DIM       = (30, 80, 140)     # dim orange for outer rings

# Correct mode (green/gold — success glow)
CORRECT_GREEN   = (80, 255, 120)
CORRECT_GOLD    = (80, 230, 200)
CORRECT_DIM     = (40, 120, 60)

# Severe mode (red/magenta — urgent)
SEVERE_RED      = (60, 60, 255)
SEVERE_MAGENTA  = (180, 50, 220)
SEVERE_DIM      = (40, 30, 120)


# -- Landmark groups ----------------------------------------------------------

WRIST = 0
FINGERTIPS = [4, 8, 12, 16, 20]        # thumb, index, middle, ring, pinky
FINGER_MCPS = [1, 5, 9, 13, 17]        # base joints
FINGER_PIPS = [2, 6, 10, 14, 18]       # mid joints


class MagicOverlay:
    """
    Animated 'Doctor Strange' style guidance overlay.

    Call .draw() once per frame.  Internally tracks animation state
    using wall-clock time — no external timer needed.
    """

    def __init__(self) -> None:
        self._start_time = time.time()

    # ------------------------------------------------------------------ API

    def draw(
        self,
        frame: np.ndarray,
        hand_landmarks: Any | None,
        severity: str = "neutral",
    ) -> np.ndarray:
        """
        Render the magic overlay onto the frame.

        Parameters
        ----------
        frame : BGR image (modified in-place AND returned)
        hand_landmarks : MediaPipe hand landmarks, or None
        severity : "correct" | "warning" | "error" | "neutral"
        """
        if hand_landmarks is None:
            return frame

        t = time.time() - self._start_time     # animation clock
        fh, fw = frame.shape[:2]
        lm = hand_landmarks.landmark

        # Pick colour palette
        if severity == "correct":
            c_pri, c_sec, c_dim, c_acc = CORRECT_GREEN, CORRECT_GOLD, CORRECT_DIM, CORRECT_GREEN
        elif severity == "error":
            c_pri, c_sec, c_dim, c_acc = SEVERE_RED, SEVERE_MAGENTA, SEVERE_DIM, SEVERE_RED
        else:
            c_pri, c_sec, c_dim, c_acc = GUIDE_ORANGE, GUIDE_BLUE, GUIDE_DIM, GUIDE_GOLD

        # Create glow layer (black = transparent after addWeighted)
        glow = np.zeros_like(frame)

        # Pixel positions for all 21 landmarks
        pts = [(int(lm[i].x * fw), int(lm[i].y * fh)) for i in range(21)]
        wx, wy = pts[WRIST]

        # ============ 1. WRIST MANDALA (multi-ring portal) ============
        self._draw_mandala(glow, wx, wy, t, c_pri, c_sec, c_dim, c_acc, severity)

        # ============ 2. FINGERTIP HALOS ============
        for i, tip_id in enumerate(FINGERTIPS):
            tx, ty = pts[tip_id]
            self._draw_fingertip_halo(glow, tx, ty, t, i, c_pri, c_sec, severity)

        # ============ 3. ENERGY LINES (wrist → fingertips) ============
        self._draw_energy_lines(glow, pts, t, c_dim, c_acc)

        # ============ 4. JOINT DOTS (small glowing circles) ============
        self._draw_joint_dots(glow, pts, t, c_pri)

        # ============ 5. COMPOSITE — blur glow + blend ============
        # Subtle mode: reduced intensity so it complements the Jarvis HUD
        glow_blurred = cv2.GaussianBlur(glow, (21, 21), 0)

        # Reduced additive blend (0.35 instead of full add)
        scaled_glow = (glow_blurred * 0.35).astype(np.uint8)
        frame = cv2.add(frame, scaled_glow)

        # Sharp detail overlay (reduced from 0.55 to 0.25)
        sharp_alpha = 0.25
        cv2.addWeighted(glow, sharp_alpha, frame, 1.0, 0, frame)

        return frame

    # ------------------------------------------------------------- FX layers

    def _draw_mandala(
        self, layer: np.ndarray,
        cx: int, cy: int, t: float,
        c_pri: tuple, c_sec: tuple, c_dim: tuple, c_acc: tuple,
        severity: str,
    ) -> None:
        """Multi-layer rotating rings around the wrist — the main portal."""

        # Pulse factor (breathing glow)
        pulse = 0.6 + 0.4 * math.sin(t * 3.0)

        # --- Ring 1: outer ring (slow clockwise) ---
        r1 = int(75 * pulse)
        angle1 = math.degrees(t * 0.8)
        self._draw_arc_ring(layer, cx, cy, r1, angle1, c_dim, thickness=1, segments=6, gap=25)

        # --- Ring 2: mid ring (counter-clockwise, faster) ---
        r2 = int(55 * pulse)
        angle2 = math.degrees(-t * 1.5)
        self._draw_arc_ring(layer, cx, cy, r2, angle2, c_pri, thickness=2, segments=4, gap=40)

        # --- Ring 3: inner ring (fast clockwise) ---
        r3 = int(35 * pulse)
        angle3 = math.degrees(t * 2.5)
        self._draw_arc_ring(layer, cx, cy, r3, angle3, c_sec, thickness=2, segments=3, gap=50)

        # --- Center dot (bright core) ---
        core_r = max(3, int(8 * pulse))
        cv2.circle(layer, (cx, cy), core_r, c_acc, -1)

        # --- Rune tick marks on Ring 1 ---
        num_ticks = 12
        for i in range(num_ticks):
            a = math.radians(angle1 + i * (360 / num_ticks))
            inner_r = r1 - 6
            outer_r = r1 + 6
            x1 = int(cx + inner_r * math.cos(a))
            y1 = int(cy + inner_r * math.sin(a))
            x2 = int(cx + outer_r * math.cos(a))
            y2 = int(cy + outer_r * math.sin(a))
            cv2.line(layer, (x1, y1), (x2, y2), c_dim, 1)

        # --- Rotating triangle inscribed in Ring 2 ---
        if severity != "correct":
            tri_angle = math.radians(angle2)
            tri_pts = []
            for k in range(3):
                a = tri_angle + k * (2 * math.pi / 3)
                x = int(cx + r2 * 0.7 * math.cos(a))
                y = int(cy + r2 * 0.7 * math.sin(a))
                tri_pts.append((x, y))
            for k in range(3):
                cv2.line(layer, tri_pts[k], tri_pts[(k + 1) % 3], c_sec, 1)

    def _draw_fingertip_halo(
        self, layer: np.ndarray,
        cx: int, cy: int, t: float, finger_idx: int,
        c_pri: tuple, c_sec: tuple, severity: str,
    ) -> None:
        """Pulsing arc halo around each fingertip."""
        # Each finger pulses at a slightly different phase
        phase = finger_idx * 0.7
        pulse = 0.5 + 0.5 * math.sin(t * 4.0 + phase)

        radius = int(12 + 8 * pulse)
        angle_offset = math.degrees(t * 2.0 + phase)

        # Two opposing arcs (like parentheses)
        cv2.ellipse(layer, (cx, cy), (radius, radius),
                    angle_offset, 0, 120, c_pri, 2)
        cv2.ellipse(layer, (cx, cy), (radius, radius),
                    angle_offset, 180, 300, c_sec, 2)

        # Center dot
        dot_r = max(2, int(4 * pulse))
        cv2.circle(layer, (cx, cy), dot_r, c_pri, -1)

        # Orbiting particle
        orbit_r = radius + 4
        pa = math.radians(angle_offset * 3)
        px = int(cx + orbit_r * math.cos(pa))
        py = int(cy + orbit_r * math.sin(pa))
        cv2.circle(layer, (px, py), 2, c_sec, -1)

    def _draw_energy_lines(
        self, layer: np.ndarray,
        pts: list[tuple[int, int]], t: float,
        c_dim: tuple, c_acc: tuple,
    ) -> None:
        """Animated energy traces from wrist to each fingertip."""
        wx, wy = pts[WRIST]

        for i, tip_id in enumerate(FINGERTIPS):
            tx, ty = pts[tip_id]

            # Draw dashed energy line
            dx = tx - wx
            dy = ty - wy
            length = math.sqrt(dx * dx + dy * dy)
            if length < 10:
                continue

            num_particles = 6
            for k in range(num_particles):
                # Animate particles along the line
                frac = ((k / num_particles) + t * 0.8 + i * 0.15) % 1.0
                px = int(wx + dx * frac)
                py = int(wy + dy * frac)

                # Particle size varies with position (bigger toward tip)
                size = max(1, int(3 * frac))
                # Color interpolates from dim to bright
                alpha = frac
                color = (
                    int(c_dim[0] + alpha * (c_acc[0] - c_dim[0])),
                    int(c_dim[1] + alpha * (c_acc[1] - c_dim[1])),
                    int(c_dim[2] + alpha * (c_acc[2] - c_dim[2])),
                )
                cv2.circle(layer, (px, py), size, color, -1)

    def _draw_joint_dots(
        self, layer: np.ndarray,
        pts: list[tuple[int, int]], t: float,
        c_pri: tuple,
    ) -> None:
        """Small glowing dots on PIP and MCP joints."""
        pulse = 0.5 + 0.5 * math.sin(t * 5.0)

        for jid in FINGER_PIPS + FINGER_MCPS:
            jx, jy = pts[jid]
            r = max(2, int(4 * pulse))
            cv2.circle(layer, (jx, jy), r, c_pri, -1)

    # ------------------------------------------------------------- Helpers

    @staticmethod
    def _draw_arc_ring(
        layer: np.ndarray,
        cx: int, cy: int, radius: int,
        base_angle: float,
        color: tuple, thickness: int,
        segments: int, gap: float,
    ) -> None:
        """Draw a ring made of evenly spaced arc segments."""
        if radius < 5:
            return
        arc_span = (360 / segments) - gap
        for i in range(segments):
            start = base_angle + i * (360 / segments)
            end = start + arc_span
            cv2.ellipse(layer, (cx, cy), (radius, radius),
                        0, int(start), int(end), color, thickness)
