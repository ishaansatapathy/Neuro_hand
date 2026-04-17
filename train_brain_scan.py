"""
=============================================================================
 BRAIN SCAN IMAGE CLASSIFIER — Training Pipeline v2
 Post-Stroke Rehabilitation AI System

 Usage:  py -3 train_brain_scan.py
         py -3 train_brain_scan.py --quick   # ~1 hour (subsample + fewer epochs)
         py -3 train_brain_scan.py --medium  # ~75% of full run — between quick & full (~4–8h CPU typical)
         py -3 train_brain_scan.py --resume models/brain_scan_train_checkpoint.pt
             # continue after Ctrl+C; finetune e.g. 7/25 = resume with ft_epochs_completed=6 in ckpt
         py -3 train_brain_scan.py --data-profile conservative
             # fewer merged sources → often cleaner labels before long runs

 Improvements over v1:
   * Merges Hemorrhage/Ischemia/Normal from train/ and test/ dirs
   * Includes dataset/Dataset_MRI_Folder and dataset/Stroke_classification (Haemorrhagic/Ischemic -> Stroke)
   * Deduplicates by resolved file path when the same image appears under multiple roots
   * Maps Hemorrhage+Ischemia -> Stroke subtypes for richer Stroke class
   * WeightedRandomSampler for class-balanced training
   * Stratified train/val split (sklearn)
   * Stronger augmentation (RandomResizedCrop, Affine, Blur, Erasing)
   * Class-weighted CrossEntropyLoss
   * EfficientNet-B0/B1/B2 with dropout head, focal loss, optional Mixup

 Saved artifacts:
   models/brain_scan_classifier.pt
   models/brain_scan_classifier_meta.json
   models/brain_scan_train_checkpoint.pt  (periodic; resume with --resume)
   (legacy names brain_scan_efficientnet_b0.* still supported by server if present)
=============================================================================
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from torch.utils.data import Dataset

# Leave TQDM enabled by default so you see per-batch progress; set TQDM_DISABLE=1 to silence.
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR   = Path(__file__).resolve().parent
RAW_DIR    = BASE_DIR / "data" / "raw"
MODELS_DIR = BASE_DIR / "models"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
# Optional: lines = substrings; if path contains line, image is excluded (see data/brain_scan_exclude_paths.txt)
EXCLUDE_PATHS_FILE = BASE_DIR / "data" / "brain_scan_exclude_paths.txt"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

IMG_SIZE       = 256
BATCH_SIZE     = 24
VAL_SPLIT      = 0.15
RANDOM_SEED    = 42
HEAD_EPOCHS    = 5
MAX_EPOCHS     = 25
LR_HEAD        = 3e-3
LR_FINETUNE    = 5e-5
WEIGHT_DECAY   = 1e-4
PATIENCE       = 7
FOCAL_GAMMA    = 2.0
MIXUP_ALPHA    = 0.35
MIXUP_PROB     = 0.55
CLASSIFIER_DROPOUT = 0.35

# --quick: target ~1 hour on CPU (subsample + fewer epochs)
QUICK_HEAD_EPOCHS  = 3
QUICK_MAX_EPOCHS   = 12
QUICK_PATIENCE     = 4
QUICK_MAX_PER_CLASS = 2000

# --medium: ~75% of full default budget (epochs/patience vs MAX_EPOCHS/HEAD_EPOCHS/PATIENCE); more data than quick
MEDIUM_HEAD_EPOCHS    = 4
MEDIUM_MAX_EPOCHS     = 19
MEDIUM_PATIENCE       = 6
MEDIUM_MAX_PER_CLASS  = 5000

TRAIN_CKPT_VERSION = 1
DEFAULT_TRAIN_CHECKPOINT = MODELS_DIR / "brain_scan_train_checkpoint.pt"


def log(msg: str = "") -> None:
    print(msg, flush=True)


def _load_image_rgb(path: Path):
    """Load raster as RGB; avoids PIL UserWarning on palette+transparency PNGs."""
    from PIL import Image

    im = Image.open(path)
    if im.mode == "P":
        im = im.convert("RGBA")
    return im.convert("RGB")


class ScanDataset(Dataset):
    """Top-level class so DataLoader workers can pickle it (nested classes fail on Windows)."""

    def __init__(self, samples: list[tuple[Path, str]], tf: Any, label_to_idx: dict[str, int]):
        self.samples = samples
        self.tf = tf
        self.label_to_idx = label_to_idx

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        path, label = self.samples[idx]
        img = _load_image_rgb(path)
        return self.tf(img), self.label_to_idx[label]


def build_classifier_model(arch: str, n_classes: int):
    """EfficientNet-B0/B1/B2 with dropout head (must match server load)."""
    import torch
    from torchvision import models

    arch = arch.lower().strip()
    if arch == "efficientnet_b2":
        m = models.efficientnet_b2(weights=models.EfficientNet_B2_Weights.IMAGENET1K_V1)
    elif arch == "efficientnet_b1":
        m = models.efficientnet_b1(weights=models.EfficientNet_B1_Weights.IMAGENET1K_V1)
    else:
        m = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1)
    in_features = m.classifier[-1].in_features
    m.classifier = torch.nn.Sequential(
        torch.nn.Dropout(p=CLASSIFIER_DROPOUT, inplace=True),
        torch.nn.Linear(in_features, n_classes),
    )
    return m


# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------
def _check_deps() -> None:
    missing = []
    for pkg in ("torch", "torchvision", "PIL", "sklearn"):
        try:
            __import__(pkg)
        except ModuleNotFoundError:
            missing.append(pkg)
    if missing:
        log("\n[ERROR] Missing packages: " + ", ".join(missing))
        log("Install with:  pip install -r requirements-train.txt\n")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Data collection — merge all available brain scan sources
# ---------------------------------------------------------------------------
def _scan_folder(folder: Path, label: str) -> list[tuple[Path, str]]:
    """Collect all images from folder, assign label."""
    if not folder.exists():
        return []
    imgs = [p for p in folder.rglob("*") if p.suffix.lower() in IMAGE_EXTS]
    return [(p, label) for p in imgs]


def collect_all_data(data_profile: str = "full") -> list[tuple[Path, str]]:
    """
    Merge brain scan sources into one pool.

    data_profile:
      full          — all sources (legacy; noisy if merged Kaggle-style folders disagree).
      conservative  — 7 class dirs + dataset MRI trees only (drops train/test/External_test merges).
      originals_only — only data/raw/<ClassName>/ (single labeling scheme; smallest but cleanest).
    """
    samples: list[tuple[Path, str]] = []

    # Source 1: Original 7 class directories (always)
    original_classes = [
        "Alzheimer", "Stroke", "Normal", "Multiple Sclerosis",
        "Meningioma", "Epilepsy", "Cerebral Calcinosi",
    ]
    for cls in original_classes:
        found = _scan_folder(RAW_DIR / cls, cls)
        if found:
            log(f"  [class dir] {cls}: {len(found)} images")
        samples.extend(found)

    merge_map = {
        "Hemorrhage": "Stroke",
        "Ischemia":   "Stroke",
        "Normal":     "Normal",
    }

    if data_profile == "full":
        # Source 2: train/ and test/ brain-related subfolders
        for split_dir_name in ("train", "test"):
            split_dir = RAW_DIR / split_dir_name
            if not split_dir.exists():
                continue
            for subfolder, target_label in merge_map.items():
                found = _scan_folder(split_dir / subfolder, target_label)
                if found:
                    log(f"  [{split_dir_name}/{subfolder}] -> {target_label}: {len(found)} images")
                samples.extend(found)

        # Source 3: External_test
        ext_dir = RAW_DIR / "External_test"
        if ext_dir.exists():
            for sub in sorted(ext_dir.iterdir()):
                if not sub.is_dir():
                    continue
                target = merge_map.get(sub.name, sub.name)
                if target in set(c for _, c in samples):
                    found = _scan_folder(sub, target)
                    if found:
                        log(f"  [External_test/{sub.name}] -> {target}: {len(found)} images")
                    samples.extend(found)

    elif data_profile == "conservative":
        log("  [data profile] Skipping train/, test/, External_test/ (merged sources).")

    if data_profile == "originals_only":
        log("  [data profile] originals_only - only data/raw/<ClassName>/ folders.")
    elif data_profile in ("full", "conservative"):
        # Source 4: Extra MRI trees under data/raw/dataset/
        mri_subfolder_to_label = {
            "Haemorrhagic": "Stroke",
            "Hemorrhagic": "Stroke",
            "Ischemic": "Stroke",
            "Ischemia": "Stroke",
            "Normal": "Normal",
        }
        for rel in ("dataset/Dataset_MRI_Folder", "dataset/Stroke_classification"):
            mri_root = RAW_DIR.joinpath(*rel.split("/"))
            if not mri_root.is_dir():
                continue
            for sub in sorted(mri_root.iterdir()):
                if not sub.is_dir():
                    continue
                target = mri_subfolder_to_label.get(sub.name)
                if target is None:
                    continue
                found = _scan_folder(sub, target)
                if found:
                    log(f"  [{rel}/{sub.name}] -> {target}: {len(found)} images")
                samples.extend(found)

    before = len(samples)
    seen_paths: set[Path] = set()
    unique: list[tuple[Path, str]] = []
    for path, label in samples:
        rp = path.resolve()
        if rp in seen_paths:
            continue
        seen_paths.add(rp)
        unique.append((path, label))
    if before != len(unique):
        log(f"  [dedupe] removed {before - len(unique)} duplicate paths ({before} -> {len(unique)})")

    return unique


def load_exclude_path_substrings() -> list[str]:
    """Lines from data/brain_scan_exclude_paths.txt matched as substrings on resolved paths."""
    if not EXCLUDE_PATHS_FILE.is_file():
        return []
    lines: list[str] = []
    for line in EXCLUDE_PATHS_FILE.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        lines.append(s.replace("\\", "/"))
    return lines


def apply_exclude_substrings(
    samples: list[tuple[Path, str]], patterns: list[str],
) -> list[tuple[Path, str]]:
    if not patterns:
        return samples
    out: list[tuple[Path, str]] = []
    skipped = 0
    for path, label in samples:
        sp = str(path.resolve()).replace("\\", "/")
        if any(p in sp for p in patterns):
            skipped += 1
            continue
        out.append((path, label))
    if skipped:
        log(f"  [exclude] removed {skipped} paths (data/brain_scan_exclude_paths.txt)")
    return out


def filter_readable_images(samples: list[tuple[Path, str]]) -> list[tuple[Path, str]]:
    """Drop files PIL cannot open (corrupt / wrong format)."""
    ok: list[tuple[Path, str]] = []
    bad = 0
    for path, label in samples:
        try:
            _load_image_rgb(path)
            ok.append((path, label))
        except Exception:
            bad += 1
    if bad:
        log(f"  [images] skipped {bad} unreadable/corrupt files")
    return ok


def subsample_per_class(
    samples: list[tuple[Path, str]], max_per_class: int, seed: int
) -> list[tuple[Path, str]]:
    """Cap each class to max_per_class images (random) to speed up training."""
    random.seed(seed)
    by_class: dict[str, list[tuple[Path, str]]] = defaultdict(list)
    for item in samples:
        by_class[item[1]].append(item)
    out: list[tuple[Path, str]] = []
    for cls, items in sorted(by_class.items()):
        if len(items) > max_per_class:
            random.shuffle(items)
            items = items[:max_per_class]
        out.extend(items)
    random.shuffle(out)
    return out


# ---------------------------------------------------------------------------
# Stratified split
# ---------------------------------------------------------------------------
def stratified_split(
    samples: list[tuple[Path, str]], val_ratio: float, seed: int
) -> tuple[list[tuple[Path, str]], list[tuple[Path, str]]]:
    """Stratified train/val split ensuring proportional class representation."""
    from sklearn.model_selection import StratifiedShuffleSplit

    labels = [label for _, label in samples]
    sss = StratifiedShuffleSplit(n_splits=1, test_size=val_ratio, random_state=seed)
    train_idx, val_idx = next(sss.split(samples, labels))

    train_samples = [samples[i] for i in train_idx]
    val_samples = [samples[i] for i in val_idx]
    return train_samples, val_samples


# ---------------------------------------------------------------------------
# Dataset, transforms, model
# ---------------------------------------------------------------------------
def build_all(
    train_samples: list[tuple[Path, str]],
    val_samples: list[tuple[Path, str]],
    class_to_idx: dict[str, int],
    arch: str = "efficientnet_b1",
    img_size: int | None = None,
) -> tuple[Any, Any, Any]:
    from torchvision import transforms

    sz = img_size if img_size is not None else IMG_SIZE
    resize_before_crop = int(sz * 1.1)

    normalize = transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225],
    )

    try:
        ra = transforms.RandAugment(
            num_ops=2,
            magnitude=12,
            interpolation=transforms.InterpolationMode.BILINEAR,
        )
    except TypeError:
        ra = transforms.RandAugment(num_ops=2, magnitude=12)

    train_tf = transforms.Compose([
        transforms.Resize(resize_before_crop),
        transforms.RandomCrop(sz, padding=0),
        transforms.RandomHorizontalFlip(),
        transforms.RandomVerticalFlip(p=0.15),
        ra,
        transforms.ColorJitter(brightness=0.15, contrast=0.15, saturation=0.1),
        transforms.ToTensor(),
        normalize,
        transforms.RandomErasing(p=0.15, scale=(0.02, 0.12)),
    ])

    val_tf = transforms.Compose([
        transforms.Resize(resize_before_crop),
        transforms.CenterCrop(sz),
        transforms.ToTensor(),
        normalize,
    ])

    train_ds = ScanDataset(train_samples, train_tf, class_to_idx)
    val_ds = ScanDataset(val_samples, val_tf, class_to_idx)

    n_classes = len(class_to_idx)
    model = build_classifier_model(arch, n_classes)

    return train_ds, val_ds, model


# ---------------------------------------------------------------------------
# Training helpers
# ---------------------------------------------------------------------------
def build_loss_fn(
    loss_weights: Any,
    use_focal: bool,
    gamma: float,
    label_smoothing: float,
):
    """Returns loss_fn(logits, targets, reduction='mean'|'none')."""
    import torch
    import torch.nn.functional as F

    def loss_fn(
        logits: torch.Tensor,
        targets: torch.Tensor,
        reduction: str = "mean",
    ) -> torch.Tensor:
        ls = 0.0 if use_focal else label_smoothing
        ce = F.cross_entropy(
            logits,
            targets,
            reduction="none",
            weight=loss_weights,
            label_smoothing=ls,
        )
        if not use_focal:
            return ce.mean() if reduction == "mean" else ce
        pt = torch.exp(-ce).clamp(min=1e-8, max=1.0)
        focal = ((1 - pt) ** gamma) * ce
        return focal.mean() if reduction == "mean" else focal

    return loss_fn


def save_train_checkpoint(path: Path, payload: dict[str, Any]) -> None:
    """Atomic-ish write: temp file then replace."""
    import torch

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = {**payload, "ckpt_version": TRAIN_CKPT_VERSION}
    torch.save(payload, tmp)
    tmp.replace(path)


def load_train_checkpoint(path: Path) -> dict[str, Any]:
    import torch

    ckpt = torch.load(str(path), map_location="cpu", weights_only=False)
    ver = ckpt.get("ckpt_version", 0)
    if ver != TRAIN_CKPT_VERSION:
        raise ValueError(
            f"Checkpoint version mismatch: file has {ver}, this script expects {TRAIN_CKPT_VERSION}",
        )
    return ckpt


def _default_num_workers() -> int:
    """Windows was pinned to 0 workers → CPU sat idle waiting on PIL decode. Use a small pool."""
    if sys.platform == "win32":
        return 2
    return min(8, max(2, (os.cpu_count() or 4) // 2))


def train_one_epoch(
    model,
    loader,
    optimizer,
    loss_fn,
    device,
    desc: str = "train",
    mixup_alpha: float = 0.0,
    mixup_prob: float = 0.0,
):
    import torch

    model.train()
    correct, total = 0, 0
    n_batches = len(loader)
    log_every = max(1, n_batches // 8)

    iterator = loader
    try:
        from tqdm import tqdm

        if os.environ.get("TQDM_DISABLE") != "1":
            iterator = tqdm(loader, desc=desc, leave=False, ncols=100)
    except ImportError:
        pass

    for batch_idx, (images, labels) in enumerate(iterator):
        images, labels = images.to(device), labels.to(device)
        optimizer.zero_grad()
        use_mixup = (
            mixup_alpha > 0
            and mixup_prob > 0
            and torch.rand(1, device=device).item() < mixup_prob
        )
        if use_mixup:
            lam = torch.distributions.Beta(mixup_alpha, mixup_alpha).sample().item()
            idx = torch.randperm(images.size(0), device=device)
            mixed = lam * images + (1 - lam) * images[idx]
            logits = model(mixed)
            la = loss_fn(logits, labels, reduction="none")
            lb = loss_fn(logits, labels[idx], reduction="none")
            loss = (lam * la + (1 - lam) * lb).mean()
            pred = logits.argmax(1)
            correct += (
                lam * (pred == labels).float() + (1 - lam) * (pred == labels[idx]).float()
            ).sum().item()
        else:
            logits = model(images)
            loss = loss_fn(logits, labels, reduction="mean")
            correct += (logits.argmax(1) == labels).sum().item()
        total += images.size(0)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        if os.environ.get("TQDM_DISABLE") == "1" and (
            batch_idx % log_every == 0 or batch_idx == n_batches - 1
        ):
            log(f"    {desc} batch {batch_idx + 1}/{n_batches}  loss={loss.item():.4f}")
    return correct / total


def eval_epoch(model, loader, device, desc: str = "val"):
    import torch

    model.eval()
    all_preds, all_labels = [], []
    iterator = loader
    try:
        from tqdm import tqdm

        if os.environ.get("TQDM_DISABLE") != "1":
            iterator = tqdm(loader, desc=desc, leave=False, ncols=100)
    except ImportError:
        pass
    with torch.no_grad():
        for images, labels in iterator:
            images, labels = images.to(device), labels.to(device)
            preds = model(images).argmax(1)
            all_preds.extend(preds.cpu().tolist())
            all_labels.extend(labels.cpu().tolist())
    acc = sum(p == l for p, l in zip(all_preds, all_labels)) / len(all_labels)
    return acc, all_preds, all_labels


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    _check_deps()

    import torch
    import numpy as np
    from torch import optim
    from torch.utils.data import DataLoader, WeightedRandomSampler
    from sklearn.metrics import classification_report, confusion_matrix

    ap = argparse.ArgumentParser(
        description="Train brain scan classifier (EfficientNet-B0/B1/B2, focal loss, mixup).",
    )
    ap.add_argument(
        "--arch",
        type=str,
        default="efficientnet_b1",
        choices=("efficientnet_b0", "efficientnet_b1", "efficientnet_b2"),
        help="Backbone (default: efficientnet_b1).",
    )
    ap.add_argument(
        "--img-size",
        type=int,
        default=None,
        metavar="PX",
        help=f"Square input size after crop (default: {IMG_SIZE}).",
    )
    ap.add_argument(
        "--no-focal",
        action="store_true",
        help="Use weighted CE + label smoothing instead of focal loss.",
    )
    ap.add_argument(
        "--no-mixup",
        action="store_true",
        help="Disable Mixup augmentation during training.",
    )
    ap.add_argument(
        "--quick",
        action="store_true",
        help="Faster run (~1h on CPU): cap 2000 imgs/class, fewer epochs (use full run overnight for best quality).",
    )
    ap.add_argument(
        "--medium",
        action="store_true",
        help="Between quick and full: ~75%% of default training budget, max 5000 imgs/class (~4–8h CPU typical).",
    )
    ap.add_argument(
        "--workers",
        type=int,
        default=None,
        metavar="N",
        help=f"DataLoader workers (default: {_default_num_workers()} on this machine; 0=main process only).",
    )
    ap.add_argument(
        "--max-per-class",
        type=int,
        default=None,
        metavar="N",
        help="Cap images per class (use on CPU: e.g. 800–2000). Full data + CPU = hours per epoch.",
    )
    ap.add_argument(
        "--head-epochs",
        type=int,
        default=None,
        help="Override head-training epochs (default: 5, or 3 with --quick, 4 with --medium).",
    )
    ap.add_argument(
        "--finetune-epochs",
        type=int,
        default=None,
        help="Override max fine-tune epochs (default: 25, or 12 with --quick, 19 with --medium).",
    )
    ap.add_argument(
        "--patience",
        type=int,
        default=None,
        help="Early-stopping patience (default: 7, or 4 with --quick, 6 with --medium).",
    )
    ap.add_argument(
        "--resume",
        type=str,
        default=None,
        metavar="PATH",
        help="Resume from a training checkpoint (same data layout; config is taken from the checkpoint).",
    )
    ap.add_argument(
        "--data-profile",
        type=str,
        default="full",
        choices=("full", "conservative", "originals_only"),
        help=(
            "Which folders to merge: full (all sources), conservative (skip train/test/External_test), "
            "originals_only (only data/raw/<ClassName>/). Ignored when using --resume (checkpoint wins)."
        ),
    )
    ap.add_argument(
        "--no-verify-images",
        action="store_true",
        help="Skip opening every file with PIL at collect time (faster; corrupt files may error in DataLoader).",
    )
    ap.add_argument(
        "--checkpoint-path",
        type=str,
        default=str(DEFAULT_TRAIN_CHECKPOINT),
        metavar="PATH",
        help=f"Where to write periodic training checkpoints (default: {DEFAULT_TRAIN_CHECKPOINT}).",
    )
    args = ap.parse_args()

    resume_path = Path(args.resume).resolve() if args.resume else None
    checkpoint_path = Path(args.checkpoint_path).resolve()

    quick_mode = bool(args.quick)
    medium_mode = bool(args.medium)
    if quick_mode and medium_mode:
        log("\n[ERROR] Use only one of --quick or --medium (not both).\n")
        sys.exit(1)
    if resume_path and (quick_mode or medium_mode or args.max_per_class is not None):
        log("\n  [resume] Ignoring --quick/--medium/--max-per-class (using values from checkpoint).\n")

    torch.manual_seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    nw = args.workers if args.workers is not None else _default_num_workers()
    if device.type == "cpu":
        try:
            torch.set_num_threads(max(1, min(16, (os.cpu_count() or 4))))
        except Exception:
            pass

    resume_ckpt: dict[str, Any] | None = None
    data_mode: str
    max_per_class_custom: int | None
    data_profile: str

    if resume_path:
        if not resume_path.is_file():
            log(f"\n[ERROR] --resume file not found: {resume_path}\n")
            sys.exit(1)
        resume_ckpt = load_train_checkpoint(resume_path)
        quick_mode = bool(resume_ckpt["quick_mode"])
        medium_mode = bool(resume_ckpt["medium_mode"])
        head_epochs = int(resume_ckpt["head_epochs"])
        max_epochs = int(resume_ckpt["max_epochs"])
        patience = int(resume_ckpt["patience"])
        batch_size = int(resume_ckpt["batch_size"])
        arch = str(resume_ckpt["arch"]).lower().strip()
        img_size = int(resume_ckpt["img_size"])
        use_focal = bool(resume_ckpt["use_focal"])
        mixup_alpha = float(resume_ckpt["mixup_alpha"])
        mixup_prob = float(resume_ckpt["mixup_prob"])
        data_mode = str(resume_ckpt.get("data_mode", "full"))
        max_per_class_custom = resume_ckpt.get("max_per_class_custom")
        if max_per_class_custom is not None:
            max_per_class_custom = int(max_per_class_custom)
        data_profile = str(resume_ckpt.get("data_profile", "full")).lower().strip()
        if data_profile not in ("full", "conservative", "originals_only"):
            data_profile = "full"
        log(f"\n  [resume] {resume_path.name}")
        log(f"  [resume] data_profile={data_profile} (from checkpoint)")
        log(
            f"  [resume] Progress: head {resume_ckpt['head_epochs_completed']}/{head_epochs}  |  "
            f"finetune {resume_ckpt['finetune_epochs_completed']}/{max_epochs}",
        )
    else:
        head_epochs = HEAD_EPOCHS
        max_epochs = MAX_EPOCHS
        patience = PATIENCE
        batch_size = BATCH_SIZE

        if quick_mode:
            head_epochs = QUICK_HEAD_EPOCHS
            max_epochs = QUICK_MAX_EPOCHS
            patience = QUICK_PATIENCE
            batch_size = 48 if device.type == "cuda" else 32
        elif medium_mode:
            head_epochs = MEDIUM_HEAD_EPOCHS
            max_epochs = MEDIUM_MAX_EPOCHS
            patience = MEDIUM_PATIENCE
            batch_size = 48 if device.type == "cuda" else 32
        else:
            if args.head_epochs is not None:
                head_epochs = args.head_epochs
            if args.finetune_epochs is not None:
                max_epochs = args.finetune_epochs
            if args.patience is not None:
                patience = args.patience

        if args.head_epochs is not None:
            head_epochs = args.head_epochs
        if args.finetune_epochs is not None:
            max_epochs = args.finetune_epochs
        if args.patience is not None:
            patience = args.patience

        img_size = args.img_size if args.img_size is not None else IMG_SIZE
        arch = args.arch.strip().lower()
        use_focal = not args.no_focal
        mixup_alpha = 0.0 if args.no_mixup else MIXUP_ALPHA
        mixup_prob = 0.0 if args.no_mixup else MIXUP_PROB

        if quick_mode:
            data_mode = "quick"
            max_per_class_custom = None
        elif medium_mode:
            data_mode = "medium"
            max_per_class_custom = None
        elif args.max_per_class is not None:
            data_mode = "custom"
            max_per_class_custom = int(args.max_per_class)
        else:
            data_mode = "full"
            max_per_class_custom = None

        data_profile = str(args.data_profile).lower().strip()

    log(f"\n  Device: {device}")
    log(f"  DataLoader workers: {nw}  (images decoded in parallel; was 0 on Windows before)")
    if device.type == "cpu":
        log("  Tip: NVIDIA GPU + CUDA build of PyTorch se training 5-20x fast ho sakti hai.")
    if not resume_ckpt:
        if quick_mode:
            log("  Mode: QUICK (~1 hour target) - subsample + reduced epochs")
        elif medium_mode:
            log("  Mode: MEDIUM (~75% of full default budget) - more data/epochs than --quick; ~4-8h CPU typical")
    else:
        log("  Mode: RESUME (config from checkpoint)")

    log("\n" + "=" * 70)
    log("  BRAIN SCAN CLASSIFIER v2 - TRAINING PIPELINE")
    log(f"  Model: {arch} | img={img_size} | focal={use_focal} | mixup={mixup_alpha > 0}")
    log(f"  data_profile: {data_profile}")
    log(f"  Training checkpoint file: {checkpoint_path}")
    log("=" * 70)

    # -- Collect ALL data ----------------------------------------------------
    log("\n  Collecting images from all sources...")
    all_samples = collect_all_data(data_profile)
    all_samples = apply_exclude_substrings(all_samples, load_exclude_path_substrings())
    if not args.no_verify_images:
        all_samples = filter_readable_images(all_samples)
    else:
        log("  [images] skipping PIL verify (--no-verify-images)")

    if data_mode == "quick":
        before = len(all_samples)
        all_samples = subsample_per_class(all_samples, QUICK_MAX_PER_CLASS, RANDOM_SEED)
        log(f"\n  [quick] Subsampled: {before} -> {len(all_samples)} (max {QUICK_MAX_PER_CLASS}/class)")
    elif data_mode == "medium":
        before = len(all_samples)
        all_samples = subsample_per_class(all_samples, MEDIUM_MAX_PER_CLASS, RANDOM_SEED)
        log(f"\n  [medium] Subsampled: {before} -> {len(all_samples)} (max {MEDIUM_MAX_PER_CLASS}/class)")
    elif data_mode == "custom" and max_per_class_custom is not None:
        before = len(all_samples)
        all_samples = subsample_per_class(all_samples, max_per_class_custom, RANDOM_SEED)
        log(f"\n  [max-per-class] Subsampled: {before} -> {len(all_samples)} (max {max_per_class_custom}/class)")

    if not all_samples:
        log("[ERROR] No images found.")
        sys.exit(1)

    # Build class map
    class_names = sorted(set(label for _, label in all_samples))
    class_to_idx = {c: i for i, c in enumerate(class_names)}
    idx_to_class = {i: c for c, i in class_to_idx.items()}
    n_classes = len(class_names)

    if resume_ckpt is not None and resume_ckpt.get("class_to_idx") != class_to_idx:
        log("\n[ERROR] Resume failed: class_to_idx does not match current data.")
        log("        Use the same data/raw layout and subsample mode as the original run.\n")
        sys.exit(1)

    # -- Class distribution --------------------------------------------------
    cnt = Counter(label for _, label in all_samples)
    log(f"\n  Total: {len(all_samples)} images, {n_classes} classes")
    log("  Class distribution:")
    for cls in class_names:
        bar = "#" * (cnt[cls] // 100)
        log(f"    {cls:30s} {cnt[cls]:6d} {bar}")

    # -- Stratified split ----------------------------------------------------
    train_samples, val_samples = stratified_split(all_samples, VAL_SPLIT, RANDOM_SEED)
    log(f"\n  Stratified split: {len(train_samples)} train / {len(val_samples)} val")

    if device.type == "cpu":
        n_train = len(train_samples)
        batches_per_epoch = (n_train + batch_size - 1) // batch_size
        log(f"\n  [CPU] ~{batches_per_epoch} train batches/epoch @ batch_size={batch_size}.")
        log("        Full data on CPU = often 30-90+ min/epoch (or more). Not stuck - just slow.")
        if data_mode == "full":
            log("        Stop: Ctrl+C then run one of:")
            log('          py -3 train_brain_scan.py --quick')
            log('          py -3 train_brain_scan.py --medium')
            log('          py -3 train_brain_scan.py --max-per-class 1500 --finetune-epochs 10')
            log('          py -3 train_brain_scan.py --resume models/brain_scan_train_checkpoint.pt')
            log("        GPU (CUDA) install karne se usually 5-20x fast.")

    train_cnt = Counter(label for _, label in train_samples)
    val_cnt = Counter(label for _, label in val_samples)
    log("  Train distribution:")
    for cls in class_names:
        log(f"    {cls:30s} train={train_cnt[cls]:5d}  val={val_cnt[cls]:4d}")

    # -- Build datasets and model --------------------------------------------
    train_ds, val_ds, model = build_all(
        train_samples, val_samples, class_to_idx, arch=arch, img_size=img_size,
    )
    model = model.to(device)

    # -- Weighted sampler (class-balanced batches) ---------------------------
    train_labels = [class_to_idx[label] for _, label in train_samples]
    class_counts = np.bincount(train_labels, minlength=n_classes).astype(float)
    class_weights = 1.0 / (class_counts + 1e-6)
    sample_weights = [class_weights[label] for label in train_labels]
    sampler = WeightedRandomSampler(sample_weights, num_samples=len(train_labels), replacement=True)

    train_loader = DataLoader(
        train_ds, batch_size=batch_size, sampler=sampler,
        num_workers=nw, pin_memory=(device.type == "cuda"),
        persistent_workers=(nw > 0),
    )
    val_loader = DataLoader(
        val_ds, batch_size=batch_size, shuffle=False, num_workers=nw,
        persistent_workers=(nw > 0),
    )

    # -- Class-weighted focal or CE ------------------------------------------
    loss_weights = torch.tensor(class_weights / class_weights.sum() * n_classes, dtype=torch.float32).to(device)
    loss_fn = build_loss_fn(
        loss_weights,
        use_focal=use_focal,
        gamma=FOCAL_GAMMA,
        label_smoothing=0.1,
    )
    log(f"\n  Loss: {'focal' if use_focal else 'weighted CE + label smoothing'}  |  class weights: {[f'{w:.2f}' for w in loss_weights.cpu().tolist()]}")
    if mixup_alpha > 0:
        log(f"  Mixup: alpha={mixup_alpha}  prob={mixup_prob}")

    h_done = int(resume_ckpt["head_epochs_completed"]) if resume_ckpt else 0
    f_done = int(resume_ckpt["finetune_epochs_completed"]) if resume_ckpt else 0

    def pack_ckpt(
        *,
        hed: int,
        fed: int,
        optimizer,
        scheduler,
        bva: float,
        pc: int,
        bst,
        phase: str,
    ) -> dict[str, Any]:
        return {
            "class_to_idx": class_to_idx,
            "idx_to_class": idx_to_class,
            "n_classes": n_classes,
            "arch": arch,
            "img_size": img_size,
            "head_epochs": head_epochs,
            "max_epochs": max_epochs,
            "patience": patience,
            "batch_size": batch_size,
            "quick_mode": quick_mode,
            "medium_mode": medium_mode,
            "data_mode": data_mode,
            "data_profile": data_profile,
            "max_per_class_custom": max_per_class_custom,
            "use_focal": use_focal,
            "mixup_alpha": mixup_alpha,
            "mixup_prob": mixup_prob,
            "head_epochs_completed": hed,
            "finetune_epochs_completed": fed,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "scheduler_state_dict": scheduler.state_dict() if scheduler is not None else None,
            "best_val_acc": bva,
            "patience_cnt": pc,
            "best_state": bst,
            "phase": phase,
        }

    # ========================================================================
    # PHASE 1: Head-only (backbone frozen)
    # ========================================================================
    head_completed_this_run = False
    if h_done < head_epochs:
        log(f"\n{'=' * 70}")
        log(f"  PHASE 1: Head-only training ({head_epochs} epochs, backbone frozen)")
        log(f"{'=' * 70}")

        for param in model.features.parameters():
            param.requires_grad = False

        optimizer = optim.Adam(
            filter(lambda p: p.requires_grad, model.parameters()),
            lr=LR_HEAD, weight_decay=WEIGHT_DECAY,
        )
        if resume_ckpt is not None and h_done > 0:
            model.load_state_dict(resume_ckpt["model_state_dict"])
            optimizer.load_state_dict(resume_ckpt["optimizer_state_dict"])

        for epoch in range(h_done + 1, head_epochs + 1):
            train_acc = train_one_epoch(
                model,
                train_loader,
                optimizer,
                loss_fn,
                device,
                desc=f"head ep{epoch}/{head_epochs}",
                mixup_alpha=mixup_alpha,
                mixup_prob=mixup_prob,
            )
            val_acc, _, _ = eval_epoch(model, val_loader, device, desc="val")
            log(f"  Epoch {epoch:2d}/{head_epochs} | train={train_acc:.4f} | val={val_acc:.4f}")
            save_train_checkpoint(
                checkpoint_path,
                pack_ckpt(
                    hed=epoch,
                    fed=0,
                    optimizer=optimizer,
                    scheduler=None,
                    bva=0.0,
                    pc=0,
                    bst=None,
                    phase="head",
                ),
            )
            log(f"  [checkpoint] saved -> {checkpoint_path.name}  (head {epoch}/{head_epochs})")
        h_done = head_epochs
        head_completed_this_run = True

    # ========================================================================
    # PHASE 2: Full fine-tune
    # ========================================================================
    log(f"\n{'=' * 70}")
    log(f"  PHASE 2: Full fine-tune (max {max_epochs} epochs, patience={patience})")
    log(f"{'=' * 70}")

    for param in model.parameters():
        param.requires_grad = True

    if resume_ckpt is not None and f_done > 0:
        model.load_state_dict(resume_ckpt["model_state_dict"])
        optimizer = optim.Adam(model.parameters(), lr=LR_FINETUNE, weight_decay=WEIGHT_DECAY)
        optimizer.load_state_dict(resume_ckpt["optimizer_state_dict"])
        scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max_epochs)
        sd_sched = resume_ckpt.get("scheduler_state_dict")
        if sd_sched is not None:
            scheduler.load_state_dict(sd_sched)
        best_val_acc = float(resume_ckpt.get("best_val_acc", 0.0))
        patience_cnt = int(resume_ckpt.get("patience_cnt", 0))
        best_state = resume_ckpt.get("best_state")
    elif resume_ckpt is not None and f_done == 0 and h_done >= head_epochs and not head_completed_this_run:
        model.load_state_dict(resume_ckpt["model_state_dict"])
        optimizer = optim.Adam(model.parameters(), lr=LR_FINETUNE, weight_decay=WEIGHT_DECAY)
        scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max_epochs)
        best_val_acc = 0.0
        patience_cnt = 0
        best_state = None
    else:
        optimizer = optim.Adam(model.parameters(), lr=LR_FINETUNE, weight_decay=WEIGHT_DECAY)
        scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max_epochs)
        best_val_acc = 0.0
        patience_cnt = 0
        best_state = None

    for epoch in range(f_done + 1, max_epochs + 1):
        train_acc = train_one_epoch(
            model,
            train_loader,
            optimizer,
            loss_fn,
            device,
            desc=f"ft ep{epoch}/{max_epochs}",
            mixup_alpha=mixup_alpha,
            mixup_prob=mixup_prob,
        )
        val_acc, val_preds, val_labels = eval_epoch(model, val_loader, device, desc="val")
        scheduler.step()

        improved = val_acc > best_val_acc
        if improved:
            best_val_acc = val_acc
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            patience_cnt = 0
            marker = " [best]"
        else:
            patience_cnt += 1
            marker = f" (no improve {patience_cnt}/{patience})"

        log(f"  Epoch {epoch:2d}/{max_epochs} | train={train_acc:.4f} | val={val_acc:.4f}{marker}")

        save_train_checkpoint(
            checkpoint_path,
            pack_ckpt(
                hed=head_epochs,
                fed=epoch,
                optimizer=optimizer,
                scheduler=scheduler,
                bva=best_val_acc,
                pc=patience_cnt,
                bst=best_state,
                phase="finetune",
            ),
        )
        log(f"  [checkpoint] saved -> {checkpoint_path.name}  (finetune {epoch}/{max_epochs})")

        if patience_cnt >= patience:
            log(f"  Early stopping at epoch {epoch}.")
            break

    if best_state is not None:
        model.load_state_dict(best_state)

    # -- Final val metrics ---------------------------------------------------
    log(f"\n{'=' * 70}")
    log("  VALIDATION METRICS (best checkpoint)")
    log(f"{'=' * 70}")

    val_acc_final, val_preds, val_labels = eval_epoch(model, val_loader, device)
    label_ids = list(range(n_classes))
    label_names = [idx_to_class[i] for i in label_ids]

    log(f"\n  Accuracy: {val_acc_final:.4f}")
    log("\n  Classification Report:")
    log(classification_report(
        val_labels, val_preds,
        labels=label_ids, target_names=label_names, zero_division=0,
    ))

    cm = confusion_matrix(val_labels, val_preds, labels=label_ids)
    log("  Confusion Matrix:")
    for i, row in enumerate(cm):
        log(f"    {label_names[i]:25s} {row}")

    # -- Per-class accuracy --------------------------------------------------
    log("\n  Per-class accuracy:")
    for i in range(n_classes):
        total_i = sum(1 for l in val_labels if l == i)
        correct_i = sum(1 for p, l in zip(val_preds, val_labels) if p == l == i)
        acc_i = correct_i / total_i if total_i > 0 else 0
        log(f"    {label_names[i]:25s} {acc_i:.4f} ({correct_i}/{total_i})")

    # ========================================================================
    # Save artifacts
    # ========================================================================
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODELS_DIR / "brain_scan_classifier.pt"
    meta_path = MODELS_DIR / "brain_scan_classifier_meta.json"

    import torch
    torch.save({
        "model_state_dict": model.state_dict(),
        "class_to_idx":     class_to_idx,
        "idx_to_class":     idx_to_class,
        "n_classes":        n_classes,
        "img_size":         img_size,
        "best_val_acc":     best_val_acc,
        "arch":             arch,
        "classifier_dropout": CLASSIFIER_DROPOUT,
    }, model_path)

    meta = {
        "arch":           arch,
        "n_classes":      n_classes,
        "class_to_idx":   class_to_idx,
        "idx_to_class":   {str(k): v for k, v in idx_to_class.items()},
        "img_size":       img_size,
        "classifier_dropout": CLASSIFIER_DROPOUT,
        "best_val_acc":   round(best_val_acc, 4),
        "train_samples":  len(train_samples),
        "val_samples":    len(val_samples),
        "class_counts":   dict(cnt),
        "training_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "version":        "v2",
        "quick_mode":     quick_mode,
        "medium_mode":    medium_mode,
        "data_profile":   data_profile,
        "use_focal":      use_focal,
        "focal_gamma":    FOCAL_GAMMA,
        "mixup_alpha":    mixup_alpha,
        "mixup_prob":     mixup_prob,
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    log(f"\n{'=' * 70}")
    log("  ARTIFACTS SAVED")
    log(f"{'=' * 70}")
    log(f"  Checkpoint : {model_path}")
    log(f"  Metadata   : {meta_path}")
    log(f"  Best val   : {best_val_acc:.4f}")
    log(f"  Classes    : {class_names}")
    log(f"  Total data : {len(all_samples)} images")
    log(f"{'=' * 70}\n")


if __name__ == "__main__":
    t0 = time.time()
    main()
    log(f"  Total time: {time.time() - t0:.1f}s\n")
