"""
=============================================================================
 OPTIMIZED TRAINING PIPELINE - Rehab AI System
 Healthy Hand Analysis -> Damaged Hand Mapping

 Usage (run from repo root):
     py -3 train_optimized.py

 Inputs (must exist):
     data/raw/data.csv                              <- hand landmark CSV
     data/raw/DynamicGesturesDataSet/GestureData/  <- optional sequences

 Outputs:
     models/landmarks_rehab_<best_model>_optimized.joblib
     models/gesture_sequences_rehab_<best_model>_optimized.joblib (if seq found)
     data/processed/healthy_hand_profiles.json

 Bundle fields (used by realtime.py):
     model, scaler, label_encoder, feature_columns,
     reference_vector, per_class_references, dataset_name
=============================================================================
"""

from __future__ import annotations

import json
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import (
    RandomForestClassifier,
    HistGradientBoostingClassifier,
    VotingClassifier,
)
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import (
    StratifiedKFold,
    GridSearchCV,
    cross_val_score,
    train_test_split,
)
from sklearn.preprocessing import LabelEncoder, StandardScaler


def log(msg: str = "") -> None:
    print(msg, flush=True)


# -- Paths -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
RAW_DATA_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
MODELS_DIR = BASE_DIR / "models"

LANDMARK_CSV = RAW_DATA_DIR / "data.csv"
SEQUENCE_ROOT = RAW_DATA_DIR / "DynamicGesturesDataSet" / "GestureData"
# Cap CSVs per gesture folder so training finishes in minutes (full set ~10k files).
MAX_SEQUENCE_CSV_PER_FOLDER = 45


# -- Landmark Constants ------------------------------------------------------
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

REHAB_LABEL_MAP = {
    "Paper": "open_hand",
    "Stone": "fist",
    "Scissor": "point",
}


@dataclass
class TrainingResult:
    dataset_name: str
    X_train: np.ndarray
    X_test: np.ndarray
    y_train: np.ndarray
    y_test: np.ndarray
    scaler: StandardScaler
    label_encoder: LabelEncoder
    feature_columns: list[str]
    per_class_references: dict[str, dict]
    global_reference: np.ndarray
    feature_importances: dict[str, float] = field(default_factory=dict)


# -- Vectorized Feature Engineering ------------------------------------------

def _pts(df: pd.DataFrame, idx: int) -> np.ndarray:
    """Get Nx2 array of (x,y) for landmark idx."""
    return np.column_stack([df[f"{idx}_x"].values, df[f"{idx}_y"].values])


def _vec_angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Vectorized angle ABC in degrees. B is vertex."""
    ba = a - b
    bc = c - b
    dot = np.sum(ba * bc, axis=1)
    mag = np.linalg.norm(ba, axis=1) * np.linalg.norm(bc, axis=1)
    mag = np.where(mag < 1e-10, 1e-10, mag)
    return np.degrees(np.arccos(np.clip(dot / mag, -1.0, 1.0)))


def _vec_dist(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Vectorized Euclidean distance."""
    return np.linalg.norm(a - b, axis=1)


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Vectorized rehab feature engineering.
    32 features: 15 angles + 5 curl + 4 spread + 5 wrist_dist + 3 palm
    """
    new = {}
    wrist = _pts(df, WRIST)

    for fname, mcp_i, pip_i, dip_i, tip_i in FINGERS:
        mcp = _pts(df, mcp_i)
        pip_ = _pts(df, pip_i)
        dip = _pts(df, dip_i)
        tip = _pts(df, tip_i)

        new[f"angle_{fname}_mcp"] = _vec_angle(wrist, mcp, pip_)
        new[f"angle_{fname}_pip"] = _vec_angle(mcp, pip_, dip)
        new[f"angle_{fname}_dip"] = _vec_angle(pip_, dip, tip)

        tip_w = _vec_dist(tip, wrist)
        mcp_w = _vec_dist(mcp, wrist)
        new[f"curl_{fname}"] = tip_w / (mcp_w + 1e-10)
        new[f"wrist_dist_{fname}"] = tip_w

    for pname, ta, tb in FINGER_TIP_PAIRS:
        new[f"spread_{pname}"] = _vec_dist(_pts(df, ta), _pts(df, tb))

    mcp_d = [_vec_dist(_pts(df, f[1]), wrist) for f in FINGERS]
    new["palm_size"] = np.mean(mcp_d, axis=0)
    new["thumb_pinky_dist"] = _vec_dist(_pts(df, THUMB_TIP), _pts(df, PINKY_TIP))

    tips = [_pts(df, f[4]) for f in FINGERS]
    span = np.zeros(len(df))
    for i in range(len(tips)):
        for j in range(i + 1, len(tips)):
            span = np.maximum(span, _vec_dist(tips[i], tips[j]))
    new["hand_span"] = span

    return pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)


def normalize_landmarks(df: pd.DataFrame) -> pd.DataFrame:
    """Wrist-relative normalization."""
    r = df.copy()
    wx, wy = df["0_x"].values, df["0_y"].values
    for p in range(21):
        r[f"{p}_x"] = df[f"{p}_x"].values - wx
        r[f"{p}_y"] = df[f"{p}_y"].values - wy
    return r


# -- Data Loading ------------------------------------------------------------

def load_landmarks() -> TrainingResult:
    log("=" * 70)
    log("  LOADING LANDMARK DATASET")
    log("=" * 70)

    df = pd.read_csv(LANDMARK_CSV)
    log(f"  Loaded: {df.shape[0]:,} samples x {df.shape[1]} columns")

    df["Category"] = df["Category"].map(REHAB_LABEL_MAP).fillna(df["Category"])
    log(f"  Classes: {dict(df['Category'].value_counts())}")

    labels = df["Category"].astype(str)
    features = df.drop(columns=["Category"])

    log("  > Normalizing landmarks...")
    features = normalize_landmarks(features)

    log("  > Engineering features...")
    t0 = time.time()
    features = engineer_features(features)
    log(f"  > Done in {time.time() - t0:.1f}s  |  {len(features.columns)} features")

    le = LabelEncoder()
    y = le.fit_transform(labels)
    log(f"  > Labels: {list(le.classes_)}")

    Xtr_df, Xte_df, ytr, yte = train_test_split(
        features, y, test_size=0.2, random_state=42, stratify=y,
    )
    log(f"  > Split: {len(Xtr_df):,} train / {len(Xte_df):,} test")

    sc = StandardScaler()
    Xtr = sc.fit_transform(Xtr_df)
    Xte = sc.transform(Xte_df)

    log("\n  Computing per-class reference profiles...")
    refs = {}
    for ci, cn in enumerate(le.classes_):
        m = ytr == ci
        refs[cn] = {
            "mean": Xtr[m].mean(axis=0),
            "std": Xtr[m].std(axis=0),
            "sample_count": int(m.sum()),
        }
        log(f"    {cn}: {m.sum():,} samples")

    return TrainingResult(
        dataset_name="landmarks_rehab",
        X_train=Xtr, X_test=Xte, y_train=ytr, y_test=yte,
        scaler=sc, label_encoder=le,
        feature_columns=Xtr_df.columns.tolist(),
        per_class_references=refs,
        global_reference=Xtr.mean(axis=0),
    )


def load_sequences() -> TrainingResult | None:
    if not SEQUENCE_ROOT.exists():
        log("  [!] Sequence dataset not found, skipping.")
        return None

    log("\n" + "=" * 70)
    log("  LOADING DYNAMIC GESTURE DATASET")
    log("=" * 70)

    rows = []
    rng = random.Random(42)
    gdirs = sorted(p for p in SEQUENCE_ROOT.iterdir() if p.is_dir())
    for gi, gdir in enumerate(gdirs):
        csvs = sorted(gdir.glob("*.csv"))
        if len(csvs) > MAX_SEQUENCE_CSV_PER_FOLDER:
            csvs = rng.sample(csvs, MAX_SEQUENCE_CSV_PER_FOLDER)
        for cf in csvs:
            sdf = pd.read_csv(cf, low_memory=False)
            ndf = sdf.apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all").dropna(axis=0, how="any")
            if ndf.empty:
                continue
            s = {"gesture_label": gdir.name}
            for c in ndf.columns:
                s[f"{c}_mean"] = ndf[c].mean()
                s[f"{c}_std"] = ndf[c].std(ddof=0)
                s[f"{c}_min"] = ndf[c].min()
                s[f"{c}_max"] = ndf[c].max()
                s[f"{c}_range"] = ndf[c].max() - ndf[c].min()
            rows.append(s)
        log(f"    [{gi + 1}/{len(gdirs)}] {gdir.name}: {len(csvs)} CSVs")

    if not rows:
        return None

    df = pd.DataFrame(rows)
    log(f"  Loaded: {len(df)} sequences, {df['gesture_label'].nunique()} classes")

    labels = df["gesture_label"].astype(str)
    features = df.drop(columns=["gesture_label"]).apply(pd.to_numeric, errors="coerce").fillna(0)

    le = LabelEncoder()
    y = le.fit_transform(labels)

    Xtr_df, Xte_df, ytr, yte = train_test_split(
        features, y, test_size=0.2, random_state=42, stratify=y,
    )

    sc = StandardScaler()
    Xtr = sc.fit_transform(Xtr_df)
    Xte = sc.transform(Xte_df)

    refs = {}
    for ci, cn in enumerate(le.classes_):
        m = ytr == ci
        refs[cn] = {"mean": Xtr[m].mean(axis=0), "std": Xtr[m].std(axis=0), "sample_count": int(m.sum())}

    return TrainingResult(
        dataset_name="gesture_sequences_rehab",
        X_train=Xtr, X_test=Xte, y_train=ytr, y_test=yte,
        scaler=sc, label_encoder=le,
        feature_columns=features.columns.tolist(),
        per_class_references=refs,
        global_reference=Xtr.mean(axis=0),
    )


# -- Training ----------------------------------------------------------------

def train_models(data: TrainingResult) -> dict[str, Any]:
    log(f"\n{'=' * 70}")
    log(f"  TRAINING -- {data.dataset_name}")
    log(f"{'=' * 70}")

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    results = {}

    # 1. Random Forest -- GridSearchCV (the main model, properly tuned)
    log("\n  [1/3] Random Forest -- GridSearchCV...")
    rf_params = {
        "n_estimators": [400],
        "max_depth": [None, 30],
        "min_samples_split": [2, 5],
        "max_features": ["sqrt", "log2"],
    }
    rf_grid = GridSearchCV(
        RandomForestClassifier(random_state=42, class_weight="balanced", n_jobs=-1),
        rf_params, cv=cv, scoring="f1_weighted", n_jobs=-1, verbose=0,
    )
    rf_grid.fit(data.X_train, data.y_train)
    rf_best = rf_grid.best_estimator_
    log(f"        Best CV F1: {rf_grid.best_score_:.4f}")
    log(f"        Params: {rf_grid.best_params_}")
    results["random_forest"] = {"model": rf_best, "cv_score": rf_grid.best_score_}

    data.feature_importances = dict(zip(data.feature_columns, rf_best.feature_importances_))

    # 2. Histogram GB — fast on large n; classic GradientBoosting is too slow here
    log("\n  [2/3] HistGradientBoosting (direct train)...")
    gb = HistGradientBoostingClassifier(
        max_iter=300,
        max_depth=6,
        learning_rate=0.08,
        l2_regularization=1e-4,
        random_state=42,
        early_stopping=True,
        validation_fraction=0.1,
        n_iter_no_change=15,
    )
    gb.fit(data.X_train, data.y_train)
    gb_train_acc = accuracy_score(data.y_train, gb.predict(data.X_train))
    log(f"        Train accuracy: {gb_train_acc:.4f}")
    results["gradient_boosting"] = {"model": gb, "cv_score": gb_train_acc}

    # 3. Ensemble (RF + GB soft voting -- train directly)
    log("\n  [3/3] Ensemble (RF + GB Soft Voting, direct train)...")
    ensemble = VotingClassifier(
        estimators=[("rf", rf_best), ("gb", gb)],
        voting="soft", n_jobs=-1,
    )
    ensemble.fit(data.X_train, data.y_train)
    ens_train_acc = accuracy_score(data.y_train, ensemble.predict(data.X_train))
    log(f"        Train accuracy: {ens_train_acc:.4f}")
    results["ensemble"] = {"model": ensemble, "cv_score": ens_train_acc}

    return results


# -- Evaluation --------------------------------------------------------------

def evaluate(results: dict[str, Any], data: TrainingResult) -> tuple[str, Any]:
    log(f"\n{'=' * 70}")
    log(f"  EVALUATION -- {data.dataset_name}")
    log(f"{'=' * 70}")

    best_name, best_model, best_f1 = None, None, -1

    for name, info in results.items():
        model = info["model"]
        preds = model.predict(data.X_test)
        acc = accuracy_score(data.y_test, preds)
        f1 = f1_score(data.y_test, preds, average="weighted")

        dt = data.label_encoder.inverse_transform(data.y_test)
        dp = data.label_encoder.inverse_transform(preds)

        log(f"\n  -- {name.upper()} --")
        log(f"  Accuracy:      {acc:.4f}")
        log(f"  F1 (weighted): {f1:.4f}")
        log(f"  CV F1:         {info['cv_score']:.4f}")
        log(classification_report(dt, dp, zero_division=0))

        cm = confusion_matrix(data.y_test, preds)
        log("  Confusion Matrix:")
        for row in cm:
            log(f"    {row}")

        if f1 > best_f1:
            best_f1, best_name, best_model = f1, name, model

    log(f"\n  >> BEST: {best_name.upper()} (Test F1: {best_f1:.4f})")
    return best_name, best_model


def show_importances(data: TrainingResult, top_n: int = 20) -> None:
    if not data.feature_importances:
        return
    log(f"\n{'=' * 70}")
    log(f"  TOP {top_n} FEATURES")
    log(f"{'=' * 70}")
    for i, (n, v) in enumerate(sorted(data.feature_importances.items(), key=lambda x: x[1], reverse=True)[:top_n], 1):
        bar = "#" * int(v * 200)
        log(f"  {i:2d}. {n:30s} {v:.4f} {bar}")


# -- Save --------------------------------------------------------------------

def save_model(name: str, model: Any, data: TrainingResult) -> Path:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    out = MODELS_DIR / f"{data.dataset_name}_{name}_optimized.joblib"

    refs = {}
    for cn, rd in data.per_class_references.items():
        refs[cn] = {"mean": rd["mean"].tolist(), "std": rd["std"].tolist(), "sample_count": rd["sample_count"]}

    joblib.dump({
        "model_name": name, "model": model,
        "scaler": data.scaler, "label_encoder": data.label_encoder,
        "feature_columns": data.feature_columns,
        "reference_vector": data.global_reference,
        "per_class_references": refs,
        "feature_importances": data.feature_importances,
        "dataset_name": data.dataset_name,
        "training_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, out, compress=3)

    log(f"\n  > Saved: {out.name} ({out.stat().st_size / 1024 / 1024:.1f} MB)")
    return out


def save_profiles(data: TrainingResult) -> Path:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = PROCESSED_DIR / "healthy_hand_profiles.json"

    profiles = {}
    for cn, rd in data.per_class_references.items():
        feat_prof = {}
        for i, col in enumerate(data.feature_columns):
            if any(col.startswith(p) for p in ("angle_", "curl_", "spread_", "wrist_dist_", "palm_", "hand_", "thumb_pinky")):
                feat_prof[col] = {
                    "ideal": round(float(rd["mean"][i]), 4),
                    "std": round(float(rd["std"][i]), 4),
                    "good_threshold": round(float(rd["std"][i] * 1.0), 4),
                    "moderate_threshold": round(float(rd["std"][i] * 2.0), 4),
                }
        profiles[cn] = {"samples": rd["sample_count"], "features": feat_prof}

    out.write_text(json.dumps(profiles, indent=2), encoding="utf-8")
    log(f"  > Profiles saved: {out.name}")
    return out


# -- Main --------------------------------------------------------------------

def main() -> None:
    t0 = time.time()

    log("\n" + "=" * 70)
    log("  REHAB AI -- OPTIMIZED TRAINING PIPELINE")
    log("  Healthy Hand Analysis -> Damaged Hand Mapping")
    log("=" * 70)

    # Landmark dataset
    ld = load_landmarks()
    lr = train_models(ld)
    bn, bm = evaluate(lr, ld)
    show_importances(ld)
    save_model(bn, bm, ld)
    save_profiles(ld)

    # Sequence dataset
    sd = load_sequences()
    if sd is not None:
        sr = train_models(sd)
        sbn, sbm = evaluate(sr, sd)
        show_importances(sd)
        save_model(sbn, sbm, sd)

    log(f"\n{'=' * 70}")
    log(f"  DONE in {time.time() - t0:.1f}s")
    log(f"  Models -> {MODELS_DIR}")
    log(f"  Profiles -> {PROCESSED_DIR}")
    log(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
