"""
=============================================================================
 REAL-TIME REHAB AI SYSTEM
 Uses the optimized model with full feature engineering
 (joint angles, curl ratios, finger spread, wrist-relative normalization)
=============================================================================
"""
from __future__ import annotations

import argparse
import json
import random
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import joblib
import mediapipe as mp
import numpy as np
import pandas as pd

from esp32_feedback import FeedbackManager, SerialController
from gesture_constants import GESTURE_IDS
from ghost_hand import GhostHandSystem
from hud_overlay import JarvisHUD
from magic_overlay import MagicOverlay
from visual_guidance import GuidanceEngine, draw_guidance_overlay

try:
    import serial
    from serial import Serial
    from serial import SerialException
    from serial.tools import list_ports
except ImportError:
    serial = None
    Serial = Any  # type: ignore[assignment]
    list_ports = None

    class SerialException(Exception):
        """Fallback error type when pyserial is not installed."""


# -- Paths -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"
PROFILES_PATH = BASE_DIR / "data" / "processed" / "healthy_hand_profiles.json"
HEALTHY_REF_PATH = BASE_DIR / "data" / "processed" / "healthy_reference.json"

# -- Label Mapping -----------------------------------------------------------
LABEL_MAPPING = {
    "d_rbm_": "Open Hand",
    "d_rbm+": "Open Hand",
    "open_hand": "Open Hand",
    "fist": "Fist",
    "point": "Point",
}
for _gid in GESTURE_IDS:
    LABEL_MAPPING.setdefault(_gid, _gid.replace("_", " ").title())

# All 25 poses (model may still predict only classes it was trained on)
DEFAULT_TARGET_GESTURES = list(GESTURE_IDS)

# Brain-scan-based gesture plans keyed by stroke_type
_SCAN_GESTURE_PLANS: dict[str, dict] = {
    "Hemorrhagic": {
        "gestures": ["fist", "half_fist", "open_hand", "relaxed_spread", "tripod_grasp",
                     "lateral_pinch", "spread_wide"],
        "exercise_dur": 10.0,
        "hold_dur": 1.5,
        "label": "Hemorrhagic Stroke (Deep Brain — PNF Protocol)",
    },
    "Ischemic": {
        "gestures": ["open_hand", "fist", "point", "pinch", "flat_hand",
                     "lateral_pinch", "number_one", "number_five"],
        "exercise_dur": 7.0,
        "hold_dur": 1.0,
        "label": "Ischemic Stroke (MCA Territory — CIMT Protocol)",
    },
    "Stroke (Unspecified)": {
        "gestures": ["open_hand", "fist", "point", "half_fist", "flat_hand"],
        "exercise_dur": 8.0,
        "hold_dur": 1.2,
        "label": "Stroke (General Rehab Protocol)",
    },
}


def load_scan_based_plan() -> dict | None:
    """Read latest brain scan JSON and return a personalized exercise plan."""
    scans_dir = BASE_DIR / "data" / "scans"
    if not scans_dir.exists():
        return None
    scan_files = sorted(scans_dir.glob("*.json"), reverse=True)
    for f in scan_files:
        try:
            data = json.loads(f.read_text())
            sa = data.get("stroke_analysis")
            if not sa:
                continue
            stroke_type = sa.get("stroke_type", "")
            if stroke_type in ("None", "Non-stroke Condition", ""):
                continue
            plan = _SCAN_GESTURE_PLANS.get(stroke_type)
            if plan:
                return {**plan, "stroke_type": stroke_type,
                        "scan_confidence": data.get("confidence", 0),
                        "predicted_class": data.get("predicted_class", "Unknown")}
        except Exception:
            pass
    return None


# -- Landmark Constants (same as training) -----------------------------------
WRIST = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP = 17, 18, 19, 20

FINGERS = [
    ("thumb", THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP),
    ("index", INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP),
    ("middle", MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP),
    ("ring", RING_MCP, RING_PIP, RING_DIP, RING_TIP),
    ("pinky", PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP),
]

FINGER_TIP_PAIRS = [
    ("thumb_index", THUMB_TIP, INDEX_TIP),
    ("index_middle", INDEX_TIP, MIDDLE_TIP),
    ("middle_ring", MIDDLE_TIP, RING_TIP),
    ("ring_pinky", RING_TIP, PINKY_TIP),
]


# -- Exercise State ----------------------------------------------------------
@dataclass
class ExerciseState:
    """Keep the exercise session state in one place."""

    target_gesture: str
    target_deadline: float
    score: int = 0
    already_scored: bool = False
    exercise_message: str = "Match the target gesture"
    hold_start_time: float | None = None
    prediction_history: deque[str] = field(default_factory=deque)


# -- Feature Engineering (matches train_optimized.py exactly) ----------------

def _angle_3pt(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Angle ABC in degrees. B is vertex. For single points."""
    ba = a - b
    bc = c - b
    denom = np.linalg.norm(ba) * np.linalg.norm(bc)
    if denom < 1e-10:
        return 0.0
    cos_val = np.clip(np.dot(ba, bc) / denom, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_val)))


def _dist(a: np.ndarray, b: np.ndarray) -> float:
    """Euclidean distance between two points."""
    return float(np.linalg.norm(a - b))


def compute_rehab_features(landmarks_63: list[float]) -> dict[str, float]:
    """
    Compute the exact same 74 features used in training:
    42 raw landmarks (wrist-normalized) + 32 engineered features.

    This MUST match train_optimized.py's feature engineering exactly,
    otherwise the model predictions will be garbage.
    """
    # Parse 63 values -> 21 points (x, y, z)
    pts = {}
    for i in range(21):
        pts[i] = np.array([
            landmarks_63[i * 3],
            landmarks_63[i * 3 + 1],
            landmarks_63[i * 3 + 2],
        ])

    # We only use x, y (training data was 2D: 0_x, 0_y format)
    pts_2d = {i: pts[i][:2] for i in range(21)}

    # Step 1: Wrist-relative normalization (same as training)
    wrist = pts_2d[WRIST].copy()
    features = {}
    for i in range(21):
        features[f"{i}_x"] = pts_2d[i][0] - wrist[0]
        features[f"{i}_y"] = pts_2d[i][1] - wrist[1]

    wrist_norm = np.array([0.0, 0.0])  # After normalization, wrist is at origin

    # Step 2: Engineered features (EXACTLY matching train_optimized.py)
    for fname, mcp_i, pip_i, dip_i, tip_i in FINGERS:
        mcp = np.array([features[f"{mcp_i}_x"], features[f"{mcp_i}_y"]])
        pip_ = np.array([features[f"{pip_i}_x"], features[f"{pip_i}_y"]])
        dip = np.array([features[f"{dip_i}_x"], features[f"{dip_i}_y"]])
        tip = np.array([features[f"{tip_i}_x"], features[f"{tip_i}_y"]])

        # Joint angles
        features[f"angle_{fname}_mcp"] = _angle_3pt(wrist_norm, mcp, pip_)
        features[f"angle_{fname}_pip"] = _angle_3pt(mcp, pip_, dip)
        features[f"angle_{fname}_dip"] = _angle_3pt(pip_, dip, tip)

        # Curl ratio
        tip_to_wrist = _dist(tip, wrist_norm)
        mcp_to_wrist = _dist(mcp, wrist_norm)
        features[f"curl_{fname}"] = tip_to_wrist / (mcp_to_wrist + 1e-10)

        # Wrist distance
        features[f"wrist_dist_{fname}"] = tip_to_wrist

    # Finger spread
    for pname, ta, tb in FINGER_TIP_PAIRS:
        pt_a = np.array([features[f"{ta}_x"], features[f"{ta}_y"]])
        pt_b = np.array([features[f"{tb}_x"], features[f"{tb}_y"]])
        features[f"spread_{pname}"] = _dist(pt_a, pt_b)

    # Palm geometry
    mcp_dists = []
    for fname, mcp_i, pip_i, dip_i, tip_i in FINGERS:
        mcp = np.array([features[f"{mcp_i}_x"], features[f"{mcp_i}_y"]])
        mcp_dists.append(_dist(mcp, wrist_norm))
    features["palm_size"] = float(np.mean(mcp_dists))

    thumb_tip = np.array([features[f"{THUMB_TIP}_x"], features[f"{THUMB_TIP}_y"]])
    pinky_tip = np.array([features[f"{PINKY_TIP}_x"], features[f"{PINKY_TIP}_y"]])
    features["thumb_pinky_dist"] = _dist(thumb_tip, pinky_tip)

    # Hand span
    all_tips = []
    for _, _, _, _, tip_i in FINGERS:
        all_tips.append(np.array([features[f"{tip_i}_x"], features[f"{tip_i}_y"]]))
    max_span = 0.0
    for i in range(len(all_tips)):
        for j in range(i + 1, len(all_tips)):
            d = _dist(all_tips[i], all_tips[j])
            if d > max_span:
                max_span = d
    features["hand_span"] = max_span

    return features


def compute_joint_angles_display(landmarks_63: list[float]) -> dict[str, float]:
    """
    Compute key angles for UI display (not for model, just visual feedback).
    Returns human-readable angle values for each finger.
    """
    pts = {}
    for i in range(21):
        pts[i] = np.array([landmarks_63[i * 3], landmarks_63[i * 3 + 1]])

    angles = {}
    for fname, mcp_i, pip_i, dip_i, tip_i in FINGERS:
        angles[f"{fname}_pip"] = round(_angle_3pt(pts[mcp_i], pts[pip_i], pts[dip_i]), 1)

    return angles


# -- Model & Args ------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Real-time hand rehab with optimized model.")
    parser.add_argument("--model", type=str, default=None, help="Path to .joblib model bundle.")
    parser.add_argument("--camera", type=int, default=0, help="Webcam index.")
    parser.add_argument("--deviation-threshold", type=float, default=0.5)
    parser.add_argument("--min-detection-confidence", type=float, default=0.6)
    parser.add_argument("--min-tracking-confidence", type=float, default=0.6)
    parser.add_argument("--exercise-duration", type=float, default=7.0)
    parser.add_argument("--targets", nargs="+", default=None)
    parser.add_argument("--smoothing-window", type=int, default=7)
    parser.add_argument("--confidence-threshold", type=float, default=0.5)
    parser.add_argument("--hold-duration", type=float, default=1.0)
    parser.add_argument("--serial-port", type=str, default=None)
    parser.add_argument("--serial-baudrate", type=int, default=115200)
    parser.add_argument("--incorrect-alert-delay", type=float, default=1.0)
    parser.add_argument(
        "--high-deviation-threshold",
        type=float,
        default=None,
        help="Optional deviation level that sends serial '2' instead of '1'.",
    )
    return parser.parse_args()


def find_model_path(model_argument: str | None) -> Path:
    """Prefer the optimized model, fall back to any available model."""
    if model_argument:
        p = Path(model_argument).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(f"Model not found: {p}")
        return p

    # Prefer optimized landmark bundle (matches Mediapipe features), not sequence-only models
    optimized = list(MODELS_DIR.glob("*_optimized.joblib"))
    if optimized:
        landmark = [p for p in optimized if "landmarks_rehab" in p.name]
        pool = landmark if landmark else optimized
        return sorted(pool, key=lambda p: p.stat().st_mtime, reverse=True)[0]

    # Fall back to any model
    all_models = sorted(MODELS_DIR.glob("*.joblib"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not all_models:
        raise FileNotFoundError("No .joblib model found in models/")
    return all_models[0]


def load_model_bundle(model_path: Path) -> dict[str, Any]:
    bundle = joblib.load(model_path)
    required = {"model", "scaler", "label_encoder", "feature_columns"}
    missing = required - set(bundle.keys())
    if missing:
        raise KeyError(f"Model bundle missing: {', '.join(sorted(missing))}")
    return bundle


def load_healthy_profiles() -> dict[str, Any] | None:
    """Load healthy hand reference profiles for comparison feedback."""
    if not PROFILES_PATH.exists():
        return None
    return json.loads(PROFILES_PATH.read_text(encoding="utf-8"))


def load_healthy_reference() -> dict[str, Any] | None:
    """Load personal healthy hand+arm reference from capture_reference.py."""
    if not HEALTHY_REF_PATH.exists():
        return None
    ref = json.loads(HEALTHY_REF_PATH.read_text(encoding="utf-8"))
    print(f"Loaded personal healthy reference: {list(ref.keys())}")
    return ref


def get_instruction_for_gesture(healthy_ref: dict[str, Any] | None, gesture: str) -> str:
    """Get the next instruction to show patient for current target gesture."""
    if not healthy_ref or gesture not in healthy_ref:
        return ""
    instructions = healthy_ref[gesture].get("instructions", [])
    if not instructions:
        return ""
    # Cycle through instructions based on time
    idx = int(time.time() / 3) % len(instructions)
    return instructions[idx]


def compare_with_healthy_ref(
    healthy_ref: dict[str, Any] | None,
    gesture: str,
    live_features: dict[str, float],
    arm_analysis: dict[str, Any] | None,
) -> str:
    """Compare current movement with healthy reference, return specific fix."""
    if not healthy_ref or gesture not in healthy_ref:
        return ""

    ref = healthy_ref[gesture]
    hand_ref = ref.get("hand", {})
    arm_ref = ref.get("arm", {})

    worst_name = ""
    worst_error_ratio = 0.0

    # Check finger angles against healthy reference
    for feat_name, ref_data in hand_ref.items():
        if not feat_name.startswith("angle_"):
            continue
        if feat_name not in live_features:
            continue
        ideal = ref_data["mean"]
        std = ref_data["std"]
        if std < 1.0:
            std = 10.0  # minimum threshold
        error = abs(live_features[feat_name] - ideal)
        ratio = error / std
        if ratio > 2.0 and ratio > worst_error_ratio:
            worst_error_ratio = ratio
            parts = feat_name.replace("angle_", "").split("_")
            finger = parts[0].title()
            joint = parts[1].upper() if len(parts) > 1 else ""
            diff = live_features[feat_name] - ideal
            direction = "more" if diff < 0 else "less"
            worst_name = f"{finger} {joint}: bend {direction} ({abs(diff):.0f} deg off)"

    # Check elbow angle against healthy reference
    if arm_ref and arm_analysis and "elbow_angle" in arm_ref:
        ideal_elbow = arm_ref["elbow_angle"]["mean"]
        current_elbow = arm_analysis.get("elbow_angle", 0)
        elbow_diff = abs(current_elbow - ideal_elbow)
        if elbow_diff > 15:
            direction = "Extend" if current_elbow < ideal_elbow else "Relax"
            elbow_msg = f"Elbow: {direction} ({elbow_diff:.0f} deg off)"
            if not worst_name or elbow_diff > 25:
                worst_name = elbow_msg

    return worst_name


# NOTE: Serial connection and hardware feedback are now handled by
# esp32_feedback.SerialController and esp32_feedback.FeedbackManager.
# See esp32_feedback.py for the clean, modular implementation.


# -- Prediction & Exercise Logic ---------------------------------------------

def clean_gesture_name(raw_label: str) -> str:
    if raw_label in LABEL_MAPPING:
        return LABEL_MAPPING[raw_label]
    return raw_label.replace("_", " ").strip().title()


def normalize_label_name(label: str) -> str:
    return "".join(c.lower() for c in label if c.isalnum())


def resolve_target_gestures(bundle: dict[str, Any], requested: list[str] | None) -> list[str]:
    available = [str(l) for l in bundle["label_encoder"].classes_]
    lookup = {normalize_label_name(l): l for l in available}
    for l in available:
        lookup.setdefault(normalize_label_name(clean_gesture_name(l)), l)

    if requested:
        resolved = []
        for t in requested:
            r = lookup.get(normalize_label_name(t))
            if r and r not in resolved:
                resolved.append(r)
        if resolved:
            return resolved

    fallback = [l for l in DEFAULT_TARGET_GESTURES if l in available]
    return fallback if fallback else available[:min(3, len(available))]


def extract_landmarks(hand_landmarks: Any) -> list[float]:
    """Convert 21 MediaPipe landmarks into flat [x1, y1, z1, ...] list."""
    flat = []
    for lm in hand_landmarks.landmark:
        flat.extend([lm.x, lm.y, lm.z])
    return flat


def align_live_features(
    live_landmarks: list[float],
    feature_columns: list[str],
) -> pd.DataFrame:
    """
    Convert live landmarks to the same feature layout as training.
    Uses the EXACT SAME feature engineering as train_optimized.py.
    """
    features = compute_rehab_features(live_landmarks)
    live_df = pd.DataFrame([features])

    # Ensure all training columns exist
    for col in feature_columns:
        if col not in live_df.columns:
            live_df[col] = 0.0

    return live_df[feature_columns]


def predict_live(
    live_landmarks: list[float],
    bundle: dict[str, Any],
    deviation_threshold: float,
    confidence_threshold: float,
    healthy_profiles: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run prediction with the optimized model + healthy hand comparison."""
    live_df = align_live_features(live_landmarks, bundle["feature_columns"])
    scaled = bundle["scaler"].transform(live_df)

    encoded_pred = bundle["model"].predict(scaled)[0]
    predicted_label = str(bundle["label_encoder"].inverse_transform([encoded_pred])[0])

    # Confidence
    confidence = None
    if hasattr(bundle["model"], "predict_proba"):
        probs = bundle["model"].predict_proba(scaled)[0]
        confidence = float(np.max(probs))

    # Deviation from healthy reference
    deviation_score = None
    per_class_refs = bundle.get("per_class_references")
    if per_class_refs and predicted_label in per_class_refs:
        ref_mean = np.array(per_class_refs[predicted_label]["mean"])
        deviation_score = float(np.mean(np.abs(scaled[0] - ref_mean)))
    elif bundle.get("reference_vector") is not None:
        deviation_score = float(np.mean(np.abs(scaled[0] - bundle["reference_vector"])))

    is_wrong = False
    if deviation_score is not None:
        is_wrong = deviation_score > deviation_threshold
    elif confidence is not None:
        is_wrong = confidence < confidence_threshold

    movement_quality = "correct"
    feedback_text = "Perfect!"

    if is_wrong:
        movement_quality = "incorrect"
        feedback_text = "Adjust your movement"
    elif confidence is not None:
        if confidence >= 0.7:
            movement_quality = "correct"
            feedback_text = "Perfect!"
        elif confidence >= 0.5:
            movement_quality = "almost"
            feedback_text = "Good, hold steady"
        elif confidence >= 0.3:
            movement_quality = "almost"
            feedback_text = "Getting there"
        else:
            movement_quality = "uncertain"
            feedback_text = "Show hand clearly"

    return {
        "predicted_label": predicted_label,
        "display_label": clean_gesture_name(predicted_label),
        "movement_quality": movement_quality,
        "feedback_text": feedback_text,
        "joint_feedback": "",
        "is_wrong": is_wrong,
        "confidence": None if confidence is None else round(confidence, 3),
        "deviation_score": None if deviation_score is None else round(deviation_score, 4),
    }


def smooth_prediction(
    state: ExerciseState,
    prediction: dict[str, Any] | None,
    smoothing_window: int,
) -> dict[str, Any] | None:
    if prediction is None:
        state.prediction_history.clear()
        return None
    state.prediction_history.append(prediction["predicted_label"])
    while len(state.prediction_history) > smoothing_window:
        state.prediction_history.popleft()
    majority = Counter(state.prediction_history).most_common(1)[0][0]
    smoothed = prediction.copy()
    smoothed["predicted_label"] = majority
    smoothed["display_label"] = clean_gesture_name(majority)
    return smoothed


def get_target_gesture(targets: list[str], current: str | None = None) -> str:
    choices = [g for g in targets if g != current]
    return random.choice(choices or targets)


def update_score(
    state: ExerciseState,
    prediction: dict[str, Any] | None,
    hold_duration: float,
    confidence_threshold: float,
) -> ExerciseState:
    if prediction is None:
        state.exercise_message = "Show your hand to start"
        state.hold_start_time = None
        return state

    # Score based on: does the gesture MATCH the target?
    matches = prediction["predicted_label"] == state.target_gesture
    conf = prediction["confidence"] or 0.0

    if matches and conf >= 0.3:
        # Gesture matches! Start hold timer
        now = time.time()
        if state.hold_start_time is None:
            state.hold_start_time = now
        held = now - state.hold_start_time
        remaining = max(0.0, hold_duration - held)
        if held >= hold_duration:
            state.exercise_message = "Great! +1"
            if not state.already_scored:
                state.score += 1
                state.already_scored = True
        else:
            state.exercise_message = f"Matched! Hold {remaining:.1f}s"
    elif matches:
        state.exercise_message = "Almost matched, hold steady"
        state.hold_start_time = None
    else:
        target_name = clean_gesture_name(state.target_gesture)
        state.exercise_message = f"Make a {target_name}"
        state.hold_start_time = None

    return state


# NOTE: update_hardware_feedback() has been replaced by FeedbackManager.update().
# The new implementation lives in esp32_feedback.py with proper debounce,
# intensity levels, and state management encapsulated in a clean class.


# -- Arm Analysis (optional, uses pose landmarks) ----------------------------

def landmark_to_array(lm: Any) -> np.ndarray:
    return np.array([lm.x, lm.y, lm.z], dtype=float)


def analyze_arm(pose_landmarks: Any, hand_landmarks: Any, handedness: str | None) -> dict[str, Any] | None:
    """
    Analyze arm posture from MediaPipe Pose.
    Returns None silently when landmarks aren't visible — no confusing
    "Keep elbow visible" messages.  Only returns data when shoulder,
    elbow AND wrist are all confidently detected (visibility > 0.5).
    """
    if pose_landmarks is None or hand_landmarks is None:
        return None

    pose = mp.solutions.pose.PoseLandmark
    side = "left" if (handedness or "").lower() == "left" else "right"

    sh_i = pose.LEFT_SHOULDER if side == "left" else pose.RIGHT_SHOULDER
    el_i = pose.LEFT_ELBOW if side == "left" else pose.RIGHT_ELBOW
    wr_i = pose.LEFT_WRIST if side == "left" else pose.RIGHT_WRIST

    sh_lm = pose_landmarks.landmark[sh_i.value]
    el_lm = pose_landmarks.landmark[el_i.value]
    wr_lm = pose_landmarks.landmark[wr_i.value]

    # Only report arm data when all 3 joints are confidently visible
    min_vis = 0.5
    if (getattr(sh_lm, "visibility", 0) < min_vis or
        getattr(el_lm, "visibility", 0) < min_vis or
        getattr(wr_lm, "visibility", 0) < min_vis):
        return None

    sh = landmark_to_array(sh_lm)
    el = landmark_to_array(el_lm)
    wr = landmark_to_array(wr_lm)
    idx_tip = landmark_to_array(hand_landmarks.landmark[8])

    elbow_angle = _angle_3pt(sh, el, wr)
    wrist_angle = _angle_3pt(el, wr, idx_tip)

    if elbow_angle > 160:
        fb, q = "Good extension", "correct"
    elif elbow_angle >= 100:
        fb, q = "Straighten more", "almost"
    else:
        fb, q = "Too bent", "incorrect"

    return {
        "side": side.title(),
        "elbow_angle": round(elbow_angle, 1),
        "wrist_angle": round(wrist_angle, 1),
        "arm_feedback": fb,
        "arm_quality": q,
    }


# -- UI Drawing (delegated to JarvisHUD) ------------------------------------
# display_feedback is kept as a thin wrapper so the main loop signature
# doesn't need to change.  All heavy rendering lives in hud_overlay.py.

_hud: JarvisHUD | None = None


def _get_hud() -> JarvisHUD:
    global _hud
    if _hud is None:
        _hud = JarvisHUD()
    return _hud


def display_feedback(
    frame: np.ndarray,
    prediction: dict[str, Any] | None,
    arm_analysis: dict[str, Any] | None,
    fps: float,
    hand_detected: bool,
    state: ExerciseState,
    time_left: float,
    joint_angles: dict[str, float] | None = None,
    instruction: str = "",
    haptic_message: str = "",
    haptic_level: int = 0,
    *,
    hand_landmarks: Any | None = None,
    guidance: Any | None = None,
    ghost_match_pct: float = 0.0,
) -> np.ndarray:
    """Delegates all rendering to JarvisHUD."""
    hud = _get_hud()

    # Gather values for the HUD
    detected_gesture = ""
    confidence = 0.0
    joint_feedback = ""
    if prediction:
        detected_gesture = prediction.get("display_label", "")
        confidence = prediction.get("confidence") or 0.0
        joint_feedback = prediction.get("joint_feedback", "")

    arm_info = ""
    if arm_analysis:
        ea = arm_analysis.get("elbow_angle", 0)
        af = arm_analysis.get("arm_feedback", "")
        arm_info = f"Elbow {ea:.0f} - {af}"

    finger_states = []
    if guidance and hasattr(guidance, "finger_states"):
        finger_states = guidance.finger_states

    return hud.draw(
        frame,
        hand_landmarks,
        target_gesture=state.target_gesture,
        detected_gesture=detected_gesture,
        match_pct=ghost_match_pct,
        confidence=confidence,
        score=state.score,
        time_left=time_left,
        exercise_msg=state.exercise_message if hand_detected else "",
        finger_states=finger_states,
        haptic_msg=haptic_message,
        haptic_level=haptic_level,
        arm_info=arm_info,
        joint_feedback=joint_feedback,
    )


# -- Main Loop ---------------------------------------------------------------

def main() -> None:
    args = parse_args()
    model_path = find_model_path(args.model)
    bundle = load_model_bundle(model_path)
    healthy_profiles = load_healthy_profiles()
    healthy_ref = load_healthy_reference()

    print(f"Model: {model_path.name}")
    print(f"Features: {len(bundle['feature_columns'])}")
    print(f"Classes: {list(bundle['label_encoder'].classes_)}")
    print(f"Healthy profiles (ML): {'loaded' if healthy_profiles else 'not found'}")
    print(f"Healthy reference (personal): {'loaded' if healthy_ref else 'not found'}")
    if not healthy_ref:
        print("  TIP: Run capture_reference.py first to capture your healthy hand!")
    print("Starting webcam. Press Q to quit.\n")

    mp_hands = mp.solutions.hands
    mp_pose = mp.solutions.pose
    # mp_drawing / mp_drawing_styles removed — skeleton is drawn by
    # visual_guidance.py with per-finger colour coding instead.

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open webcam {args.camera}.")
    cap.set(3, 1280)
    cap.set(4, 720)
    cv2.namedWindow("Rehab AI", cv2.WINDOW_NORMAL)

    # -- ESP32 Feedback (SerialController + FeedbackManager) -----------------
    serial_ctrl = SerialController(
        port=args.serial_port,
        baudrate=args.serial_baudrate,
    )
    serial_ctrl.connect()

    feedback_mgr = FeedbackManager(
        serial_controller=serial_ctrl,
        debounce_seconds=max(args.incorrect_alert_delay, 0.2),
        low_threshold=args.deviation_threshold,
        high_threshold=(
            args.high_deviation_threshold
            if args.high_deviation_threshold is not None
            else args.deviation_threshold * 2.0
        ),
    )

    prev_time = time.time()
    exercise_dur = max(args.exercise_duration, 1.0)
    smoothing_win = max(args.smoothing_window, 1)
    conf_thresh = args.confidence_threshold
    hold_dur = max(args.hold_duration, 0.5)

    # -- Visual Guidance Engine ----------------------------------------------
    guidance_engine = GuidanceEngine(debounce_seconds=0.5)

    target_gestures = resolve_target_gestures(bundle, args.targets)

    # If user didn't specify --targets, try to load a brain-scan-personalized plan
    if args.targets is None:
        scan_plan = load_scan_based_plan()
        if scan_plan:
            available = set(bundle["label_encoder"].classes_)
            plan_gestures = [g for g in scan_plan["gestures"] if g in available]
            if plan_gestures:
                target_gestures = plan_gestures
                exercise_dur = scan_plan["exercise_dur"]
                hold_dur = scan_plan["hold_dur"]
                print(f"\n🧠 BRAIN SCAN PLAN: {scan_plan['label']}")
                print(f"   Detected: {scan_plan['predicted_class']} "
                      f"(confidence: {scan_plan['scan_confidence']:.1%})")
                print(f"   Exercises: {', '.join(target_gestures)}")
                print(f"   Hold: {hold_dur}s | Exercise duration: {exercise_dur}s\n")
        else:
            print("\n[INFO] No brain scan found — using default gesture sequence.\n")

    if not target_gestures:
        raise ValueError("No usable target gestures found.")

    state = ExerciseState(
        target_gesture=get_target_gesture(target_gestures),
        target_deadline=time.time() + exercise_dur,
    )

    # -- Magic Overlay (Doctor Strange FX) -----------------------------------
    magic = MagicOverlay()

    # -- Ghost Hand Guide (animated target pose overlay) ---------------------
    ghost = GhostHandSystem(
        gestures=target_gestures,
        transition_duration=1.0,
        base_position=(0.50, 0.42),
        scale=1.0,
        alpha=0.40,
    )
    ghost.set_target(state.target_gesture)

    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        model_complexity=1,
        min_detection_confidence=args.min_detection_confidence,
        min_tracking_confidence=args.min_tracking_confidence,
    ) as hands, mp_pose.Pose(
        static_image_mode=False,
        model_complexity=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    ) as pose:
        while True:
            success, frame = cap.read()
            if not success:
                print("Could not read frame.")
                break

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb)
            pose_results = pose.process(rgb)

            now = time.time()
            fps = 1.0 / max(now - prev_time, 1e-6)
            prev_time = now

            prediction = None
            arm_analysis = None
            joint_angles = None
            hand_detected = bool(results.multi_hand_landmarks)
            hand_lm = None
            haptic_msg = ""
            haptic_lvl = 0

            # Exercise timer
            if now >= state.target_deadline:
                state.target_gesture = get_target_gesture(target_gestures, state.target_gesture)
                state.target_deadline = now + exercise_dur
                state.already_scored = False
                state.exercise_message = "Match the target gesture"
                state.hold_start_time = None
                ghost.set_target(state.target_gesture)


            if hand_detected:
                hand_lm = results.multi_hand_landmarks[0]
                handedness = None
                if results.multi_handedness:
                    handedness = results.multi_handedness[0].classification[0].label

                live_landmarks = extract_landmarks(hand_lm)
                joint_angles = compute_joint_angles_display(live_landmarks)

                raw_pred = predict_live(
                    live_landmarks=live_landmarks,
                    bundle=bundle,
                    deviation_threshold=args.deviation_threshold,
                    confidence_threshold=conf_thresh,
                    healthy_profiles=healthy_profiles,
                )
                prediction = smooth_prediction(state, raw_pred, smoothing_win)

                arm_analysis = analyze_arm(
                    pose_landmarks=pose_results.pose_landmarks,
                    hand_landmarks=hand_lm,
                    handedness=handedness,
                )

                # Compare with personal healthy reference
                if healthy_ref and prediction:
                    live_feats = compute_rehab_features(live_landmarks)
                    fix_msg = compare_with_healthy_ref(
                        healthy_ref, state.target_gesture, live_feats, arm_analysis
                    )
                    if fix_msg:
                        prediction = prediction.copy()
                        prediction["joint_feedback"] = fix_msg

                # Arm analysis is INFORMATIONAL only — shown on screen
                # but does NOT override hand gesture quality/scoring

                state = update_score(state, prediction, hold_dur, conf_thresh)
                feedback_mgr.update(
                    deviation=prediction.get("deviation_score") if prediction else None,
                    confidence=prediction.get("confidence") if prediction else None,
                )
                haptic_msg = feedback_mgr.level_message
                haptic_lvl = feedback_mgr.current_level

                # Pose skeleton is intentionally NOT drawn — it clutters the
                # frame.  Arm analysis data is still computed above and shown
                # in the HUD text when detected.
            else:
                state.exercise_message = "Show your hand to start"
                state.hold_start_time = None
                state.prediction_history.clear()
                feedback_mgr.reset()
                haptic_msg = ""
                haptic_lvl = 0

            # -- Visual Guidance Analysis ------------------------------------
            guidance = guidance_engine.analyze(
                hand_landmarks=hand_lm,
                target_gesture=state.target_gesture,
                joint_angles=joint_angles,
                prediction=prediction,
                arm_analysis=arm_analysis,
                frame_shape=(frame.shape[0], frame.shape[1]),
            )

            # Get instruction from healthy reference
            instruction = ""
            if healthy_ref:
                instruction = get_instruction_for_gesture(healthy_ref, state.target_gesture)

            time_left = max(0.0, state.target_deadline - now)

            # -- Ghost hand (PiP panel — evaluate match score) ---------------
            ghost.tick()
            ghost_match = ghost.evaluate(hand_lm, (frame.shape[0], frame.shape[1]))
            ghost_match_pct = ghost_match.score if ghost_match else 0.0

            # -- Draw visual guidance overlay (target zone only) -------------
            frame = draw_guidance_overlay(frame, guidance, hand_lm)

            # -- Jarvis HUD (all UI elements) --------------------------------
            frame = display_feedback(
                frame=frame,
                prediction=prediction,
                arm_analysis=arm_analysis,
                fps=fps,
                hand_detected=hand_detected,
                state=state,
                time_left=time_left,
                joint_angles=joint_angles,
                instruction=instruction,
                haptic_message=haptic_msg,
                haptic_level=haptic_lvl,
                hand_landmarks=hand_lm,
                guidance=guidance,
                ghost_match_pct=ghost_match_pct,
            )

            # -- Ghost hand PiP panel (top-right corner) ---------------------
            frame = ghost.draw(frame, ghost_match)

            # -- Magic overlay (subtle — reduced to complement HUD) ----------
            magic_severity = guidance.severity if hand_lm else "neutral"
            frame = magic.draw(frame, hand_lm, severity=magic_severity)

            cv2.imshow("Rehab AI", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    serial_ctrl.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
