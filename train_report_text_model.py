"""
Train a small TF-IDF + LogisticRegression model on OCR text from data/processed/reports/manifest.jsonl

Labels are weak / rule-based from keywords (demo only, not clinical ground truth).

Usage:  py -3 train_report_text_model.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
MANIFEST = BASE / "data" / "processed" / "reports" / "manifest.jsonl"
MODEL_DIR = BASE / "models"


def weak_label(text: str) -> str:
    """Coarse categories from English (+ common misspellings) medical strings."""
    t = text.lower()
    t = re.sub(r"\s+", " ", t)

    # Order matters: first match wins (broad → specific-ish)
    if any(
        k in t
        for k in (
            "stroke",
            "ischem",
            "hemorrh",
            "infarct",
            "acute infarct",
            "cva",
            "territory",
            "mca",
        )
    ):
        return "cerebrovascular"
    if any(k in t for k in ("meningioma", "glioma", "mass effect", "space occupying", "tumor", "tumour")):
        return "neoplasm"
    if any(k in t for k in ("multiple sclerosis", "demyelin", "demyl", "mse ", "ms ")):
        return "demyelinating"
    if any(k in t for k in ("alzheimer", "atrophy", "dementia", "neurodegen")):
        return "degenerative"
    if any(k in t for k in ("epilepsy", "seizure")):
        return "seizure_related"
    if len(t.strip()) < 15:
        return "sparse_text"
    return "general_other"


def main() -> None:
    if not MANIFEST.is_file():
        print(f"[ERROR] Run extract_report_data.py first. Missing: {MANIFEST}", flush=True)
        sys.exit(1)

    rows: list[dict] = []
    with MANIFEST.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))

    texts = [(r.get("text") or "").strip() for r in rows]
    paths = [r.get("path", "") for r in rows]
    labels = [weak_label(tx) for tx in texts]

    from collections import Counter

    cnt = Counter(labels)
    print("Weak label distribution:", dict(cnt), flush=True)

    # Need at least 2 classes for meaningful classifier
    unique_valid = [c for c, n in cnt.items() if n >= 1]
    if len(unique_valid) < 2:
        print("[WARN] Fewer than 2 label buckets — saving dummy metadata only.", flush=True)

    import joblib
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import classification_report
    from sklearn.model_selection import train_test_split

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    X_raw = texts
    y = np.array(labels)

    # Stratify only if each class has >=2 samples in train split — fallback
    strat = y if len(set(labels)) > 1 and min(cnt.values()) >= 2 else None
    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X_raw, y, test_size=0.25, random_state=42, stratify=strat
        )
    except ValueError:
        X_train, X_test, y_train, y_test = train_test_split(
            X_raw, y, test_size=0.25, random_state=42
        )

    vec = TfidfVectorizer(
        max_features=1200,
        ngram_range=(1, 2),
        min_df=1,
        max_df=0.95,
    )
    Xtr = vec.fit_transform(X_train)
    Xte = vec.transform(X_test)

    clf = LogisticRegression(max_iter=300, class_weight="balanced", random_state=42)
    clf.fit(Xtr, y_train)

    pred = clf.predict(Xte)
    report = classification_report(y_test, pred, zero_division=0)
    print("\nValidation (Held-out weak labels):\n", report, flush=True)

    joblib.dump(vec, MODEL_DIR / "report_text_vectorizer.joblib")
    joblib.dump(clf, MODEL_DIR / "report_text_clf.joblib")

    meta = {
        "n_docs": len(rows),
        "labels_seen": list(cnt.keys()),
        "weak_label_counts": dict(cnt),
        "vectorizer": "TfidfVectorizer",
        "classifier": "LogisticRegression",
        "paths_preview": paths[:5],
        "note": "Weak labels from keywords — for demo pipeline only.",
    }
    (MODEL_DIR / "report_text_model_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"\nSaved: {MODEL_DIR / 'report_text_clf.joblib'}", flush=True)


if __name__ == "__main__":
    main()
