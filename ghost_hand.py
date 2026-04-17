"""
=============================================================================
 GHOST HAND GUIDANCE SYSTEM
 Animated reference hand overlay with match evaluation + progress bar
=============================================================================

 Shows a semi-transparent "ghost hand" demonstrating the target gesture.
 The user follows the ghost to learn correct movement.

 Classes:
   GhostHand          - Pose interpolation engine
   MatchEvaluator     - Compares user hand vs ghost hand
   GhostHandSystem    - All-in-one controller (use this in realtime.py)

 Usage:
   ghost = GhostHandSystem(["open_hand", "fist", "point"])
   ghost.set_target("fist")
   ghost.tick()
   match = ghost.evaluate(hand_landmarks, (720, 1280))
   frame = ghost.draw(frame, match)
=============================================================================
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np


# -- Hand topology (same as MediaPipe) ---------------------------------------

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),        # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),        # index
    (0, 9), (9, 10), (10, 11), (11, 12),   # middle
    (0, 13), (13, 14), (14, 15), (15, 16), # ring
    (0, 17), (17, 18), (18, 19), (19, 20), # pinky
    (5, 9), (9, 13), (13, 17),             # palm
]

FINGERTIP_IDS = [4, 8, 12, 16, 20]
JOINT_IDS = list(range(21))


# -- Reference poses (dx, dy offsets from wrist) -----------------------------
# These define the hand SHAPE. They are positioned on-screen by base_position.
# Coordinate system: x+ = right, y+ = down (matches image coords).

POSES: dict[str, list[tuple[float, float]]] = {
    "open_hand": [
        # 0:wrist
        (0.000,  0.000),
        # 1-4: thumb (spread left-upward)
        (-0.030, -0.020), (-0.060, -0.050), (-0.085, -0.085), (-0.095, -0.115),
        # 5-8: index
        (-0.020, -0.080), (-0.025, -0.125), (-0.025, -0.160), (-0.025, -0.190),
        # 9-12: middle
        ( 0.000, -0.085), ( 0.000, -0.130), ( 0.000, -0.168), ( 0.000, -0.200),
        # 13-16: ring
        ( 0.025, -0.080), ( 0.028, -0.125), ( 0.028, -0.158), ( 0.028, -0.185),
        # 17-20: pinky
        ( 0.050, -0.070), ( 0.055, -0.105), ( 0.055, -0.135), ( 0.055, -0.158),
    ],
    "fist": [
        (0.000,  0.000),
        (-0.030, -0.020), (-0.050, -0.042), (-0.038, -0.062), (-0.018, -0.058),
        (-0.020, -0.078), (-0.022, -0.100), (-0.008, -0.092), ( 0.002, -0.072),
        ( 0.000, -0.080), ( 0.002, -0.102), ( 0.015, -0.094), ( 0.015, -0.074),
        ( 0.025, -0.072), ( 0.028, -0.092), ( 0.035, -0.084), ( 0.030, -0.065),
        ( 0.048, -0.060), ( 0.050, -0.078), ( 0.055, -0.070), ( 0.048, -0.054),
    ],
    "point": [
        (0.000,  0.000),
        (-0.030, -0.020), (-0.050, -0.042), (-0.038, -0.062), (-0.018, -0.058),
        # index EXTENDED
        (-0.020, -0.080), (-0.025, -0.125), (-0.025, -0.160), (-0.025, -0.190),
        # others curled
        ( 0.000, -0.080), ( 0.002, -0.102), ( 0.015, -0.094), ( 0.015, -0.074),
        ( 0.025, -0.072), ( 0.028, -0.092), ( 0.035, -0.084), ( 0.030, -0.065),
        ( 0.048, -0.060), ( 0.050, -0.078), ( 0.055, -0.070), ( 0.048, -0.054),
    ],
}


def _blend_pose(
    a: list[tuple[float, float]],
    b: list[tuple[float, float]],
    t: float,
) -> list[tuple[float, float]]:
    return [
        (a[i][0] * (1.0 - t) + b[i][0] * t, a[i][1] * (1.0 - t) + b[i][1] * t)
        for i in range(21)
    ]


# 22 additional poses (blend open/fist/point) — keep in sync with website/src/config/gestures.ts
_EXTRA_POSE_NAMES: tuple[str, ...] = (
    "thumbs_up",
    "peace_sign",
    "ok_sign",
    "pinch",
    "flat_hand",
    "shaka",
    "rock_on",
    "stop_hand",
    "claw",
    "pinch_wide",
    "tripod_grasp",
    "lateral_pinch",
    "number_one",
    "number_two",
    "number_three",
    "number_four",
    "number_five",
    "relaxed_spread",
    "half_fist",
    "index_only",
    "thumb_out",
    "spread_wide",
)

_OH = POSES["open_hand"]
_FT = POSES["fist"]
_PT = POSES["point"]
for _j, _name in enumerate(_EXTRA_POSE_NAMES):
    _u = 0.08 + (_j % 11) * 0.08
    _v = 0.05 + (_j // 11) * 0.12
    _mid = _blend_pose(_OH, _FT, _u)
    POSES[_name] = _blend_pose(_mid, _PT, _v)

# Alias mappings for dataset label variants
POSE_ALIASES = {
    "d_rbm_": "open_hand",
    "d_rbm+": "open_hand",
    "Open Hand": "open_hand",
    "Fist": "fist",
    "Point": "point",
}


# -- Colors (BGR) ------------------------------------------------------------
# Using Jarvis palette for visual consistency
GHOST_JOINT   = (50, 200, 255)    # amber
GHOST_BONE    = (30, 100, 140)    # dim amber
GHOST_TIP     = (60, 220, 255)    # gold
MATCH_GREEN   = (80, 255, 120)
WARN_YELLOW   = (50, 230, 255)
ERR_RED       = (60, 60, 255)
BAR_BG        = (25, 25, 30)
DARK          = (12, 12, 12)
WHITE         = (240, 240, 240)

# PiP panel config
PIP_W = 200
PIP_H = 200
PIP_MARGIN = 12
PIP_BG = (18, 18, 22)


# ---------------------------------------------------------------------------
#  GhostHand — Interpolation engine for pose transitions
# ---------------------------------------------------------------------------

class GhostHand:
    """
    Manages smooth animated transitions between hand poses.

    Stores 21 landmark offsets (relative to wrist) and interpolates
    between keyframes using cosine easing.
    """

    def __init__(self, initial_gesture: str = "open_hand") -> None:
        pose = self._resolve_pose(initial_gesture)
        self._current = [list(p) for p in pose]
        self._start   = [list(p) for p in pose]
        self._target  = [list(p) for p in pose]
        self._progress = 1.0        # 0 = start, 1 = done
        self._transition_dur = 1.0
        self._transition_start = 0.0

    def set_target(self, gesture: str, duration: float = 1.2) -> None:
        """Begin smooth transition to a new gesture pose."""
        self._start = [list(p) for p in self._current]
        self._target = [list(p) for p in self._resolve_pose(gesture)]
        self._progress = 0.0
        self._transition_dur = max(duration, 0.1)
        self._transition_start = time.time()

    def tick(self) -> list[tuple[float, float]]:
        """
        Advance animation. Returns current 21 landmark offsets.
        Call once per frame.
        """
        if self._progress < 1.0:
            elapsed = time.time() - self._transition_start
            raw_t = min(elapsed / self._transition_dur, 1.0)
            # Cosine easing (smooth start + end)
            t = 0.5 * (1.0 - math.cos(raw_t * math.pi))
            self._progress = raw_t

            for i in range(21):
                self._current[i][0] = self._start[i][0] + t * (self._target[i][0] - self._start[i][0])
                self._current[i][1] = self._start[i][1] + t * (self._target[i][1] - self._start[i][1])

        return [(p[0], p[1]) for p in self._current]

    @property
    def is_animating(self) -> bool:
        return self._progress < 1.0

    @staticmethod
    def _resolve_pose(gesture: str) -> list[tuple[float, float]]:
        """Look up pose by name or alias."""
        key = POSE_ALIASES.get(gesture, gesture)
        if key in POSES:
            return POSES[key]
        # Fallback: open hand
        return POSES["open_hand"]


# ---------------------------------------------------------------------------
#  MatchEvaluator — Compare user hand shape to ghost hand shape
# ---------------------------------------------------------------------------

@dataclass
class MatchResult:
    """Result of comparing user hand to ghost hand."""
    score: float = 0.0            # 0.0 (no match) to 1.0 (perfect)
    is_matched: bool = False
    message: str = "Show your hand"
    color: tuple = WHITE


class MatchEvaluator:
    """
    Compares user's hand landmarks with ghost hand landmarks.

    Uses wrist-relative normalization so only the hand SHAPE matters,
    not the hand's position on screen.
    """

    MATCH_THRESHOLD = 0.85     # score >= this = "MATCHED"
    CLOSE_THRESHOLD = 0.60     # score >= this = "Almost"

    def evaluate(
        self,
        user_landmarks: Any,
        ghost_offsets: list[tuple[float, float]],
    ) -> MatchResult:
        """
        Compare user's MediaPipe hand landmarks with ghost hand offsets.

        Both are normalized to wrist-relative + scale-invariant representation
        before comparison.
        """
        if user_landmarks is None:
            return MatchResult(score=0.0, message="Show your hand", color=WHITE)

        lm = user_landmarks.landmark

        # -- Normalize user landmarks to wrist-relative ---------------------
        wx, wy = lm[0].x, lm[0].y
        user_rel = [(lm[i].x - wx, lm[i].y - wy) for i in range(21)]

        # Scale factor = distance from wrist to middle_mcp (landmark 9)
        user_scale = math.sqrt(user_rel[9][0]**2 + user_rel[9][1]**2)
        if user_scale < 1e-6:
            return MatchResult(score=0.0, message="Move hand closer", color=WHITE)

        user_norm = [(x / user_scale, y / user_scale) for x, y in user_rel]

        # -- Normalize ghost offsets the same way ---------------------------
        ghost_scale = math.sqrt(ghost_offsets[9][0]**2 + ghost_offsets[9][1]**2)
        if ghost_scale < 1e-6:
            ghost_scale = 0.08  # safe default
        ghost_norm = [(x / ghost_scale, y / ghost_scale) for x, y in ghost_offsets]

        # -- Compute per-landmark distance ----------------------------------
        total_dist = 0.0
        for i in range(21):
            dx = user_norm[i][0] - ghost_norm[i][0]
            dy = user_norm[i][1] - ghost_norm[i][1]
            total_dist += math.sqrt(dx * dx + dy * dy)

        avg_dist = total_dist / 21.0

        # Convert distance to 0–1 score (lower distance = higher score)
        # Tuned so avg_dist ~0.3 = score ~0.75, avg_dist ~0.8 = score ~0.3
        score = max(0.0, min(1.0, 1.0 - (avg_dist / 1.2)))

        # -- Generate feedback -----------------------------------------------
        if score >= self.MATCH_THRESHOLD:
            return MatchResult(
                score=score, is_matched=True,
                message="MATCH! Great form!", color=MATCH_GREEN)
        elif score >= self.CLOSE_THRESHOLD:
            return MatchResult(
                score=score, is_matched=False,
                message="Almost there - keep adjusting", color=WARN_YELLOW)
        elif score >= 0.3:
            return MatchResult(
                score=score, is_matched=False,
                message="Follow the ghost hand", color=WARN_YELLOW)
        else:
            return MatchResult(
                score=score, is_matched=False,
                message="Move to match the guide", color=ERR_RED)


# ---------------------------------------------------------------------------
#  GhostHandSystem — All-in-one controller for realtime.py
# ---------------------------------------------------------------------------

class GhostHandSystem:
    """
    Complete ghost hand guidance system.

    Combines GhostHand animation + MatchEvaluator + drawing.
    Single integration point for realtime.py.

    Usage:
        ghost = GhostHandSystem(["open_hand", "fist", "point"])
        ghost.set_target("fist")

        # Every frame:
        ghost.tick()
        match = ghost.evaluate(hand_landmarks, frame_shape)
        frame = ghost.draw(frame, match)
    """

    def __init__(
        self,
        gestures: list[str] | None = None,
        transition_duration: float = 1.2,
        base_position: tuple[float, float] = (0.50, 0.42),
        scale: float = 1.0,
        alpha: float = 0.45,
    ) -> None:
        """
        Parameters
        ----------
        gestures : list of gesture names (for reference; not used for cycling)
        transition_duration : seconds for pose-to-pose animation
        base_position : (x, y) normalized screen position for the ghost wrist
        scale : size multiplier for the ghost hand
        alpha : transparency (0 = invisible, 1 = opaque)
        """
        initial = (gestures or ["open_hand"])[0]
        self._ghost = GhostHand(initial_gesture=initial)
        self._evaluator = MatchEvaluator()
        self._transition_dur = transition_duration
        self._base_x, self._base_y = base_position
        self._scale = scale
        self._alpha = alpha
        self._current_gesture = initial
        self._last_match: MatchResult = MatchResult()

    # ------------------------------------------------------------------ API

    def set_target(self, gesture: str) -> None:
        """Animate ghost hand to a new gesture."""
        if gesture != self._current_gesture:
            self._ghost.set_target(gesture, duration=self._transition_dur)
            self._current_gesture = gesture

    def tick(self) -> list[tuple[float, float]]:
        """Advance animation one frame. Returns current offsets."""
        return self._ghost.tick()

    def evaluate(
        self,
        hand_landmarks: Any | None,
        frame_shape: tuple[int, int],
    ) -> MatchResult:
        """Compare user's hand with ghost hand."""
        offsets = [(p[0], p[1]) for p in self._ghost._current]
        result = self._evaluator.evaluate(hand_landmarks, offsets)
        self._last_match = result
        return result

    def draw(
        self,
        frame: np.ndarray,
        match_result: MatchResult | None = None,
    ) -> np.ndarray:
        """
        Draw ghost hand as a Picture-in-Picture panel (top-right corner).
        Clean, separated from the live hand — no overlap confusion.
        """
        fh, fw = frame.shape[:2]
        mr = match_result or self._last_match

        # PiP panel position (top-right corner)
        pip_x = fw - PIP_W - PIP_MARGIN
        pip_y = 40

        # -- 1. Draw PiP panel background -----------------------------------
        cv2.rectangle(frame, (pip_x, pip_y),
                      (pip_x + PIP_W, pip_y + PIP_H), PIP_BG, -1)

        # Animated border colour based on match
        if mr.score >= 0.85:
            border_color = MATCH_GREEN
        elif mr.score >= 0.5:
            border_color = GHOST_JOINT
        else:
            border_color = GHOST_BONE
        cv2.rectangle(frame, (pip_x, pip_y),
                      (pip_x + PIP_W, pip_y + PIP_H), border_color, 2)

        # "GUIDE" label
        cv2.putText(frame, "GUIDE", (pip_x + 6, pip_y + 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, GHOST_JOINT, 1, cv2.LINE_AA)

        # -- 2. Compute ghost landmarks inside the PiP panel -----------------
        offsets = self._ghost.tick()

        # Centre the ghost hand in the PiP panel
        center_x = pip_x + PIP_W // 2
        center_y = pip_y + PIP_H // 2 + 10
        pip_scale = PIP_W * 2.0

        ghost_pts: list[tuple[int, int]] = []
        for dx, dy in offsets:
            px = int(center_x + dx * pip_scale)
            py = int(center_y + dy * pip_scale)
            ghost_pts.append((px, py))

        # -- 3. Draw ghost hand skeleton inside panel -----------------------
        for a, b in HAND_CONNECTIONS:
            cv2.line(frame, ghost_pts[a], ghost_pts[b],
                     GHOST_BONE, 2, cv2.LINE_AA)

        for i in JOINT_IDS:
            color = GHOST_TIP if i in FINGERTIP_IDS else GHOST_JOINT
            radius = 5 if i in FINGERTIP_IDS else 3
            cv2.circle(frame, ghost_pts[i], radius, color, -1, cv2.LINE_AA)

        # Wrist dot
        cv2.circle(frame, ghost_pts[0], 6, GHOST_JOINT, 2, cv2.LINE_AA)

        # -- 4. Match arc inside the panel (bottom edge) ---------------------
        arc_cx = pip_x + PIP_W // 2
        arc_cy = pip_y + PIP_H - 18
        arc_r = 14

        cv2.ellipse(frame, (arc_cx, arc_cy), (arc_r, arc_r),
                    0, 0, 360, BAR_BG, 2, cv2.LINE_AA)

        arc_deg = int(360 * max(0.0, min(1.0, mr.score)))
        if arc_deg > 0:
            if mr.score >= 0.85:
                arc_color = MATCH_GREEN
            elif mr.score >= 0.6:
                arc_color = GHOST_JOINT
            else:
                arc_color = WARN_YELLOW
            cv2.ellipse(frame, (arc_cx, arc_cy), (arc_r, arc_r),
                        -90, 0, arc_deg, arc_color, 2, cv2.LINE_AA)

        # Match % text
        pct = int(mr.score * 100)
        cv2.putText(frame, f"{pct}%", (arc_cx + arc_r + 6, arc_cy + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, WHITE, 1, cv2.LINE_AA)

        return frame

    # ----------------------------------------------------------- Properties

    @property
    def current_gesture(self) -> str:
        return self._current_gesture

    @property
    def is_animating(self) -> bool:
        return self._ghost.is_animating
