
from collections import deque

try:
    import math
    import cv2
    import mediapipe as mp
    from sklearn.tree import DecisionTreeClassifier
except ImportError:
    print("Required packages are missing.")
    print("Install them with: py -3.12 -m pip install mediapipe==0.10.14 opencv-python scikit-learn")
    raise


WINDOW_NAME = "Hand Movement Quality"
MAX_HISTORY = 5


def get_mediapipe_modules():
    if not hasattr(mp, "solutions"):
        print("This MediaPipe install does not include the 'mp.solutions' API.")
        print("Recommended: Python 3.12 with mediapipe 0.10.14")
        return None, None

    return mp.solutions.hands, mp.solutions.drawing_utils


def open_webcam():
    """Try common webcam options and return the first working camera."""
    camera_options = [
        cv2.VideoCapture(0, cv2.CAP_DSHOW),
        cv2.VideoCapture(0),
    ]

    for camera in camera_options:
        if camera.isOpened():
            return camera
        camera.release()

    return None


def get_pixel_point(landmark, frame_shape):
    """Convert a normalized MediaPipe landmark into pixel coordinates."""
    frame_height, frame_width, _ = frame_shape
    return int(landmark.x * frame_width), int(landmark.y * frame_height)


def calculate_angle(point_a, point_b, point_c):
    """Calculate angle ABC in degrees."""
    ax, ay = point_a
    bx, by = point_b
    cx, cy = point_c

    vector_ba = (ax - bx, ay - by)
    vector_bc = (cx - bx, cy - by)

    magnitude_ba = math.hypot(vector_ba[0], vector_ba[1])
    magnitude_bc = math.hypot(vector_bc[0], vector_bc[1])

    if magnitude_ba == 0 or magnitude_bc == 0:
        return 0.0

    dot_product = vector_ba[0] * vector_bc[0] + vector_ba[1] * vector_bc[1]
    cosine_angle = dot_product / (magnitude_ba * magnitude_bc)
    cosine_angle = max(-1.0, min(1.0, cosine_angle))

    return math.degrees(math.acos(cosine_angle))


def distance_between_points(point_a, point_b):
    """Return the distance between two points in pixels."""
    return math.hypot(point_a[0] - point_b[0], point_a[1] - point_b[1])


def calculate_stability(history):
    """
    Measure movement stability using changes in fingertip speed.
    Lower values mean smoother and more stable movement.
    """
    if len(history) < 2:
        return 0.0

    speed_changes = []
    for index in range(1, len(history)):
        speed_changes.append(abs(history[index] - history[index - 1]))

    return sum(speed_changes) / len(speed_changes)


def extract_features(hand_landmarks, frame_shape, mp_hands, previous_tip, speed_history):
    """
    Extract simple hand movement features for the ML model.

    Features used:
    1. Index finger angle
    2. Middle finger angle
    3. Fingertip speed
    4. Movement stability
    """
    index_mcp = get_pixel_point(
        hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_MCP],
        frame_shape,
    )
    index_pip = get_pixel_point(
        hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_PIP],
        frame_shape,
    )
    index_tip = get_pixel_point(
        hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP],
        frame_shape,
    )

    middle_mcp = get_pixel_point(
        hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP],
        frame_shape,
    )
    middle_pip = get_pixel_point(
        hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_PIP],
        frame_shape,
    )
    middle_tip = get_pixel_point(
        hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP],
        frame_shape,
    )

    index_angle = calculate_angle(index_mcp, index_pip, index_tip)
    middle_angle = calculate_angle(middle_mcp, middle_pip, middle_tip)

    fingertip_speed = 0.0
    if previous_tip is not None:
        fingertip_speed = distance_between_points(index_tip, previous_tip)

    speed_history.append(fingertip_speed)
    movement_stability = calculate_stability(list(speed_history))

    feature_values = [
        round(index_angle, 2),
        round(middle_angle, 2),
        round(fingertip_speed, 2),
        round(movement_stability, 2),
    ]

    return feature_values, index_tip


def train_simple_model():
    """
    Train a very small decision tree on sample data.

    This keeps the ML part beginner-friendly.
    Label 1 = Good movement
    Label 0 = Needs improvement
    """
    training_features = [
        [85, 90, 6, 2],
        [95, 100, 8, 3],
        [105, 98, 10, 4],
        [88, 92, 7, 2],
        [100, 104, 9, 3],
        [25, 40, 2, 1],
        [170, 165, 4, 2],
        [80, 85, 28, 18],
        [90, 95, 35, 22],
        [45, 55, 3, 12],
    ]
    training_labels = [
        1,
        1,
        1,
        1,
        1,
        0,
        0,
        0,
        0,
        0,
    ]

    model = DecisionTreeClassifier(max_depth=3, random_state=42)
    model.fit(training_features, training_labels)
    return model


def label_to_text(label):
    """Convert the ML prediction into user-friendly text and color."""
    if label == 1:
        return "Good movement", (0, 200, 0)
    return "Needs improvement", (0, 0, 255)


def draw_feedback(frame, features, status_text, color):
    """Display the extracted features and model result on the video feed."""
    index_angle, middle_angle, fingertip_speed, stability = features

    feedback_lines = [
        f"Index angle: {index_angle:.1f}",
        f"Middle angle: {middle_angle:.1f}",
        f"Speed: {fingertip_speed:.1f}",
        f"Stability: {stability:.1f}",
        f"Status: {status_text}",
    ]

    y_position = 30
    for line in feedback_lines[:-1]:
        cv2.putText(
            frame,
            line,
            (10, y_position),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )
        y_position += 30

    cv2.putText(
        frame,
        feedback_lines[-1],
        (10, y_position),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        color,
        2,
    )


def main():
    mp_hands, mp_drawing = get_mediapipe_modules()
    if mp_hands is None:
        return

    model = train_simple_model()
    cap = open_webcam()

    if cap is None:
        print("Error: Could not open the webcam.")
        print("Make sure your camera is connected and not being used by another app.")
        return

    previous_tip = None
    speed_history = deque(maxlen=MAX_HISTORY)

    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    ) as hands:
        while True:
            success, frame = cap.read()
            if not success:
                print("Error: Could not read a frame from the webcam.")
                break

            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb_frame)

            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    mp_drawing.draw_landmarks(
                        frame,
                        hand_landmarks,
                        mp_hands.HAND_CONNECTIONS,
                    )

                    features, current_tip = extract_features(
                        hand_landmarks,
                        frame.shape,
                        mp_hands,
                        previous_tip,
                        speed_history,
                    )
                    previous_tip = current_tip

                    prediction = model.predict([features])[0]
                    status_text, color = label_to_text(prediction)

                    print(
                        "Features:",
                        f"index_angle={features[0]}",
                        f"middle_angle={features[1]}",
                        f"speed={features[2]}",
                        f"stability={features[3]}",
                        f"status={status_text}",
                    )

                    draw_feedback(frame, features, status_text, color)

            cv2.imshow(WINDOW_NAME, frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
