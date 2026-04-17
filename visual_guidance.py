"""
=============================================================================
 VISUAL GUIDANCE ENGINE — Analysis + lightweight overlay
=============================================================================

 Analyses hand landmarks, finger angles, and arm data each frame to produce
 a Guidance object with per-finger states.  The heavy rendering is handled
 by hud_overlay.JarvisHUD — this module only draws a minimal target-zone
 indicator (dashed border) so the HUD stays clean.

 Usage:
   from visual_guidance import GuidanceEngine, draw_guidance_overlay

   engine  = GuidanceEngine()
   guidance = engine.analyze(hand_lm, "fist", angles, prediction, arm, shape)
   frame   = draw_guidance_overlay(frame, guidance, hand_lm)
=============================================================================
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

# Colours (Jarvis palette)
AMBER     = (50, 200, 255)
AMBER_DIM = (30, 100, 140)
GREEN     = (80, 255, 120)
RED       = (60, 60, 255)

# Target zone (normalised 0–1)
ZONE_X_MIN, ZONE_X_MAX = 0.18, 0.82
ZONE_Y_MIN, ZONE_Y_MAX = 0.08, 0.82


# -- Data classes -----------------------------------------------------------

@dataclass
class FingerState:
    name: str
    action: str = "ok"
    error_ratio: float = 0.0
    pip_angle: float = 180.0

@dataclass
class Guidance:
    message: str = "Show your hand"
    severity: str = "neutral"
    arrows: list = field(default_factory=list)
    finger_hints: list = field(default_factory=list)
    finger_states: list = field(default_factory=list)
    in_zone: bool = False


# -- Engine -----------------------------------------------------------------

class GuidanceEngine:
    GESTURE_EXPECTATIONS = {
        "fist":      {"thumb": "curl", "index": "curl", "middle": "curl", "ring": "curl", "pinky": "curl"},
        "open_hand": {"thumb": "extend", "index": "extend", "middle": "extend", "ring": "extend", "pinky": "extend"},
        "d_rbm_":    {"thumb": "extend", "index": "extend", "middle": "extend", "ring": "extend", "pinky": "extend"},
        "d_rbm+":    {"thumb": "extend", "index": "extend", "middle": "extend", "ring": "extend", "pinky": "extend"},
        "point":     {"thumb": "curl", "index": "extend", "middle": "curl", "ring": "curl", "pinky": "curl"},
    }
    CURL_THRESH   = 90
    EXTEND_THRESH = 140

    def __init__(self, debounce_seconds: float = 0.5) -> None:
        self._debounce_sec = debounce_seconds
        self._current: Guidance = Guidance()
        self._pending: Guidance | None = None
        self._pending_since: float | None = None

    def analyze(
        self,
        hand_landmarks: Any | None,
        target_gesture: str,
        joint_angles: dict[str, float] | None,
        prediction: dict[str, Any] | None,
        arm_analysis: dict[str, Any] | None,
        frame_shape: tuple[int, int],
    ) -> Guidance:
        if hand_landmarks is None:
            return self._debounce(Guidance(message="Show your hand", severity="neutral"))

        lm = hand_landmarks.landmark
        cx, cy = lm[9].x, lm[9].y

        arrows: list[tuple[str, float]] = []
        messages: list[str] = []
        finger_hints: list[str] = []
        finger_states: list[FingerState] = []
        severity = "correct"

        in_zone = ZONE_X_MIN <= cx <= ZONE_X_MAX and ZONE_Y_MIN <= cy <= ZONE_Y_MAX
        if not in_zone:
            severity = "warning"
            if cy < ZONE_Y_MIN:
                arrows.append(("down", 0.8))
            elif cy > ZONE_Y_MAX:
                arrows.append(("up", 0.8))
            if cx < ZONE_X_MIN:
                arrows.append(("right", 0.6))
            elif cx > ZONE_X_MAX:
                arrows.append(("left", 0.6))

        if joint_angles and target_gesture in self.GESTURE_EXPECTATIONS:
            for fname, expected in self.GESTURE_EXPECTATIONS[target_gesture].items():
                angle = joint_angles.get(f"{fname}_pip", 180.0)
                fs = FingerState(name=fname, pip_angle=angle)
                if expected == "curl" and angle > self.EXTEND_THRESH:
                    fs.action = "curl"
                    fs.error_ratio = (angle - self.CURL_THRESH) / 90.0
                    finger_hints.append(f"Curl {fname}")
                    if severity != "error":
                        severity = "warning"
                elif expected == "extend" and angle < self.CURL_THRESH:
                    fs.action = "extend"
                    fs.error_ratio = (self.EXTEND_THRESH - angle) / 90.0
                    finger_hints.append(f"Extend {fname}")
                    if severity != "error":
                        severity = "warning"
                finger_states.append(fs)

        if arm_analysis and arm_analysis.get("elbow_angle", 180) < 100:
            arrows.append(("up", 0.5))

        if prediction:
            quality = prediction.get("movement_quality", "")
            if quality == "correct" and not finger_hints and in_zone:
                severity = "correct"
                messages = ["Perfect form!"]
            elif quality == "incorrect":
                severity = "error"
                if not messages and not finger_hints:
                    messages.append("Adjust your movement")

        if not messages:
            messages = finger_hints[:2] if finger_hints else ["Great movement!"]

        return self._debounce(Guidance(
            message=" | ".join(messages[:2]),
            severity=severity,
            arrows=arrows,
            finger_hints=finger_hints,
            finger_states=finger_states,
            in_zone=in_zone,
        ))

    @property
    def guidance(self) -> Guidance:
        return self._current

    def _debounce(self, new: Guidance) -> Guidance:
        now = time.time()
        if new.severity == self._current.severity:
            self._current = new
            self._pending = None
            self._pending_since = None
            return self._current
        if self._pending is None or self._pending.severity != new.severity:
            self._pending = new
            self._pending_since = now
            return self._current
        if self._pending_since is not None and (now - self._pending_since) >= self._debounce_sec:
            self._current = new
            self._pending = None
            self._pending_since = None
        return self._current


# -- Minimal overlay (target zone only) -------------------------------------

_anim_start = time.time()


def draw_guidance_overlay(
    frame: np.ndarray,
    guidance: Guidance,
    hand_landmarks: Any | None = None,
) -> np.ndarray:
    """
    Lightweight overlay — only the target-zone dashed border.
    All other visuals (skeleton, arrows, pills) are handled by JarvisHUD.
    """
    fh, fw = frame.shape[:2]
    t = time.time() - _anim_start

    color = GREEN if guidance.in_zone else AMBER_DIM
    zx1 = int(ZONE_X_MIN * fw)
    zy1 = int(ZONE_Y_MIN * fh)
    zx2 = int(ZONE_X_MAX * fw)
    zy2 = int(ZONE_Y_MAX * fh)

    # Animated dashed border (subtle)
    dash, gap = 18, 14
    offset = int(t * 30) % (dash + gap)
    thickness = 1 if guidance.in_zone else 2

    for pt1, pt2 in [((zx1, zy1), (zx2, zy1)), ((zx2, zy1), (zx2, zy2)),
                      ((zx2, zy2), (zx1, zy2)), ((zx1, zy2), (zx1, zy1))]:
        _dashed_line(frame, pt1, pt2, color, thickness, dash, gap, offset)

    return frame


def _dashed_line(frame, pt1, pt2, color, thickness, dash, gap, offset):
    dx = pt2[0] - pt1[0]
    dy = pt2[1] - pt1[1]
    length = math.sqrt(dx * dx + dy * dy)
    if length < 1:
        return
    ux, uy = dx / length, dy / length
    total = dash + gap
    pos = -offset % total
    while pos < length:
        s = max(pos, 0)
        e = min(pos + dash, length)
        if e > 0 and s < length:
            cv2.line(frame,
                     (int(pt1[0] + ux * s), int(pt1[1] + uy * s)),
                     (int(pt1[0] + ux * e), int(pt1[1] + uy * e)),
                     color, thickness, cv2.LINE_AA)
        pos += total
