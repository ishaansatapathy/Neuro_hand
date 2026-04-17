"""
=============================================================================
 HEALTHY HAND + ARM REFERENCE CAPTURE
 Captures everything from the healthy side to map onto the damaged side:
   - Hand landmarks (21 points)
   - Finger joint angles (MCP, PIP, DIP per finger)
   - Finger curl ratios
   - Finger spread distances
   - Elbow angle (shoulder -> elbow -> wrist)
   - Wrist angle (elbow -> wrist -> index_tip)
=============================================================================

 Usage:
   py -3.12 capture_reference.py

 Controls:
   1 = Capture FIST
   2 = Capture OPEN HAND
   3 = Capture POINT
   S = Save reference to JSON
   Q = Quit
=============================================================================
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp
import numpy as np


# -- Paths -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "healthy_reference.json"

# -- Settings ----------------------------------------------------------------
GESTURE_KEYS = {
    ord("1"): "fist",
    ord("2"): "open_hand",
    ord("3"): "point",
}
FRAMES_PER_GESTURE = 30  # More frames = more stable reference


# -- Landmark Constants (same as train_optimized.py) -------------------------
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


# -- Angle & Distance Helpers -----------------------------------------------

def _angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Angle ABC in degrees. B is the vertex."""
    ba = a - b
    bc = c - b
    denom = np.linalg.norm(ba) * np.linalg.norm(bc)
    if denom < 1e-10:
        return 0.0
    cos_val = np.clip(np.dot(ba, bc) / denom, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_val)))


def _dist(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


def _lm_to_pt(landmark) -> np.ndarray:
    """MediaPipe landmark -> numpy array."""
    return np.array([landmark.x, landmark.y, landmark.z], dtype=float)


def _lm_to_2d(landmark) -> np.ndarray:
    """MediaPipe landmark -> 2D numpy array (x, y only)."""
    return np.array([landmark.x, landmark.y], dtype=float)


# -- Compute Full Reference from One Frame -----------------------------------

def compute_hand_reference(hand_landmarks) -> dict[str, float]:
    """
    Compute ALL rehab-relevant features from a single hand frame.
    Returns a dict of feature_name -> value.
    """
    lm = hand_landmarks.landmark
    features = {}

    # Raw 2D landmarks (wrist-normalized)
    wrist_2d = _lm_to_2d(lm[WRIST])
    for i in range(21):
        pt = _lm_to_2d(lm[i])
        features[f"{i}_x"] = pt[0] - wrist_2d[0]
        features[f"{i}_y"] = pt[1] - wrist_2d[1]

    wrist_norm = np.array([0.0, 0.0])

    # Joint angles for each finger
    for fname, mcp_i, pip_i, dip_i, tip_i in FINGERS:
        mcp = _lm_to_2d(lm[mcp_i]) - wrist_2d
        pip_ = _lm_to_2d(lm[pip_i]) - wrist_2d
        dip = _lm_to_2d(lm[dip_i]) - wrist_2d
        tip = _lm_to_2d(lm[tip_i]) - wrist_2d

        features[f"angle_{fname}_mcp"] = _angle(wrist_norm, mcp, pip_)
        features[f"angle_{fname}_pip"] = _angle(mcp, pip_, dip)
        features[f"angle_{fname}_dip"] = _angle(pip_, dip, tip)

        # Curl ratio
        tip_w = _dist(tip, wrist_norm)
        mcp_w = _dist(mcp, wrist_norm)
        features[f"curl_{fname}"] = tip_w / (mcp_w + 1e-10)

        # Wrist distance
        features[f"wrist_dist_{fname}"] = tip_w

    # Finger spread
    for pname, ta, tb in FINGER_TIP_PAIRS:
        pt_a = _lm_to_2d(lm[ta]) - wrist_2d
        pt_b = _lm_to_2d(lm[tb]) - wrist_2d
        features[f"spread_{pname}"] = _dist(pt_a, pt_b)

    # Palm size
    mcp_dists = []
    for _, mcp_i, _, _, _ in FINGERS:
        mcp = _lm_to_2d(lm[mcp_i]) - wrist_2d
        mcp_dists.append(_dist(mcp, wrist_norm))
    features["palm_size"] = float(np.mean(mcp_dists))

    # Thumb-pinky distance
    thumb_t = _lm_to_2d(lm[THUMB_TIP]) - wrist_2d
    pinky_t = _lm_to_2d(lm[PINKY_TIP]) - wrist_2d
    features["thumb_pinky_dist"] = _dist(thumb_t, pinky_t)

    # Hand span
    all_tips = []
    for _, _, _, _, tip_i in FINGERS:
        all_tips.append(_lm_to_2d(lm[tip_i]) - wrist_2d)
    max_span = 0.0
    for i in range(len(all_tips)):
        for j in range(i + 1, len(all_tips)):
            d = _dist(all_tips[i], all_tips[j])
            if d > max_span:
                max_span = d
    features["hand_span"] = max_span

    return features


def compute_arm_reference(pose_landmarks, hand_landmarks, handedness: str | None) -> dict[str, float] | None:
    """
    Compute elbow & wrist angles from Pose landmarks.
    Returns None if pose is not detected.
    """
    if pose_landmarks is None:
        return None

    pose = mp.solutions.pose.PoseLandmark
    side = "left" if (handedness or "").lower() == "left" else "right"

    sh_i = pose.LEFT_SHOULDER if side == "left" else pose.RIGHT_SHOULDER
    el_i = pose.LEFT_ELBOW if side == "left" else pose.RIGHT_ELBOW
    wr_i = pose.LEFT_WRIST if side == "left" else pose.RIGHT_WRIST

    sh = _lm_to_pt(pose_landmarks.landmark[sh_i.value])
    el = _lm_to_pt(pose_landmarks.landmark[el_i.value])
    wr = _lm_to_pt(pose_landmarks.landmark[wr_i.value])
    idx_tip = _lm_to_pt(hand_landmarks.landmark[INDEX_TIP])

    return {
        "side": side,
        "elbow_angle": _angle(sh, el, wr),
        "wrist_angle": _angle(el, wr, idx_tip),
    }


# -- Frame Recording --------------------------------------------------------

def record_frame(
    gesture_name: str,
    captured: dict[str, list[dict]],
    hand_ref: dict[str, float],
    arm_ref: dict[str, float] | None,
) -> str:
    """Record one frame of data for a gesture."""
    frame_data = {"hand": hand_ref}
    if arm_ref:
        frame_data["arm"] = arm_ref

    captured.setdefault(gesture_name, []).append(frame_data)
    count = len(captured[gesture_name])

    if count >= FRAMES_PER_GESTURE:
        return f"DONE: {gesture_name} ({count}/{FRAMES_PER_GESTURE})"
    return f"Capturing: {gesture_name} ({count}/{FRAMES_PER_GESTURE})"


# -- Save Reference ----------------------------------------------------------

def save_reference(captured: dict[str, list[dict]], output_path: Path) -> Path:
    """
    Average all captured frames per gesture and save a comprehensive reference.

    Output JSON structure per gesture:
    {
      "fist": {
        "hand": {
          "angle_index_pip": {"mean": 45.2, "std": 3.1},
          "curl_index": {"mean": 0.8, "std": 0.05},
          ...
        },
        "arm": {
          "elbow_angle": {"mean": 165.0, "std": 5.0},
          "wrist_angle": {"mean": 140.0, "std": 8.0}
        },
        "instructions": {
          "angle_index_pip": "Bend your index finger to ~45 degrees",
          ...
        },
        "frame_count": 30
      }
    }
    """
    reference = {}

    for gesture_name, frames in captured.items():
        if not frames:
            continue

        # Average hand features
        hand_features = {}
        hand_keys = frames[0]["hand"].keys()
        for key in hand_keys:
            values = [f["hand"][key] for f in frames]
            hand_features[key] = {
                "mean": round(float(np.mean(values)), 4),
                "std": round(float(np.std(values)), 4),
            }

        # Average arm features (if available)
        arm_features = {}
        arm_frames = [f["arm"] for f in frames if f.get("arm")]
        if arm_frames:
            for key in ["elbow_angle", "wrist_angle"]:
                values = [f[key] for f in arm_frames]
                arm_features[key] = {
                    "mean": round(float(np.mean(values)), 1),
                    "std": round(float(np.std(values)), 1),
                }
            arm_features["side"] = arm_frames[0].get("side", "right")

        # Generate human-readable instructions for damaged hand
        instructions = generate_instructions(gesture_name, hand_features, arm_features)

        reference[gesture_name] = {
            "hand": hand_features,
            "arm": arm_features,
            "instructions": instructions,
            "frame_count": len(frames),
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(reference, indent=2), encoding="utf-8")
    return output_path


def generate_instructions(
    gesture: str,
    hand: dict[str, dict],
    arm: dict[str, dict],
) -> list[str]:
    """
    Create step-by-step instructions for the damaged hand.
    Based on what the healthy hand did for this gesture.
    """
    steps = []

    if gesture == "open_hand":
        steps.append("Step 1: Extend all fingers as wide as possible")
        for fname in ["index", "middle", "ring", "pinky"]:
            key = f"angle_{fname}_pip"
            if key in hand:
                val = hand[key]["mean"]
                steps.append(f"  - {fname.title()} finger PIP: straighten to ~{val:.0f} deg")
        key = "spread_thumb_index"
        if key in hand:
            steps.append(f"Step 2: Spread thumb away from index finger")
        if "hand_span" in hand:
            steps.append(f"Step 3: Maximize hand span (target: {hand['hand_span']['mean']:.3f})")

    elif gesture == "fist":
        steps.append("Step 1: Curl all fingers into your palm")
        for fname in ["index", "middle", "ring", "pinky"]:
            key = f"curl_{fname}"
            if key in hand:
                val = hand[key]["mean"]
                steps.append(f"  - {fname.title()} curl ratio: {val:.2f}")
        steps.append("Step 2: Wrap thumb over fingers")

    elif gesture == "point":
        steps.append("Step 1: Extend index finger straight")
        if "angle_index_pip" in hand:
            steps.append(f"  - Index PIP angle: ~{hand['angle_index_pip']['mean']:.0f} deg")
        steps.append("Step 2: Curl other fingers into palm")
        for fname in ["middle", "ring", "pinky"]:
            key = f"curl_{fname}"
            if key in hand:
                steps.append(f"  - {fname.title()} curl: {hand[key]['mean']:.2f}")

    # Arm instructions
    if arm and "elbow_angle" in arm:
        steps.append(f"Arm: Extend elbow to ~{arm['elbow_angle']['mean']:.0f} deg")
    if arm and "wrist_angle" in arm:
        steps.append(f"Wrist: Maintain angle at ~{arm['wrist_angle']['mean']:.0f} deg")

    return steps


# -- Live Angle Display for UI -----------------------------------------------

def get_display_angles(hand_landmarks) -> dict[str, float]:
    """Get key angles for live display during capture."""
    lm = hand_landmarks.landmark
    angles = {}
    for fname, mcp_i, pip_i, dip_i, tip_i in FINGERS:
        mcp = _lm_to_2d(lm[mcp_i])
        pip_ = _lm_to_2d(lm[pip_i])
        dip = _lm_to_2d(lm[dip_i])
        angles[f"{fname}_pip"] = round(_angle(mcp, pip_, dip), 1)
    return angles


# -- UI Drawing --------------------------------------------------------------

def draw_ui(
    frame,
    status_text: str,
    captured: dict[str, list[dict]],
    live_angles: dict[str, float] | None,
    arm_info: dict[str, float] | None,
) -> None:
    fh, fw = frame.shape[:2]

    # -- Top-left: Instructions panel
    cv2.rectangle(frame, (10, 10), (540, 210), (20, 20, 20), -1)
    cv2.rectangle(frame, (10, 10), (540, 210), (0, 255, 255), 2)

    cv2.putText(frame, "HEALTHY HAND REFERENCE CAPTURE", (25, 38),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)
    cv2.putText(frame, "Show your HEALTHY hand + arm to camera", (25, 65),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
    cv2.putText(frame, "1 = Fist | 2 = Open Hand | 3 = Point", (25, 95),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 0), 2)
    cv2.putText(frame, f"Frames per gesture: {FRAMES_PER_GESTURE}", (25, 125),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 220, 220), 1)
    cv2.putText(frame, status_text, (25, 158),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(frame, "S = Save Reference | Q = Quit", (25, 190),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)

    # -- Top-right: Live angles
    if live_angles:
        cv2.rectangle(frame, (fw - 270, 10), (fw - 10, 200), (20, 20, 20), -1)
        cv2.rectangle(frame, (fw - 270, 10), (fw - 10, 200), (255, 255, 255), 2)
        cv2.putText(frame, "LIVE ANGLES", (fw - 258, 34),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)
        y = 60
        for name, val in live_angles.items():
            cv2.putText(frame, f"{name}: {val}", (fw - 255, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            y += 24

    # -- Top-right below: Arm info
    if arm_info:
        y_start = 220 if live_angles else 10
        cv2.rectangle(frame, (fw - 270, y_start), (fw - 10, y_start + 80), (20, 20, 20), -1)
        cv2.rectangle(frame, (fw - 270, y_start), (fw - 10, y_start + 80), (0, 200, 255), 2)
        cv2.putText(frame, f"Elbow: {arm_info['elbow_angle']:.1f} deg", (fw - 255, y_start + 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, f"Wrist: {arm_info['wrist_angle']:.1f} deg", (fw - 255, y_start + 58),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    # -- Bottom-left: Capture progress
    y_off = fh - 110
    cv2.rectangle(frame, (10, y_off), (370, fh - 10), (20, 20, 20), -1)
    cv2.rectangle(frame, (10, y_off), (370, fh - 10), (255, 255, 255), 2)

    gestures = ["fist", "open_hand", "point"]
    for i, g in enumerate(gestures):
        count = len(captured.get(g, []))
        done = count >= FRAMES_PER_GESTURE
        color = (0, 255, 0) if done else (255, 255, 255)
        marker = "[DONE]" if done else f"[{count}/{FRAMES_PER_GESTURE}]"
        cv2.putText(frame, f"{g}: {marker}", (25, y_off + 28 + i * 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)


# -- Main --------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("  HEALTHY HAND + ARM REFERENCE CAPTURE")
    print("  Show your HEALTHY hand + arm to the camera")
    print("=" * 60)

    mp_hands = mp.solutions.hands
    mp_pose = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils
    mp_drawing_styles = mp.solutions.drawing_styles

    captured: dict[str, list[dict]] = {
        "fist": [],
        "open_hand": [],
        "point": [],
    }
    status_text = "Show healthy hand & press 1, 2, or 3"

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Could not open the webcam.")

    cap.set(3, 1280)
    cap.set(4, 720)
    cv2.namedWindow("Healthy Reference Capture", cv2.WINDOW_NORMAL)

    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        model_complexity=1,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.6,
    ) as hands, mp_pose.Pose(
        static_image_mode=False,
        model_complexity=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    ) as pose:
        while True:
            success, frame = cap.read()
            if not success:
                print("Could not read a frame from the webcam.")
                break

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            hand_results = hands.process(rgb)
            pose_results = pose.process(rgb)

            hand_lm = None
            live_angles = None
            arm_info = None

            # ALWAYS draw Pose skeleton (arm, shoulder, elbow)
            if pose_results.pose_landmarks:
                mp_drawing.draw_landmarks(
                    frame,
                    pose_results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    mp_drawing_styles.get_default_pose_landmarks_style(),
                )

            if hand_results.multi_hand_landmarks:
                hand_lm = hand_results.multi_hand_landmarks[0]
                live_angles = get_display_angles(hand_lm)

                # Draw hand landmarks
                mp_drawing.draw_landmarks(
                    frame, hand_lm, mp_hands.HAND_CONNECTIONS,
                    mp_drawing_styles.get_default_hand_landmarks_style(),
                    mp_drawing_styles.get_default_hand_connections_style(),
                )

                # Arm analysis (needs both pose + hand)
                handedness = None
                if hand_results.multi_handedness:
                    handedness = hand_results.multi_handedness[0].classification[0].label

                if pose_results.pose_landmarks:
                    arm_ref = compute_arm_reference(
                        pose_results.pose_landmarks, hand_lm, handedness
                    )
                    if arm_ref:
                        arm_info = arm_ref

            # Draw UI
            draw_ui(frame, status_text, captured, live_angles, arm_info)
            cv2.imshow("Healthy Reference Capture", frame)

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            if key == ord("s"):
                all_done = all(
                    len(captured.get(g, [])) >= FRAMES_PER_GESTURE
                    for g in ["fist", "open_hand", "point"]
                )
                if not all_done:
                    status_text = "Capture all gestures first!"
                    continue

                saved_path = save_reference(captured, OUTPUT_PATH)
                status_text = f"SAVED! {saved_path.name}"
                print(f"\nReference saved to: {saved_path}")
                print("You can now run: py -3.12 realtime.py")
                continue

            if key in GESTURE_KEYS:
                if hand_lm is None:
                    status_text = "No hand detected. Try again."
                    continue

                gesture_name = GESTURE_KEYS[key]

                if len(captured.get(gesture_name, [])) >= FRAMES_PER_GESTURE:
                    status_text = f"{gesture_name} already complete!"
                    continue

                # Compute full reference for this frame
                hand_ref = compute_hand_reference(hand_lm)
                arm_ref = arm_info  # May be None if pose not detected

                status_text = record_frame(gesture_name, captured, hand_ref, arm_ref)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
