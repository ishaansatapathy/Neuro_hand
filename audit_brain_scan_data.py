"""
Print label counts after the same collect / exclude / verify steps as train_brain_scan.py.
Usage:  py -3 audit_brain_scan_data.py
        py -3 audit_brain_scan_data.py --data-profile conservative
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import train_brain_scan as t  # noqa: E402


def main() -> None:
    t._check_deps()
    ap = argparse.ArgumentParser(description="Audit brain scan training data (counts + optional PIL verify).")
    ap.add_argument(
        "--data-profile",
        type=str,
        default="full",
        choices=("full", "conservative", "originals_only"),
    )
    ap.add_argument("--no-verify-images", action="store_true")
    args = ap.parse_args()

    print(f"data_profile={args.data_profile}\n", flush=True)
    samples = t.collect_all_data(args.data_profile)
    samples = t.apply_exclude_substrings(samples, t.load_exclude_path_substrings())
    if args.no_verify_images:
        print("[images] skipping PIL verify (--no-verify-images)\n", flush=True)
    else:
        samples = t.filter_readable_images(samples)

    by_label = Counter(l for _, l in samples)
    print(f"Total images: {len(samples)}\n", flush=True)
    for lab in sorted(by_label.keys()):
        print(f"  {lab:28s} {by_label[lab]}", flush=True)


if __name__ == "__main__":
    main()
