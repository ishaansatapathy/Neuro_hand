"""
Build website/public/poses/manifest.json from image files in that folder.

Maps gesture_id -> filename so the Session page can show /poses/<file>.

Put images here:
    website/public/poses/open_hand.png
    website/public/poses/fist.png
    ...

Usage:
    py -3 scripts/generate_poses_manifest.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
POSES_DIR = BASE / "website" / "public" / "poses"
MANIFEST_PATH = POSES_DIR / "manifest.json"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def main() -> None:
    POSES_DIR.mkdir(parents=True, exist_ok=True)

    by_id: dict[str, str] = {}
    files = sorted(
        p for p in POSES_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )

    for p in files:
        stem = p.stem
        m = re.match(r"^([a-z][a-z0-9_]*)", stem, re.I)
        key = m.group(1).lower() if m else stem.lower()
        if key not in by_id:
            by_id[key] = p.name

    MANIFEST_PATH.write_text(json.dumps(by_id, indent=2), encoding="utf-8")
    print(f"  Wrote {MANIFEST_PATH}  ({len(by_id)} gestures)", flush=True)
    if not by_id:
        print("  (folder empty — add PNG/JPG named like open_hand.png, fist.png, ...)", flush=True)


if __name__ == "__main__":
    main()
