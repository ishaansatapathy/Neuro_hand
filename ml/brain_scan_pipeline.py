"""
Inference path for brain MRI classification — must stay aligned with server._classify_scan.
"""
from __future__ import annotations

import random
from typing import Any

from .brain_region_rules import build_brain_region_for_prediction

import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms


def is_likely_medical_image(image_path: str) -> tuple[bool, str]:
    """Lightweight heuristic: reject unreadable / tiny images."""
    try:
        im = Image.open(image_path)
        im = im.convert("RGB")
    except Exception as e:
        return False, f"Could not open image: {e}"

    w, h = im.size
    if w < 48 or h < 48:
        return False, "Image dimensions too small for analysis."

    return True, ""


def _class_name_from_meta(metadata: dict[str, Any] | None, idx: int, n_classes: int) -> str:
    if not metadata:
        return f"class_{idx}"
    m = metadata.get("idx_to_class") or {}
    name = m.get(str(idx))
    if name is not None:
        return str(name)
    name = m.get(idx)  # type: ignore[arg-type]
    if name is not None:
        return str(name)
    c2i = metadata.get("class_to_idx") or {}
    for label, j in c2i.items():
        if int(j) == idx:
            return str(label)
    return f"class_{idx}"


def _to_api_prediction_label(trained_class_name: str) -> str:
    """Compact labels for API / UI (matches server._api_to_legacy expectations)."""
    c = trained_class_name.strip()
    if c == "Hemorrhagic Stroke":
        return "Hemorrhagic"
    if c == "Ischemic Stroke":
        return "Ischemic"
    if c == "Normal":
        return "Normal"
    return c


def _dummy_run(metadata: dict[str, Any] | None) -> dict[str, Any]:
    n = 3
    if metadata and metadata.get("n_classes"):
        n = int(metadata["n_classes"])
    raw_labels = [_class_name_from_meta(metadata, i, n) for i in range(n)]
    probs = [random.random() for _ in range(n)]
    s = sum(probs) or 1.0
    probs = [p / s for p in probs]
    ranked = sorted(enumerate(probs), key=lambda x: -x[1])
    top_predictions = [{"label": raw_labels[i], "probability": float(p)} for i, p in ranked]
    best_i, best_p = ranked[0]
    api = _to_api_prediction_label(raw_labels[best_i])
    return {
        "prediction": api,
        "confidence": float(best_p),
        "raw_prediction": raw_labels[best_i],
        "top_predictions": top_predictions,
        "uncertain": best_p < 0.7,
    }


def run_classification(
    image_path: str,
    model: Any,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Returns keys used by server._classify_scan:
    prediction, confidence, raw_prediction (optional), top_predictions, uncertain (optional).
    """
    if model is None:
        return _dummy_run(metadata)

    meta = metadata or {}
    img_size = int(meta.get("img_size", 224))

    tf = transforms.Compose(
        [
            transforms.Resize((img_size, img_size)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ]
    )

    im = Image.open(image_path).convert("RGB")
    x = tf(im).unsqueeze(0)

    device = next(model.parameters()).device
    x = x.to(device)

    with torch.no_grad():
        logits = model(x)
        probs = F.softmax(logits, dim=1).squeeze(0)

    p_list = probs.cpu().tolist()
    n_classes = len(p_list)

    raw_labels = [_class_name_from_meta(meta, i, n_classes) for i in range(n_classes)]
    ranked = sorted(enumerate(p_list), key=lambda x: -x[1])
    top_predictions = [{"label": raw_labels[i], "probability": float(p)} for i, p in ranked]

    best_i = ranked[0][0]
    best_p = float(ranked[0][1])
    api = _to_api_prediction_label(raw_labels[best_i])

    return {
        "prediction": api,
        "confidence": best_p,
        "raw_prediction": raw_labels[best_i],
        "top_predictions": top_predictions,
        "uncertain": best_p < 0.7,
    }
