"""
=============================================================================
 HAND GUIDANCE TRAINING (angles + distances) — run in a 2nd terminal
=============================================================================

 Learns gesture classes from landmark-based features (same geometry as
 train_optimized.py: joint angles, finger curl, tip-tip spread, hand span).

 Data sources (pick one):
   * data/raw/data.csv  — real landmark CSV (if present and --use-csv)
   * Synthetic poses    — jittered copies of ghost_hand.POSES (realistic dummy)

 Outputs:
   models/hand_guidance_rf.joblib
   data/processed/hand_guidance_profiles.json   ← angles/spreads per gesture for UI/voice

 Usage (repo root, while brain scan trains elsewhere):
     py -3 train_hand_guidance.py
     py -3 train_hand_guidance.py --use-csv
     py -3 train_hand_guidance.py --synthetic-only --samples 800

 Pose images -> landmarks CSV (then merge with data.csv or train on extracted file):
     py -3 scripts/extract_pose_landmarks_from_images.py

 Website reference images -> manifest for Session page:
     py -3 scripts/generate_poses_manifest.py
=============================================================================
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

from ghost_hand import POSES
from train_optimized import (
    LANDMARK_CSV,
    REHAB_LABEL_MAP,
    engineer_features,
    normalize_landmarks,
)

BASE_DIR = Path(__file__).resolve().parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
MODELS_DIR = BASE_DIR / "models"

# Short vocal cues (template layer; app can refine with live deltas later)
VOCAL_BASE: dict[str, list[str]] = {
    "open_hand": [
        "Saari ungliyaan phailao — beech mein gap rakho.",
        "Thumb ko palm se thoda door rakho.",
    ],
    "fist": [
        "Ungliyon ko dheere se band karo — tight fist.",
        "Thumb index ke upar overlap kare.",
    ],
    "point": [
        "Sirf index seedha — baaki ungliyaan curl.",
        "Index tip aage, baaki relaxed.",
    ],
}


def log(msg: str = "") -> None:
    print(msg, flush=True)


def _synthetic_from_ghost(samples_per_class: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    for cat, pts in POSES.items():
        base = np.array(pts, dtype=np.float64)
        for _ in range(samples_per_class):
            noise = rng.normal(0.0, 0.014, base.shape)
            p = np.clip(base + noise, -0.35, 0.05)
            row: dict[str, Any] = {"Category": cat}
            for i in range(21):
                row[f"{i}_x"] = float(p[i, 0])
                row[f"{i}_y"] = float(p[i, 1])
            rows.append(row)
    return pd.DataFrame(rows)


def _load_csv() -> pd.DataFrame:
    df = pd.read_csv(LANDMARK_CSV)
    df["Category"] = df["Category"].map(REHAB_LABEL_MAP).fillna(df["Category"])
    # Keep only gestures we have reference poses / labels for
    keep = set(POSES.keys())
    df = df[df["Category"].isin(keep)]
    if df.empty:
        raise ValueError("No rows left after filtering to ghost_hand POSES keys.")
    return df


def _build_xy(df: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray, LabelEncoder]:
    labels = df["Category"].astype(str)
    features = df.drop(columns=["Category"])
    features = normalize_landmarks(features)
    features = engineer_features(features)
    le = LabelEncoder()
    y = le.fit_transform(labels)
    return features, y, le


def _per_class_means(
    features: pd.DataFrame, y: np.ndarray, le: LabelEncoder,
) -> dict[str, dict[str, float]]:
    """Human-readable means on engineered columns only (unscaled)."""
    _prefixes = ("angle_", "curl_", "spread_", "wrist_dist_", "palm_", "thumb_pinky", "hand_span")
    eng_cols = [c for c in features.columns if any(c.startswith(p) for p in _prefixes)]
    if not eng_cols:
        eng_cols = features.select_dtypes(include=[np.number]).columns.tolist()
    out: dict[str, dict[str, float]] = {}
    Xe = features[eng_cols].values
    for ci, name in enumerate(le.classes_):
        m = y == ci
        if not m.any():
            continue
        mu = Xe[m].mean(axis=0)
        out[str(name)] = {eng_cols[i]: float(mu[i]) for i in range(len(eng_cols))}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Train hand guidance model (angles/distances).")
    ap.add_argument("--use-csv", action="store_true", help=f"Use {LANDMARK_CSV} if available.")
    ap.add_argument(
        "--synthetic-only",
        action="store_true",
        help="Ignore CSV; train only on jittered ghost_hand poses.",
    )
    ap.add_argument(
        "--samples",
        type=int,
        default=120,
        help="Synthetic samples per class (default 120; 25 classes = large matrix if too high).",
    )
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    t0 = time.time()
    log("\n" + "=" * 70)
    log("  HAND GUIDANCE - angles / distances / spreads")
    log("=" * 70)

    if args.use_csv and not LANDMARK_CSV.exists():
        log(f"\n[ERROR] --use-csv but file not found: {LANDMARK_CSV}\n")
        sys.exit(1)

    use_csv = args.use_csv or (LANDMARK_CSV.exists() and not args.synthetic_only)
    if use_csv and LANDMARK_CSV.exists() and not args.synthetic_only:
        try:
            raw = _load_csv()
            log(f"\n  Source: CSV  ({len(raw):,} rows)  <- {LANDMARK_CSV.name}")
            source = "csv"
        except Exception as e:
            log(f"\n  [warn] CSV load failed ({e}); falling back to synthetic.")
            raw = _synthetic_from_ghost(args.samples, args.seed)
            source = "synthetic_fallback"
    else:
        raw = _synthetic_from_ghost(args.samples, args.seed)
        log(f"\n  Source: synthetic  ({len(raw):,} rows, {args.samples}/class)  <- ghost_hand.POSES + noise")
        source = "synthetic"

    features, y, le = _build_xy(raw)
    log(f"  Features after engineering: {features.shape[1]} columns")

    X_train, X_test, y_train, y_test = train_test_split(
        features.values, y, test_size=0.2, random_state=args.seed, stratify=y,
    )
    sc = StandardScaler()
    X_train = sc.fit_transform(X_train)
    X_test = sc.transform(X_test)

    log("\n  Training RandomForest (fast, parallel-friendly)...")
    rf = RandomForestClassifier(
        n_estimators=320,
        max_depth=24,
        min_samples_split=3,
        class_weight="balanced",
        random_state=args.seed,
        n_jobs=-1,
    )
    rf.fit(X_train, y_train)
    pred = rf.predict(X_test)
    acc = accuracy_score(y_test, pred)
    f1 = f1_score(y_test, pred, average="weighted")
    log(f"  Test accuracy: {acc:.4f}  |  F1 (weighted): {f1:.4f}")
    log("\n" + classification_report(
        le.inverse_transform(y_test), le.inverse_transform(pred), zero_division=0,
    ))

    means = _per_class_means(features, y, le)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    profile = {
        "version": 1,
        "source": source,
        "gestures": {},
        "feature_columns": features.columns.tolist(),
    }
    for g in le.classes_:
        gs = str(g)
        profile["gestures"][gs] = {
            "engineered_means": means.get(gs, {}),
            "vocal_cues": VOCAL_BASE.get(gs, ["Follow the rhythm and relax between reps."]),
        }

    out_json = PROCESSED_DIR / "hand_guidance_profiles.json"
    out_json.write_text(json.dumps(profile, indent=2), encoding="utf-8")

    bundle = {
        "model": rf,
        "scaler": sc,
        "label_encoder": le,
        "feature_columns": features.columns.tolist(),
        "profiles": profile,
    }
    out_model = MODELS_DIR / "hand_guidance_rf.joblib"
    joblib.dump(bundle, out_model)

    log(f"\n{'=' * 70}")
    log("  SAVED")
    log(f"    Model   : {out_model}")
    log(f"    Profiles: {out_json}")
    log(f"  ({time.time() - t0:.1f}s)")
    log("=" * 70 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\n[stopped]")
        sys.exit(130)
