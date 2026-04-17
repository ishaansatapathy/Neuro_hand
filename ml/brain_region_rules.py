"""
Rule-based brain region hints from classifier output (not a substitute for radiology).
"""
from __future__ import annotations

from typing import Any


def build_brain_region_for_prediction(
    prediction: str,
    confidence: float,
    image_path: str,
) -> dict[str, Any]:
    _ = image_path  # reserved for future lateralization heuristics
    p = (prediction or "").strip().lower()

    if p in ("rejected", "reject"):
        return {
            "region": "N/A",
            "side": "—",
            "description": "Image was not classified as a usable brain scan.",
            "confidence": 0.0,
        }

    if "hemorrhagic" in p:
        return {
            "region": "Deep / basal ganglia (typical hemorrhage territory)",
            "side": "Contralateral motor deficits possible — confirm on imaging",
            "description": "Hemorrhagic pattern: prioritize gentle range-of-motion and therapist-guided load progression.",
            "confidence": round(min(1.0, max(0.0, confidence)), 4),
        }

    if "ischemic" in p:
        return {
            "region": "Cortical / MCA territory (common for ischemia)",
            "side": "Contralateral weakness typical — confirm hemisphere on scan",
            "description": "Ischemic pattern: task-specific hand training and repetition help drive neuroplasticity.",
            "confidence": round(min(1.0, max(0.0, confidence)), 4),
        }

    if "normal" in p or "uncertain" in p:
        return {
            "region": "No focal acute stroke pattern inferred",
            "side": "—",
            "description": "Use maintenance mobility exercises; follow clinical follow-up if symptoms persist.",
            "confidence": round(min(1.0, max(0.0, confidence)), 4),
        }

    return {
        "region": "Unspecified",
        "side": "—",
        "description": "General neuro-rehab principles apply; consult imaging with a clinician.",
        "confidence": round(min(1.0, max(0.0, confidence)), 4),
    }
