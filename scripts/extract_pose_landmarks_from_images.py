"""
Extract MediaPipe hand landmarks from per-gesture image folders for training / guidance.

Folder layout (create under repo root):

    data/raw/hand_pose_images/
        open_hand/
            img01.jpg
            img02.png
        fist/
            ...
        point/
            ...

Usage:
    py -3 scripts/extract_pose_landmarks_from_images.py
    py -3 scripts/extract_pose_landmarks_from_images.py --input data/raw/hand_pose_images --output data/processed/pose_landmarks_from_images.csv

Requires: pip install mediapipe opencv-python
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DEFAULT_IN = BASE / "data" / "raw" / "hand_pose_images"
DEFAULT_OUT = BASE / "data" / "processed" / "pose_landmarks_from_images.csv"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def log(msg: str = "") -> None:
    print(msg, flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="MediaPipe hand landmarks from image folders.")
    ap.add_argument("--input", type=Path, default=DEFAULT_IN, help="Root folder; each subfolder name = Category label.")
    ap.add_argument("--output", type=Path, default=DEFAULT_OUT, help="Output CSV path.")
    ap.add_argument("--max-per-folder", type=int, default=0, help="Cap images per folder (0 = no cap).")
    args = ap.parse_args()

    try:
        import cv2
        import mediapipe as mp
    except ImportError:
        log("[ERROR] Need: pip install mediapipe opencv-python")
        sys.exit(1)

    root: Path = args.input
    if not root.is_dir():
        log(f"[ERROR] Input folder not found: {root}")
        log("  Create it and add subfolders per gesture, e.g. open_hand/, fist/")
        sys.exit(1)

    hands = mp.solutions.hands.Hands(
        static_image_mode=True,
        max_num_hands=1,
        model_complexity=1,
        min_detection_confidence=0.5,
    )

    rows: list[dict[str, float | str]] = []
    subdirs = sorted(p for p in root.iterdir() if p.is_dir())
    if not subdirs:
        log(f"[ERROR] No subfolders under {root}")
        sys.exit(1)

    for folder in subdirs:
        label = folder.name
        imgs = sorted(
            p for p in folder.iterdir()
            if p.suffix.lower() in IMAGE_EXTS
        )
        if args.max_per_folder and len(imgs) > args.max_per_folder:
            imgs = imgs[: args.max_per_folder]

        ok, skip = 0, 0
        for path in imgs:
            bgr = cv2.imread(str(path))
            if bgr is None:
                skip += 1
                continue
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            res = hands.process(rgb)
            if not res.multi_hand_landmarks:
                skip += 1
                continue
            lm = res.multi_hand_landmarks[0].landmark
            rel = f"{folder.name}/{path.name}"
            row: dict[str, float | str] = {"Category": label, "source_file": rel}
            for i in range(21):
                row[f"{i}_x"] = lm[i].x
                row[f"{i}_y"] = lm[i].y
            rows.append(row)
            ok += 1
        log(f"  [{label}]  extracted {ok}  skipped {skip}  ({len(imgs)} files)")

    hands.close()

    if not rows:
        log("[ERROR] No landmarks extracted. Check images show a clear hand.")
        sys.exit(1)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["Category", "source_file"] + [f"{i}_x" for i in range(21)] + [f"{i}_y" for i in range(21)]
    with args.output.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)

    log(f"\n  Saved {len(rows)} rows -> {args.output}")
    log("  Next: merge or use with train_hand_guidance / train_optimized (same column layout as data.csv).")


if __name__ == "__main__":
    main()
