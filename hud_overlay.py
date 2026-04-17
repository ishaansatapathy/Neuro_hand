"""
=============================================================================
 JARVIS HUD OVERLAY — Iron Man style heads-up display for Rehab AI
=============================================================================

 A unified, production-grade HUD system that renders:

   1. Animated targeting brackets around the detected hand
   2. Circular arc gauges (match %, confidence, timer)
   3. Horizontal scan-line sweep
   4. Corner data panels with clean typography
   5. Subtle grid pattern on the background
   6. Status ring around wrist landmark
   7. Finger status dots (green/red on each fingertip)

 Single consistent colour palette — Amber/Gold (Iron Man) with Teal accents.

 Usage:
   from hud_overlay import JarvisHUD
   hud = JarvisHUD()
   frame = hud.draw(frame, hand_landmarks, match_pct, confidence, ...)
=============================================================================
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np


# -- Colour Palette (BGR) — consistent Iron Man / Jarvis scheme --------------

AMBER       = (50, 200, 255)     # primary HUD colour
AMBER_DIM   = (30, 100, 140)     # dim variant
GOLD        = (60, 220, 255)     # bright accent
TEAL        = (220, 200, 50)     # secondary accent
TEAL_DIM    = (100, 90, 25)      # dim teal
CYAN        = (255, 240, 80)     # highlights
WHITE       = (240, 240, 240)
DARK        = (12, 12, 12)
DARK_PANEL  = (18, 18, 22)
GRID_COLOR  = (25, 25, 30)

STATUS_GREEN  = (80, 255, 120)
STATUS_YELLOW = (50, 230, 255)
STATUS_RED    = (60, 60, 255)

FINGER_IDS = {
    "thumb": [1, 2, 3, 4],
    "index": [5, 6, 7, 8],
    "middle": [9, 10, 11, 12],
    "ring": [13, 14, 15, 16],
    "pinky": [17, 18, 19, 20],
}
FINGERTIP_IDS = [4, 8, 12, 16, 20]
WRIST_ID = 0

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (0, 9), (9, 10), (10, 11), (11, 12),
    (0, 13), (13, 14), (14, 15), (15, 16),
    (0, 17), (17, 18), (18, 19), (19, 20),
    (5, 9), (9, 13), (13, 17),
]


@dataclass
class FingerStatus:
    name: str
    action: str = "ok"          # "ok" | "curl" | "extend"
    error_ratio: float = 0.0    # 0 = perfect


class JarvisHUD:
    """
    All-in-one Iron Man / Jarvis HUD renderer.
    Call .draw() once per frame.
    """

    def __init__(self) -> None:
        self._start = time.time()
        self._scan_y = 0.0

    def _t(self) -> float:
        return time.time() - self._start

    # ================================================================= API

    def draw(
        self,
        frame: np.ndarray,
        hand_landmarks: Any | None,
        *,
        target_gesture: str = "",
        detected_gesture: str = "",
        match_pct: float = 0.0,
        confidence: float = 0.0,
        score: int = 0,
        time_left: float = 0.0,
        exercise_msg: str = "",
        finger_states: list | None = None,
        haptic_msg: str = "",
        haptic_level: int = 0,
        arm_info: str = "",
        joint_feedback: str = "",
    ) -> np.ndarray:
        fh, fw = frame.shape[:2]
        t = self._t()

        # Layer 0: Subtle background grid
        self._draw_grid(frame, fw, fh, t)

        # Layer 1: Scan line
        self._draw_scan_line(frame, fw, fh, t)

        if hand_landmarks is not None:
            lm = hand_landmarks.landmark
            pts = [(int(lm[i].x * fw), int(lm[i].y * fh)) for i in range(21)]

            # Layer 2: Hand skeleton (clean thin lines)
            self._draw_skeleton(frame, pts, finger_states, t)

            # Layer 3: Targeting brackets around hand
            self._draw_targeting_brackets(frame, pts, fw, fh, t)

            # Layer 4: Wrist status ring
            self._draw_wrist_ring(frame, pts[0], match_pct, t)

            # Layer 5: Fingertip status dots
            self._draw_fingertip_dots(frame, pts, finger_states, t)

            # Layer 6: Per-finger direction indicators
            self._draw_finger_arrows(frame, pts, finger_states, t)

        # Layer 7: Top status bar
        self._draw_top_bar(frame, fw, target_gesture, detected_gesture,
                           confidence, t)

        # Layer 8: Score + timer (bottom-left arc gauge)
        self._draw_score_gauge(frame, score, time_left, fh, t)

        # Layer 9: Match gauge (bottom-right arc)
        self._draw_match_gauge(frame, match_pct, fw, fh, t)

        # Layer 10: Exercise message
        if exercise_msg:
            self._draw_exercise_msg(frame, exercise_msg, fw, fh, t)

        # Layer 11: Joint feedback
        if joint_feedback:
            cv2.putText(frame, f">> {joint_feedback}", (20, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, TEAL, 1, cv2.LINE_AA)

        # Layer 12: Arm info (only when present)
        if arm_info:
            cv2.putText(frame, arm_info, (20, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, AMBER_DIM, 1,
                        cv2.LINE_AA)

        # Layer 13: Haptic indicator
        if haptic_msg:
            hcolors = {0: STATUS_GREEN, 1: STATUS_YELLOW, 2: STATUS_RED}
            hc = hcolors.get(haptic_level, AMBER_DIM)
            cv2.putText(frame, haptic_msg, (fw - 180, fh - 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, hc, 1, cv2.LINE_AA)

        # Layer 14: FPS-style branding
        cv2.putText(frame, "REHAB AI", (fw - 100, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, AMBER_DIM, 1, cv2.LINE_AA)

        return frame

    # ============================================================ LAYERS

    # -- Grid --

    def _draw_grid(self, frame, fw, fh, t):
        spacing = 60
        overlay = frame.copy()
        for x in range(0, fw, spacing):
            cv2.line(overlay, (x, 0), (x, fh), GRID_COLOR, 1)
        for y in range(0, fh, spacing):
            cv2.line(overlay, (0, y), (fw, y), GRID_COLOR, 1)
        cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)

    # -- Scan line --

    def _draw_scan_line(self, frame, fw, fh, t):
        period = 4.0
        self._scan_y = (t % period) / period
        sy = int(self._scan_y * fh)

        overlay = frame.copy()
        band_h = 40
        for dy in range(-band_h, band_h + 1):
            row = sy + dy
            if 0 <= row < fh:
                alpha = 1.0 - abs(dy) / band_h
                color_val = int(alpha * 25)
                cv2.line(overlay, (0, row), (fw, row),
                         (color_val, color_val + 5, color_val + 2), 1)
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

        # Bright center line
        if 0 <= sy < fh:
            cv2.line(frame, (0, sy), (fw, sy), AMBER_DIM, 1, cv2.LINE_AA)

    # -- Skeleton --

    def _draw_skeleton(self, frame, pts, finger_states, t):
        fs_map = {}
        if finger_states:
            for fs in finger_states:
                fs_map[fs.name] = fs

        overlay = frame.copy()

        # Bones — thin, teal
        for a, b in HAND_CONNECTIONS:
            fname = self._joint_finger(a) or self._joint_finger(b)
            fs = fs_map.get(fname)

            if fs and fs.action != "ok":
                ratio = min(fs.error_ratio, 1.0)
                color = self._lerp(TEAL, STATUS_RED, ratio)
                thickness = 2
            else:
                color = TEAL_DIM
                thickness = 1

            cv2.line(overlay, pts[a], pts[b], color, thickness, cv2.LINE_AA)

        # Joints — small dots
        for i in range(21):
            fname = self._joint_finger(i)
            fs = fs_map.get(fname)
            is_tip = i in FINGERTIP_IDS

            if is_tip:
                if fs and fs.action != "ok":
                    color = self._lerp(STATUS_YELLOW, STATUS_RED,
                                       min(fs.error_ratio, 1.0))
                    r = 5
                else:
                    color = STATUS_GREEN
                    r = 4
                cv2.circle(overlay, pts[i], r, color, -1, cv2.LINE_AA)
                cv2.circle(overlay, pts[i], r + 2, color, 1, cv2.LINE_AA)
            elif i == 0:
                cv2.circle(overlay, pts[i], 6, AMBER, 2, cv2.LINE_AA)
            else:
                cv2.circle(overlay, pts[i], 2, TEAL_DIM, -1, cv2.LINE_AA)

        cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)

    # -- Targeting brackets --

    def _draw_targeting_brackets(self, frame, pts, fw, fh, t):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        margin = 35
        x1 = max(0, min(xs) - margin)
        y1 = max(0, min(ys) - margin)
        x2 = min(fw, max(xs) + margin)
        y2 = min(fh, max(ys) + margin)

        # Breathing animation
        breath = int(4 * math.sin(t * 2.0))
        x1 -= breath
        y1 -= breath
        x2 += breath
        y2 += breath

        corner_len = 25
        thickness = 2
        color = AMBER

        # Top-left corner
        cv2.line(frame, (x1, y1), (x1 + corner_len, y1), color, thickness, cv2.LINE_AA)
        cv2.line(frame, (x1, y1), (x1, y1 + corner_len), color, thickness, cv2.LINE_AA)
        # Top-right corner
        cv2.line(frame, (x2, y1), (x2 - corner_len, y1), color, thickness, cv2.LINE_AA)
        cv2.line(frame, (x2, y1), (x2, y1 + corner_len), color, thickness, cv2.LINE_AA)
        # Bottom-left corner
        cv2.line(frame, (x1, y2), (x1 + corner_len, y2), color, thickness, cv2.LINE_AA)
        cv2.line(frame, (x1, y2), (x1, y2 - corner_len), color, thickness, cv2.LINE_AA)
        # Bottom-right corner
        cv2.line(frame, (x2, y2), (x2 - corner_len, y2), color, thickness, cv2.LINE_AA)
        cv2.line(frame, (x2, y2), (x2, y2 - corner_len), color, thickness, cv2.LINE_AA)

        # Crosshair at hand center (landmark 9)
        cx, cy = pts[9]
        ch_size = 8
        cv2.line(frame, (cx - ch_size, cy), (cx + ch_size, cy),
                 AMBER_DIM, 1, cv2.LINE_AA)
        cv2.line(frame, (cx, cy - ch_size), (cx, cy + ch_size),
                 AMBER_DIM, 1, cv2.LINE_AA)

    # -- Wrist status ring --

    def _draw_wrist_ring(self, frame, wrist_pt, match_pct, t):
        wx, wy = wrist_pt
        radius = 28
        rotation = t * 30

        # Background ring
        cv2.ellipse(frame, (wx, wy), (radius, radius),
                    rotation, 0, 360, AMBER_DIM, 1, cv2.LINE_AA)

        # Match arc (fills based on match %)
        arc_end = int(360 * max(0, min(match_pct, 1.0)))
        if arc_end > 0:
            if match_pct >= 0.85:
                arc_color = STATUS_GREEN
            elif match_pct >= 0.6:
                arc_color = AMBER
            else:
                arc_color = STATUS_YELLOW
            cv2.ellipse(frame, (wx, wy), (radius, radius),
                        rotation - 90, 0, arc_end, arc_color, 2, cv2.LINE_AA)

        # Rotating tick marks (4 marks, 90 degrees apart)
        for i in range(4):
            angle = math.radians(rotation + i * 90)
            inner = radius - 4
            outer = radius + 4
            ix = int(wx + inner * math.cos(angle))
            iy = int(wy + inner * math.sin(angle))
            ox = int(wx + outer * math.cos(angle))
            oy = int(wy + outer * math.sin(angle))
            cv2.line(frame, (ix, iy), (ox, oy), AMBER, 1, cv2.LINE_AA)

    # -- Fingertip dots --

    def _draw_fingertip_dots(self, frame, pts, finger_states, t):
        fs_map = {}
        if finger_states:
            for fs in finger_states:
                fs_map[fs.name] = fs

        finger_tip_map = {"thumb": 4, "index": 8, "middle": 12,
                          "ring": 16, "pinky": 20}

        for fname, tip_id in finger_tip_map.items():
            fs = fs_map.get(fname)
            tx, ty = pts[tip_id]

            if fs and fs.action != "ok":
                pulse = 0.6 + 0.4 * math.sin(t * 5.0 + tip_id * 0.7)
                radius = int(10 + 4 * pulse)
                color = self._lerp(STATUS_YELLOW, STATUS_RED,
                                   min(fs.error_ratio, 1.0))

                # Outer pulsing ring
                cv2.circle(frame, (tx, ty), radius, color, 1, cv2.LINE_AA)
                # Inner dot
                cv2.circle(frame, (tx, ty), 3, color, -1, cv2.LINE_AA)
            else:
                # Small green check dot
                cv2.circle(frame, (tx, ty), 4, STATUS_GREEN, -1, cv2.LINE_AA)
                cv2.circle(frame, (tx, ty), 6, STATUS_GREEN, 1, cv2.LINE_AA)

    # -- Per-finger direction arrows --

    def _draw_finger_arrows(self, frame, pts, finger_states, t):
        if not finger_states:
            return

        for fs in finger_states:
            if fs.action == "ok":
                continue

            chain = FINGER_IDS.get(fs.name)
            if not chain:
                continue

            mcp_pt = pts[chain[0]]
            pip_pt = pts[chain[1]]
            tip_pt = pts[chain[3]]

            if fs.action == "curl":
                dx = mcp_pt[0] - tip_pt[0]
                dy = mcp_pt[1] - tip_pt[1]
            else:
                dx = tip_pt[0] - mcp_pt[0]
                dy = tip_pt[1] - mcp_pt[1]

            length = math.sqrt(dx * dx + dy * dy)
            if length < 5:
                continue
            ux, uy = dx / length, dy / length

            bounce = 6 * math.sin(t * 4.5 + hash(fs.name) % 7)
            arrow_len = 22 + bounce

            bx = pip_pt[0] + int(ux * 8)
            by = pip_pt[1] + int(uy * 8)
            ex = bx + int(ux * arrow_len)
            ey = by + int(uy * arrow_len)

            color = self._lerp(STATUS_YELLOW, STATUS_RED,
                               min(fs.error_ratio, 1.0))

            # Arrow with glow
            cv2.arrowedLine(frame, (bx, by), (ex, ey), DARK, 5,
                            tipLength=0.35, line_type=cv2.LINE_AA)
            cv2.arrowedLine(frame, (bx, by), (ex, ey), color, 2,
                            tipLength=0.35, line_type=cv2.LINE_AA)

    # -- Top status bar --

    def _draw_top_bar(self, frame, fw, target, detected, confidence, t):
        # Thin gradient line at top
        cv2.line(frame, (0, 0), (fw, 0), AMBER_DIM, 2)

        # Target gesture (left)
        if target:
            label = f"TARGET  {target.upper().replace('_', ' ')}"
            cv2.putText(frame, label, (16, 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, AMBER, 2, cv2.LINE_AA)

        # Detected gesture (centre-left)
        if detected:
            # Quality colour
            if confidence >= 0.7:
                gc = STATUS_GREEN
            elif confidence >= 0.4:
                gc = STATUS_YELLOW
            else:
                gc = STATUS_RED

            cv2.putText(frame, detected.upper(), (16, 55),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, gc, 1, cv2.LINE_AA)

            # Mini confidence bar
            bar_x = 180
            bar_w = 60
            bar_y = 46
            bar_h = 6
            cv2.rectangle(frame, (bar_x, bar_y),
                          (bar_x + bar_w, bar_y + bar_h), AMBER_DIM, -1)
            fill = int(bar_w * max(0, min(confidence, 1.0)))
            if fill > 0:
                cv2.rectangle(frame, (bar_x, bar_y),
                              (bar_x + fill, bar_y + bar_h), gc, -1)

    # -- Score gauge (bottom-left) --

    def _draw_score_gauge(self, frame, score, time_left, fh, t):
        cx, cy = 55, fh - 55
        radius = 35

        # Background arc
        cv2.ellipse(frame, (cx, cy), (radius, radius),
                    0, 0, 360, AMBER_DIM, 1, cv2.LINE_AA)

        # Timer arc (sweeps as time runs down, max ~7s)
        max_time = 7.0
        frac = max(0.0, min(time_left / max_time, 1.0))
        arc_deg = int(360 * frac)
        if arc_deg > 0:
            cv2.ellipse(frame, (cx, cy), (radius, radius),
                        -90, 0, arc_deg, AMBER, 2, cv2.LINE_AA)

        # Score number in center
        score_str = str(score)
        (tw, th), _ = cv2.getTextSize(score_str, cv2.FONT_HERSHEY_SIMPLEX,
                                      0.9, 2)
        cv2.putText(frame, score_str, (cx - tw // 2, cy + th // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, GOLD, 2, cv2.LINE_AA)

        # "SCORE" label below
        cv2.putText(frame, "SCORE", (cx - 22, cy + radius + 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, AMBER_DIM, 1, cv2.LINE_AA)

        # Timer text
        cv2.putText(frame, f"{time_left:.1f}s", (cx + radius + 8, cy + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, AMBER_DIM, 1, cv2.LINE_AA)

    # -- Match gauge (bottom-right) --

    def _draw_match_gauge(self, frame, match_pct, fw, fh, t):
        cx, cy = fw - 55, fh - 55
        radius = 35

        # Background
        cv2.ellipse(frame, (cx, cy), (radius, radius),
                    0, 0, 360, AMBER_DIM, 1, cv2.LINE_AA)

        # Match arc
        arc_deg = int(360 * max(0, min(match_pct, 1.0)))
        if arc_deg > 0:
            if match_pct >= 0.85:
                color = STATUS_GREEN
            elif match_pct >= 0.6:
                color = AMBER
            else:
                color = STATUS_YELLOW

            cv2.ellipse(frame, (cx, cy), (radius, radius),
                        -90, 0, arc_deg, color, 2, cv2.LINE_AA)

        # Percentage in center
        pct_str = f"{int(match_pct * 100)}"
        (tw, th), _ = cv2.getTextSize(pct_str, cv2.FONT_HERSHEY_SIMPLEX,
                                      0.8, 2)
        cv2.putText(frame, pct_str, (cx - tw // 2, cy + th // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, WHITE, 2, cv2.LINE_AA)

        # "%" small
        cv2.putText(frame, "%", (cx + tw // 2 + 2, cy + th // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, AMBER_DIM, 1, cv2.LINE_AA)

        # "MATCH" label
        cv2.putText(frame, "MATCH", (cx - 22, cy + radius + 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, AMBER_DIM, 1, cv2.LINE_AA)

    # -- Exercise message --

    def _draw_exercise_msg(self, frame, msg, fw, fh, t):
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.5
        (tw, th), _ = cv2.getTextSize(msg, font, scale, 1)

        px = (fw - tw) // 2 - 12
        py = 65

        # Subtle background
        cv2.rectangle(frame, (px - 4, py - th - 4),
                      (px + tw + 16, py + 6), DARK_PANEL, -1)
        cv2.rectangle(frame, (px - 4, py - th - 4),
                      (px + tw + 16, py + 6), AMBER_DIM, 1)

        cv2.putText(frame, msg, (px + 6, py),
                    font, scale, AMBER, 1, cv2.LINE_AA)

    # ============================================================ HELPERS

    @staticmethod
    def _joint_finger(jid: int) -> str:
        if jid in (1, 2, 3, 4):
            return "thumb"
        if jid in (5, 6, 7, 8):
            return "index"
        if jid in (9, 10, 11, 12):
            return "middle"
        if jid in (13, 14, 15, 16):
            return "ring"
        if jid in (17, 18, 19, 20):
            return "pinky"
        return ""

    @staticmethod
    def _lerp(a: tuple, b: tuple, t: float) -> tuple:
        t = max(0.0, min(1.0, t))
        return (
            int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t),
        )
