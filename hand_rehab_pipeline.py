from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, MinMaxScaler
from sklearn.svm import SVC


BASE_DIR = Path(__file__).resolve().parent
RAW_DATA_DIR = BASE_DIR / "data" / "raw"
MODELS_DIR = BASE_DIR / "models"


DATASET_PATHS = {
    "landmarks": RAW_DATA_DIR / "data.csv",
    "gesture_metadata": RAW_DATA_DIR / "hand_gestures.csv",
    "sequence_root": RAW_DATA_DIR / "DynamicGesturesDataSet" / "GestureData",
    "emg": RAW_DATA_DIR / "emg-sensor-data.csv",
}


LIKELY_LABEL_COLUMNS = [
    "label",
    "gesture",
    "gesture_type",
    "class",
    "category",
    "target",
    "movement",
    "status",
]

DROP_KEYWORDS = ["id", "time", "timestamp", "frame", "seq", "trial", "index"]


@dataclass
class PreparedData:
    dataset_name: str
    X_train: np.ndarray
    X_test: np.ndarray
    y_train: np.ndarray
    y_test: np.ndarray
    scaler: MinMaxScaler
    label_encoder: LabelEncoder
    feature_columns: list[str]
    reference_vector: np.ndarray


def load_data() -> dict[str, Any]:
    """
    Load all available CSV-based datasets.

    Returns a dictionary so each dataset can be handled separately.
    """
    datasets: dict[str, Any] = {}

    landmark_path = DATASET_PATHS["landmarks"]
    if landmark_path.exists():
        datasets["landmarks"] = pd.read_csv(landmark_path)

    metadata_path = DATASET_PATHS["gesture_metadata"]
    if metadata_path.exists():
        datasets["gesture_metadata"] = pd.read_csv(metadata_path)

    emg_path = DATASET_PATHS["emg"]
    if emg_path.exists():
        datasets["emg"] = pd.read_csv(emg_path)

    sequence_root = DATASET_PATHS["sequence_root"]
    if sequence_root.exists():
        datasets["gesture_sequences"] = load_sequence_dataset(sequence_root)

    return datasets


def load_sequence_dataset(sequence_root: Path) -> pd.DataFrame:
    """
    Convert many frame-wise gesture CSVs into one row per sequence.

    Each sequence file is summarized using mean/std/min/max so it can be
    trained with standard tabular classifiers.
    """
    sequence_rows: list[dict[str, Any]] = []

    for gesture_dir in sorted(path for path in sequence_root.iterdir() if path.is_dir()):
        for sequence_file in sorted(gesture_dir.glob("*.csv")):
            sequence_df = pd.read_csv(sequence_file)
            numeric_df = sequence_df.apply(pd.to_numeric, errors="coerce")
            numeric_df = numeric_df.dropna(axis=1, how="all").dropna(axis=0, how="any")

            if numeric_df.empty:
                continue

            row_summary: dict[str, Any] = {
                "sequence_file": sequence_file.name,
                "gesture_label": gesture_dir.name,
            }

            for column in numeric_df.columns:
                row_summary[f"{column}_mean"] = numeric_df[column].mean()
                row_summary[f"{column}_std"] = numeric_df[column].std(ddof=0)
                row_summary[f"{column}_min"] = numeric_df[column].min()
                row_summary[f"{column}_max"] = numeric_df[column].max()

            sequence_rows.append(row_summary)

    return pd.DataFrame(sequence_rows)


def find_label_column(df: pd.DataFrame) -> str:
    """Find the label column using common names or a safe fallback."""
    lowered = {column.lower(): column for column in df.columns}

    for candidate in LIKELY_LABEL_COLUMNS:
        if candidate in lowered:
            return lowered[candidate]

    object_columns = df.select_dtypes(include=["object"]).columns.tolist()
    if len(object_columns) == 1:
        return object_columns[0]

    if object_columns:
        return object_columns[-1]

    raise ValueError("Could not find a label column in the dataset.")


def drop_unnecessary_columns(df: pd.DataFrame, label_column: str) -> pd.DataFrame:
    """
    Drop obvious helper columns such as ids and timestamps.

    The label column is always kept.
    """
    columns_to_drop: list[str] = []

    for column in df.columns:
        if column == label_column:
            continue

        lowered = column.lower()
        if any(keyword in lowered for keyword in DROP_KEYWORDS):
            columns_to_drop.append(column)

    return df.drop(columns=columns_to_drop, errors="ignore")


def add_simple_landmark_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a few easy geometric features.

    These distances are simple and useful for a first rehab prototype.
    """
    feature_df = df.copy()

    point_pairs = [
        ("thumb_index", 4, 8),
        ("index_middle", 8, 12),
        ("thumb_pinky", 4, 20),
    ]

    for feature_name, point_a, point_b in point_pairs:
        coordinate_columns = []
        for suffix in ("x", "y", "z"):
            col_a = pick_coordinate_column(feature_df.columns, point_a, suffix)
            col_b = pick_coordinate_column(feature_df.columns, point_b, suffix)
            if col_a and col_b:
                coordinate_columns.append((col_a, col_b))

        if len(coordinate_columns) >= 2:
            squared_distance = np.zeros(len(feature_df), dtype=float)
            for col_a, col_b in coordinate_columns:
                squared_distance += (feature_df[col_a] - feature_df[col_b]) ** 2
            feature_df[f"distance_{feature_name}"] = np.sqrt(squared_distance)

    return feature_df


def pick_coordinate_column(columns: pd.Index, point_number: int, suffix: str) -> str | None:
    """Support both `0_x` and `P0_x` style column names."""
    candidates = [f"{point_number}_{suffix}", f"P{point_number}_{suffix}"]
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def preprocess_data(df: pd.DataFrame, dataset_name: str) -> PreparedData:
    """
    Clean, encode, split, and normalize a dataset.
    """
    working_df = df.copy()
    label_column = find_label_column(working_df)
    working_df = drop_unnecessary_columns(working_df, label_column)

    labels = working_df[label_column].astype(str)
    features = working_df.drop(columns=[label_column])

    features = features.apply(pd.to_numeric, errors="coerce")
    features = features.dropna(axis=1, how="all")

    combined_df = pd.concat([features, labels.rename(label_column)], axis=1)
    combined_df = combined_df.dropna(axis=0, how="any")

    labels = combined_df[label_column].astype(str)
    features = combined_df.drop(columns=[label_column])
    features = add_simple_landmark_features(features)

    if features.empty:
        raise ValueError(f"No usable numeric features found for dataset: {dataset_name}")

    label_encoder = LabelEncoder()
    encoded_labels = label_encoder.fit_transform(labels)

    stratify_labels = encoded_labels if len(np.unique(encoded_labels)) > 1 else None

    X_train_df, X_test_df, y_train, y_test = train_test_split(
        features,
        encoded_labels,
        test_size=0.2,
        random_state=42,
        stratify=stratify_labels,
    )

    scaler = MinMaxScaler()
    X_train = scaler.fit_transform(X_train_df)
    X_test = scaler.transform(X_test_df)

    reference_vector = X_train.mean(axis=0)

    return PreparedData(
        dataset_name=dataset_name,
        X_train=X_train,
        X_test=X_test,
        y_train=y_train,
        y_test=y_test,
        scaler=scaler,
        label_encoder=label_encoder,
        feature_columns=X_train_df.columns.tolist(),
        reference_vector=reference_vector,
    )


def train_model(prepared_data: PreparedData) -> dict[str, Any]:
    """
    Train two baseline models:
    1. Random Forest
    2. Support Vector Machine
    """
    models = {
        "random_forest": RandomForestClassifier(
            n_estimators=200,
            random_state=42,
            class_weight="balanced",
        ),
        "svm": SVC(
            kernel="rbf",
            probability=True,
            random_state=42,
        ),
    }

    trained_models: dict[str, Any] = {}
    for model_name, model in models.items():
        model.fit(prepared_data.X_train, prepared_data.y_train)
        trained_models[model_name] = model

    return trained_models


def evaluate_model(
    model_name: str,
    model: Any,
    prepared_data: PreparedData,
) -> dict[str, Any]:
    """Evaluate a trained model with clear printed output."""
    predictions = model.predict(prepared_data.X_test)
    accuracy = accuracy_score(prepared_data.y_test, predictions)
    cm = confusion_matrix(prepared_data.y_test, predictions)

    decoded_true = prepared_data.label_encoder.inverse_transform(prepared_data.y_test)
    decoded_predictions = prepared_data.label_encoder.inverse_transform(predictions)

    print(f"\n{'=' * 60}")
    print(f"Dataset: {prepared_data.dataset_name}")
    print(f"Model: {model_name}")
    print(f"Accuracy: {accuracy:.4f}")
    print("Confusion Matrix:")
    print(cm)
    print("Classification Report:")
    print(
        classification_report(
            decoded_true,
            decoded_predictions,
            zero_division=0,
        )
    )

    return {
        "model_name": model_name,
        "accuracy": accuracy,
        "confusion_matrix": cm,
    }


def summarize_emg_data(emg_df: pd.DataFrame) -> pd.DataFrame:
    """Create a small numeric summary for optional EMG inspection."""
    numeric_emg = emg_df.apply(pd.to_numeric, errors="coerce").dropna(axis=0, how="any")
    if numeric_emg.empty:
        return pd.DataFrame()

    summary = numeric_emg.agg(["mean", "std", "min", "max"]).T
    return summary.round(4)


def choose_best_model(
    trained_models: dict[str, Any],
    evaluation_results: list[dict[str, Any]],
) -> tuple[str, Any]:
    """Pick the model with the highest test accuracy."""
    best_result = max(evaluation_results, key=lambda item: item["accuracy"])
    best_model_name = best_result["model_name"]
    return best_model_name, trained_models[best_model_name]


def save_model(
    model_name: str,
    model: Any,
    prepared_data: PreparedData,
    dataset_name: str,
) -> Path:
    """Save the selected model together with preprocessing objects."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    output_path = MODELS_DIR / f"{dataset_name}_{model_name}_pipeline.joblib"
    bundle = {
        "model_name": model_name,
        "model": model,
        "scaler": prepared_data.scaler,
        "label_encoder": prepared_data.label_encoder,
        "feature_columns": prepared_data.feature_columns,
        "reference_vector": prepared_data.reference_vector,
        "dataset_name": dataset_name,
    }
    joblib.dump(bundle, output_path)
    return output_path


def align_live_features(
    live_landmarks: np.ndarray | list[float],
    feature_columns: list[str],
) -> pd.DataFrame:
    """
    Convert a live landmark array into the same feature layout used in training.

    Expected input:
    - 42 values for x/y landmarks
    - or 63 values for x/y/z landmarks
    """
    landmarks = np.asarray(live_landmarks, dtype=float).flatten()

    if landmarks.size not in (42, 63):
        raise ValueError("Live landmarks must contain either 42 or 63 numeric values.")

    dims = 2 if landmarks.size == 42 else 3
    column_names: list[str] = []

    for point_number in range(21):
        column_names.extend([f"{point_number}_x", f"{point_number}_y"])
        if dims == 3:
            column_names.append(f"{point_number}_z")

    live_df = pd.DataFrame([landmarks], columns=column_names)
    live_df = add_simple_landmark_features(live_df)

    for column in feature_columns:
        if column not in live_df.columns:
            live_df[column] = 0.0

    return live_df[feature_columns]


def predict_live_movement(
    live_landmarks: np.ndarray | list[float],
    saved_bundle_path: str | Path,
    deviation_threshold: float | None = None,
) -> dict[str, Any]:
    """
    Basic real-time placeholder for live prediction.

    If a deviation threshold is provided, the function can flag a movement as
    incorrect when it is too far from the average training pattern.
    """
    bundle = joblib.load(saved_bundle_path)
    live_df = align_live_features(live_landmarks, bundle["feature_columns"])
    scaled_features = bundle["scaler"].transform(live_df)

    encoded_prediction = bundle["model"].predict(scaled_features)[0]
    prediction_label = bundle["label_encoder"].inverse_transform([encoded_prediction])[0]

    result = {
        "predicted_label": prediction_label,
        "movement_quality": "correct",
        "deviation_score": None,
    }

    if deviation_threshold is not None:
        deviation_score = float(
            np.mean(np.abs(scaled_features[0] - bundle["reference_vector"]))
        )
        result["deviation_score"] = round(deviation_score, 4)
        if deviation_score > deviation_threshold:
            result["movement_quality"] = "incorrect"

    return result


def run_training_pipeline() -> None:
    """Run the full training flow from loading to saving."""
    datasets = load_data()

    if "landmarks" not in datasets:
        raise FileNotFoundError("Landmark dataset not found. Expected file: data/raw/data.csv")

    print("Loaded datasets:")
    for dataset_name, dataset_value in datasets.items():
        if isinstance(dataset_value, pd.DataFrame):
            print(f"- {dataset_name}: {dataset_value.shape[0]} rows x {dataset_value.shape[1]} columns")

    prepared_datasets: list[PreparedData] = []

    landmark_prepared = preprocess_data(datasets["landmarks"], dataset_name="landmarks")
    prepared_datasets.append(landmark_prepared)

    if "gesture_sequences" in datasets and not datasets["gesture_sequences"].empty:
        sequence_prepared = preprocess_data(
            datasets["gesture_sequences"].rename(columns={"gesture_label": "label"}),
            dataset_name="gesture_sequences",
        )
        prepared_datasets.append(sequence_prepared)

    if "emg" in datasets:
        emg_summary = summarize_emg_data(datasets["emg"])
        if not emg_summary.empty:
            print("\nOptional EMG summary:")
            print(emg_summary)

    for prepared_data in prepared_datasets:
        trained_models = train_model(prepared_data)
        evaluation_results: list[dict[str, Any]] = []

        for model_name, model in trained_models.items():
            result = evaluate_model(model_name, model, prepared_data)
            evaluation_results.append(result)

        best_model_name, best_model = choose_best_model(trained_models, evaluation_results)
        saved_path = save_model(
            model_name=best_model_name,
            model=best_model,
            prepared_data=prepared_data,
            dataset_name=prepared_data.dataset_name,
        )

        print(f"Best model for {prepared_data.dataset_name}: {best_model_name}")
        print(f"Saved to: {saved_path}")


if __name__ == "__main__":
    run_training_pipeline()
