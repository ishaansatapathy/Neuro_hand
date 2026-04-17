# 🧠 AI-Based Post-Stroke Rehabilitation System
### Using Computer Vision and Embedded Hardware

> A personalized, real-time rehabilitation system that captures ideal movement from a patient's healthy hand and guides the damaged hand to match it — using AI, computer vision, and haptic feedback.

---

## 📌 Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Core Idea](#2-core-idea)
3. [System Architecture](#3-system-architecture)
4. [Software Components](#4-software-components)
5. [Hardware Components](#5-hardware-components)
6. [ML Pipeline](#6-ml-pipeline)
7. [Healthy Hand Reference System](#7-healthy-hand-reference-system)
8. [Mapping & Comparison Logic](#8-mapping--comparison-logic)
9. [Feedback System](#9-feedback-system)
10. [Unique Selling Points](#10-unique-selling-points)
11. [Future Scope](#11-future-scope)

---

## 1. Problem Statement

Every year, millions of people suffer from strokes worldwide. One of the most common aftereffects is **partial or complete loss of motor control** in one hand. Recovery is possible — but it demands **consistent, repetitive physiotherapy** over weeks or even months.

Here's the reality:

- **Physiotherapy sessions are limited.** Patients typically get 2–3 sessions per week, each lasting 30–45 minutes.
- **At home, there is no guidance.** Patients are expected to practice exercises on their own, but without real-time feedback, they often perform movements incorrectly — or stop practicing altogether.
- **Progress tracking is manual.** Therapists rely on visual observation during sessions, which is subjective and infrequent.
- **Access is unequal.** In rural and semi-urban areas, qualified physiotherapists are scarce and expensive.

> **The gap is clear:** Patients need continuous, intelligent guidance at home — not just during clinic visits.

This project bridges that gap.

---

## 2. Core Idea

The fundamental concept behind this system is simple but powerful:

> **Your healthy hand is the best reference for your damaged hand.**

### How it works:

1. **Capture the ideal movement** — The system uses a camera to record the movement of the patient's **healthy (unaffected) hand**. It extracts joint angles, finger positions, and movement patterns.

2. **Build a personalized reference** — These captured movements become the patient's **own benchmark**. Not a generic standard — but a reference built from their own body.

3. **Guide the damaged hand** — When the patient exercises with their **affected (damaged) hand**, the system compares each movement against the stored healthy-hand reference in real time.

4. **Provide instant feedback** — If the movement deviates from the ideal, the system tells the patient exactly what to fix — through on-screen instructions and physical vibration feedback.

### Why this matters:

- Every person's range of motion is different. A 60-year-old's "ideal" is different from a 30-year-old's.
- By using the patient's **own healthy hand** as the baseline, the system creates a **truly personalized rehabilitation experience**.
- This is not about comparing against a database of strangers. It's about comparing **you with yourself**.

---

## 3. System Architecture

The system operates in two phases: **Reference Capture** and **Guided Rehabilitation**.

### Phase 1: Reference Capture (Healthy Hand)

```
Healthy Hand
    │
    ▼
Camera (Webcam)
    │
    ▼
MediaPipe Hand Tracking
    │ Extracts 21 hand landmarks
    ▼
Angle Calculation Engine
    │ Calculates: elbow angle, wrist angle, finger spread, individual finger curl
    ▼
Reference Storage (JSON)
    │ Stores ideal angles and landmark positions
    ▼
✅ Personalized Reference Ready
```

### Phase 2: Guided Rehabilitation (Damaged Hand)

```
Damaged Hand
    │
    ▼
Camera + Sensors (Flex, MPU6050)
    │
    ▼
Real-Time Landmark Extraction
    │
    ▼
┌─────────────────────────┐
│   Comparison Engine     │
│                         │
│  current vs. reference  │
│  angle-by-angle check   │
└────────┬────────────────┘
         │
    ┌────┴─────┐
    ▼          ▼
 Visual     Haptic
Feedback   Feedback
 (Screen)  (Vibration via ESP32)
```

### Data Flow Summary

```
Healthy Hand → Capture → Compute Angles → Store Reference (JSON)
                                                │
Damaged Hand → Capture → Compute Angles ────► Compare ──► Feedback
```

---

## 4. Software Components

### 4.1 MediaPipe (Hand Tracking)

Google's MediaPipe Hands is the backbone of our tracking system.

- **What it does:** Detects and tracks **21 key landmarks** on a hand in real time from a standard webcam feed.
- **Landmarks include:** Wrist, thumb joints (CMC, MCP, IP, TIP), index finger joints, middle finger joints, ring finger joints, and pinky finger joints.
- **Why MediaPipe:** It's fast (~30 FPS on a laptop), accurate, lightweight, and requires no GPU.
- **Our usage:** We extract the (x, y, z) coordinates of all 21 landmarks and compute joint angles from them.

```
Landmark Map:
0  = Wrist
1-4   = Thumb (CMC → TIP)
5-8   = Index Finger (MCP → TIP)
9-12  = Middle Finger (MCP → TIP)
13-16 = Ring Finger (MCP → TIP)
17-20 = Pinky (MCP → TIP)
```

### 4.2 Machine Learning Module

- **Purpose:** Gesture detection, movement validation, and deviation scoring.
- **Models Used:** Random Forest (primary), SVM (alternative).
- **Input Features:** Normalized landmark coordinates + computed joint angles.
- **Output:** Gesture classification (e.g., "Open Hand", "Closed Fist", "Pinch") + correctness score.
- **Trained Models:**
  - `landmarks_random_forest_pipeline.joblib` — Classifies based on raw landmark positions.
  - `gesture_sequences_random_forest_pipeline.joblib` — Classifies based on movement sequences over time.

### 4.3 Real-Time Processing System

- **OpenCV** handles webcam input, frame capture, and display.
- **Processing pipeline** runs at real-time speed: capture → detect → extract → compare → display.
- **Live UI overlay** shows current gesture, correctness status, and instructions directly on the camera feed.

### 4.4 Gamification Layer

Recovery is boring. Repetition is boring. So we make it engaging:

- **Guided Exercises:** Step-by-step on-screen instructions ("Open your hand... now close it slowly").
- **Score System:** Every correct movement earns points. Streaks multiply the score.
- **Progress Tracking:** Session-by-session improvement is logged and can be reviewed.
- **Goal:** Turn rehabilitation from a chore into a challenge.

---

## 5. Hardware Components

| Component | Role | Details |
|-----------|------|---------|
| **ESP32** | Central microcontroller | Handles communication between sensors and the software system via serial/WiFi |
| **Flex Sensors** | Finger bend detection | Resistance changes as fingers bend — provides analog data on finger curl |
| **MPU6050** | Motion & orientation sensing | 6-axis IMU (3-axis accelerometer + 3-axis gyroscope) — detects hand tilt, rotation, and movement speed |
| **Vibration Motor** | Haptic feedback | Activates when movement is incorrect — gives physical "nudge" to correct posture |
| **Breadboard + Jumper Wires** | Prototyping connections | Standard prototyping setup for sensor integration |

### Hardware-Software Communication

```
Flex Sensors ──┐
               ├──► ESP32 ──► Serial/WiFi ──► Python Backend
MPU6050 ───────┘                                    │
                                                    ▼
                                            Comparison Engine
                                                    │
                                                    ▼
Vibration Motor ◄──── ESP32 ◄──── Feedback Signal ──┘
```

> **Note:** Hardware integration is a Phase 2 milestone. The current system operates fully with camera-based tracking using MediaPipe.

---

## 6. ML Pipeline

### Overview

```
Data Collection → Preprocessing → Feature Extraction → Model Training → Prediction
```

### Step-by-Step Breakdown

#### 6.1 Data Collection
- Hand gesture data captured via webcam using MediaPipe.
- Each frame produces 21 landmarks × 3 coordinates (x, y, z) = **63 features per frame**.
- Additional datasets used: `hand_gestures.csv`, `data.csv`, `Controlled_EDK_Dataset2.csv`.
- Multiple gesture classes recorded: Open Hand, Closed Fist, Pinch, Spread, Point, etc.

#### 6.2 Preprocessing
- **Normalization:** Landmark coordinates normalized relative to wrist position (landmark 0) to make the model position-invariant.
- **Filtering:** Frames with low detection confidence are discarded.
- **Augmentation:** Minor rotations and scaling applied to increase dataset diversity.

#### 6.3 Feature Extraction
Two types of features are computed:

| Feature Type | Description |
|---|---|
| **Landmark Coordinates** | Normalized (x, y, z) of all 21 points |
| **Joint Angles** | Angles between connected landmarks — e.g., angle at MCP joint of index finger, wrist flexion angle, thumb abduction angle |

Angle calculation formula:
```
Given three points A, B, C:
  vector BA = A - B
  vector BC = C - B
  angle = arccos( (BA · BC) / (|BA| × |BC|) )
```

#### 6.4 Model Training
- **Algorithm:** Random Forest Classifier (ensemble of decision trees).
- **Why Random Forest:**
  - Handles high-dimensional data well (63+ features).
  - Resistant to overfitting with proper tuning.
  - Fast inference — critical for real-time use.
- **Training:** scikit-learn pipeline with StandardScaler + RandomForestClassifier.
- **Validation:** Train/test split with cross-validation.

#### 6.5 Prediction
- Trained model receives live landmark data and outputs:
  - **Gesture class** (what gesture is being performed)
  - **Confidence score** (how certain the model is)
- Prediction runs every frame in the real-time loop.

---

## 7. Healthy Hand Reference System

This is the **heart of personalization** in our system.

### How Reference Capture Works

1. **User positions healthy hand** in front of the camera.
2. **System captures multiple frames** (typically 30–60 frames over 2–3 seconds).
3. **MediaPipe extracts landmarks** for each frame.
4. **Angles are calculated** for every joint of interest:
   - Wrist flexion/extension angle
   - MCP joint angles (all 5 fingers)
   - PIP joint angles (all 5 fingers)
   - Finger spread angle (distance between adjacent fingertips)
   - Thumb abduction angle
5. **Averaged values** across all captured frames become the reference.
6. **Reference is stored as JSON** for persistent use.

### Reference JSON Structure

```json
{
  "gesture": "open_hand",
  "timestamp": "2026-04-11T01:00:00",
  "reference_angles": {
    "wrist_flexion": 165.3,
    "index_mcp": 172.1,
    "index_pip": 168.5,
    "middle_mcp": 174.0,
    "middle_pip": 170.2,
    "ring_mcp": 170.8,
    "ring_pip": 166.1,
    "pinky_mcp": 168.3,
    "pinky_pip": 162.7,
    "thumb_abduction": 45.2,
    "finger_spread": 38.6
  },
  "reference_landmarks": [
    {"id": 0, "x": 0.0, "y": 0.0, "z": 0.0},
    {"id": 1, "x": 0.12, "y": -0.03, "z": 0.01},
    "... (21 landmarks total)"
  ]
}
```

### Why This Matters

- Generic systems compare against a "standard" that may not apply to the patient.
- Our system says: **"Your healthy hand IS the standard."**
- Even if a patient has naturally limited range of motion (e.g., arthritis), the reference adapts to them.

---

## 8. Mapping & Comparison Logic

### The Core Comparison

Every frame, the system performs a joint-by-joint comparison:

```python
error = abs(current_angle - ideal_angle)
```

### Decision Logic

```python
for each joint_angle:
    error = abs(current_angle - reference_angle)

    if error < THRESHOLD_GOOD:       # e.g., < 10°
        status = "CORRECT ✅"
    elif error < THRESHOLD_MODERATE:  # e.g., < 25°
        status = "CLOSE — Adjust slightly 🟡"
    else:                            # e.g., > 25°
        status = "INCORRECT ❌"
        trigger_feedback(joint_name, direction)
```

### Threshold Configuration

| Threshold | Value | Meaning |
|-----------|-------|---------|
| `THRESHOLD_GOOD` | < 10° | Movement is within acceptable range |
| `THRESHOLD_MODERATE` | 10° – 25° | Close but needs minor adjustment |
| `THRESHOLD_BAD` | > 25° | Significant deviation — feedback triggered |

### Direction Detection

The system doesn't just say "wrong" — it tells you **how to fix it**:

```python
if current_angle < reference_angle:
    instruction = f"Extend your {joint_name} more"
else:
    instruction = f"Curl your {joint_name} slightly"
```

### Overall Score Calculation

```python
total_error = sum(errors_for_all_joints)
max_possible_error = num_joints * 180  # worst case

score = max(0, 10 - (total_error / max_possible_error) * 10)
# Score ranges from 0 (worst) to 10 (perfect match)
```

---

## 9. Feedback System

The system provides **two channels of feedback** simultaneously:

### 9.1 Visual Feedback (On-Screen)

Real-time text overlays on the webcam feed and dashboard:

| Scenario | Message |
|----------|---------|
| Perfect match | ✅ **"Great job! Hold this position"** |
| Minor deviation | 🟡 **"Almost there — extend your index finger a bit more"** |
| Major deviation | ❌ **"Your wrist angle is too low — raise your hand"** |
| Gesture mismatch | ⚠️ **"Expected: Open Hand. Detected: Fist. Please open your hand."** |

Additional visual cues:
- **Color-coded skeleton overlay** — Green joints = correct, Red joints = needs correction.
- **Progress bar** — Shows how close the current pose is to the reference.
- **Score counter** — Real-time score with animation for streaks.

### 9.2 Haptic Feedback (Physical — via ESP32)

- When movement deviation exceeds the threshold, the **vibration motor activates**.
- **Vibration intensity scales with error magnitude** — slight error = gentle buzz, major error = strong vibration.
- This provides a **physical nudge** — patients can feel when they're going wrong even without looking at the screen.

```
Error Level → Vibration Response:
  < 10°   → No vibration
  10°-25° → Light pulse (200ms)
  > 25°   → Strong continuous vibration
```

---

## 10. Unique Selling Points

### 🎯 Personalized Rehabilitation
Not a one-size-fits-all system. The patient's own healthy hand creates the reference — making the rehabilitation targets **biologically accurate** for each individual.

### ⚡ Real-Time Feedback
No waiting for a weekly physiotherapy session. The system provides **instant, frame-by-frame feedback** — every second of practice is guided.

### 🤖 AI + Hardware Integration
Combines the intelligence of **computer vision and machine learning** with the physicality of **embedded sensors and haptic feedback** — creating a multi-modal rehabilitation experience.

### 🎮 Gamified Recovery
Turns repetitive exercises into **engaging challenges** with scores, streaks, and progress tracking — because motivation matters as much as medicine.

### 💰 Cost-Effective
Requires only a **standard webcam** and **affordable microcontroller components** (ESP32, flex sensors, vibration motor) — total hardware cost under ₹2,000.

### 🏠 Home-Ready
Designed to work **at home** with minimal setup — no clinic visits needed for daily practice. The physiotherapist can review progress data remotely.

---

## 11. Future Scope

| Enhancement | Description |
|---|---|
| **Full Body Tracking** | Extend from hand rehabilitation to arm, shoulder, and full upper body using MediaPipe Pose |
| **Robotic Assistance** | Integrate with robotic exoskeletons for patients with severe motor loss — the system guides the robot's movement |
| **Mobile App** | Port the system to a smartphone app using the phone's camera — making it accessible to everyone |
| **Remote Monitoring** | Physiotherapists can monitor patient progress remotely through a cloud dashboard |
| **Adaptive Difficulty** | System automatically adjusts exercise difficulty based on patient's improvement rate |
| **Multi-Language Support** | Voice instructions in regional languages for wider accessibility |
| **Clinical Integration** | Export progress reports compatible with hospital EMR systems |
| **Wearable Form Factor** | Design a compact wearable glove with integrated sensors — replacing breadboard prototyping |

---

## 📊 Project Status

| Module | Status |
|--------|--------|
| MediaPipe Hand Tracking | ✅ Complete |
| Healthy Hand Reference Capture | ✅ Complete |
| ML Model Training (Random Forest) | ✅ Complete |
| Real-Time Gesture Detection | ✅ Complete |
| Comparison Engine | ✅ Complete |
| React Dashboard (Basic UI) | ✅ Complete |
| Dashboard ↔ Backend Connection | 🔄 In Progress |
| Gamification Layer | 📋 Planned |
| ESP32 + Hardware Integration | 📋 Planned |
| Haptic Feedback System | 📋 Planned |
| Mobile App | 📋 Future |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Hand Tracking | Google MediaPipe |
| Machine Learning | scikit-learn (Random Forest, SVM) |
| Computer Vision | OpenCV |
| Data Processing | NumPy, Pandas |
| Frontend | React 18 + Vite 5 |
| Styling | Vanilla CSS |
| Microcontroller | ESP32 (Arduino IDE) |
| Sensors | Flex Sensors, MPU6050 |
| Actuators | Vibration Motor |
| Data Storage | JSON (references), CSV (datasets), Joblib (models) |

---

> **Built with the belief that recovery should be personalized, guided, and accessible — not limited to clinic walls.**
