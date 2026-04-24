"""
=============================================================================
 Brain Scan Analyzer — Real CV-based analysis of brain CT/MRI scans
=============================================================================

Replaces the hardcoded dummy analysis in server.py with actual image analysis.

Techniques used:
  1. Otsu thresholding + morphology for brain mask extraction
  2. Hemisphere asymmetry index (pixel-level L/R comparison)
  3. Intensity distribution analysis per anatomical zone
  4. Hyper/hypo-dense region detection for hemorrhagic/ischemic lesions
  5. Texture analysis (local intensity variance)
  6. Composite severity scoring per zone

Each scan now produces UNIQUE results based on actual pixel data.
=============================================================================
"""
from __future__ import annotations

import cv2
import numpy as np
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Anatomical zone definitions (approximate mapping on axial CT slice)
# y = top→bottom (anterior→posterior), x = left→right
# ---------------------------------------------------------------------------
ZONE_MAP = {
    "Frontal Lobe — Motor Cortex": {
        "y_range": (0.05, 0.38),
        "x_range": (0.15, 0.85),
        "depth": "cortical",
    },
    "Parietal Lobe — Sensory Cortex": {
        "y_range": (0.38, 0.65),
        "x_range": (0.10, 0.90),
        "depth": "cortical",
    },
    "Temporal Lobe": {
        "y_range": (0.30, 0.65),
        "x_range": (0.0, 0.18),
        "depth": "cortical",
    },
    "Occipital Lobe": {
        "y_range": (0.68, 0.95),
        "x_range": (0.20, 0.80),
        "depth": "cortical",
    },
    "Basal Ganglia / Putamen": {
        "y_range": (0.32, 0.52),
        "x_range": (0.30, 0.70),
        "depth": "deep",
    },
    "Thalamus": {
        "y_range": (0.45, 0.58),
        "x_range": (0.35, 0.65),
        "depth": "deep",
    },
    "Internal Capsule": {
        "y_range": (0.36, 0.52),
        "x_range": (0.28, 0.72),
        "depth": "deep",
    },
    "Middle Cerebral Artery (MCA) Territory": {
        "y_range": (0.20, 0.55),
        "x_range": (0.08, 0.92),
        "depth": "vascular",
    },
}

# ---------------------------------------------------------------------------
# Clinical effects per region
# ---------------------------------------------------------------------------
REGION_EFFECTS: dict[str, list[str]] = {
    "Frontal Lobe — Motor Cortex": [
        "Voluntary movement impairment",
        "Fine motor control deficit",
        "Motor planning difficulty (apraxia)",
        "Executive function impairment",
        "Behavioral and personality changes",
    ],
    "Parietal Lobe — Sensory Cortex": [
        "Reduced proprioception",
        "Tactile discrimination impairment",
        "Difficulty with spatial awareness",
        "Sensory processing deficit",
        "Dyscalculia and agraphia",
    ],
    "Temporal Lobe": [
        "Language comprehension deficit (Wernicke's area)",
        "Auditory processing issues",
        "Memory encoding difficulty",
        "Emotional regulation problems",
    ],
    "Occipital Lobe": [
        "Visual field defects (hemianopia)",
        "Visual processing impairment",
        "Object recognition difficulty (agnosia)",
        "Reading comprehension loss (alexia)",
    ],
    "Basal Ganglia / Putamen": [
        "Movement initiation problems",
        "Bradykinesia",
        "Muscle tone abnormalities",
        "Involuntary movements (dyskinesia)",
        "Movement coordination breakdown",
    ],
    "Thalamus": [
        "Contralateral sensory loss",
        "Central post-stroke pain",
        "Attention and memory deficits",
        "Sleep-wake cycle disruption",
    ],
    "Internal Capsule": [
        "Dense motor pathway disruption",
        "Pure motor or sensory stroke pattern",
        "Corticospinal tract damage",
        "Contralateral hemiplegia",
    ],
    "Middle Cerebral Artery (MCA) Territory": [
        "Contralateral hemiparesis (arm > leg)",
        "Sensory loss on opposite side",
        "Aphasia (if dominant hemisphere)",
        "Spatial neglect (if non-dominant hemisphere)",
    ],
}

# ---------------------------------------------------------------------------
# Rehab recommendations indexed by zone
# ---------------------------------------------------------------------------
REHAB_BY_ZONE: dict[str, str] = {
    "Frontal Lobe — Motor Cortex": "Task-specific repetitive training and motor planning exercises",
    "Parietal Lobe — Sensory Cortex": "Proprioceptive neuromuscular facilitation (PNF) and sensory retraining",
    "Temporal Lobe": "Speech-language therapy and auditory rehabilitation",
    "Occipital Lobe": "Visual scanning training and compensatory strategies",
    "Basal Ganglia / Putamen": "Rhythmic auditory stimulation for motor timing recovery",
    "Thalamus": "Sensory discrimination training and desensitization protocols",
    "Internal Capsule": "Constraint-induced movement therapy (CIMT) for affected limb",
    "Middle Cerebral Artery (MCA) Territory": "Bilateral arm training for interhemispheric facilitation",
}

# General rehab recommendations by stroke type
GENERAL_REHAB = {
    "hemorrhagic": [
        "Progressive resistance training for deep brain pathway activation",
        "Functional electrical stimulation (FES) assisted training",
        "Gradual weight-bearing exercises as edema resolves",
    ],
    "ischemic": [
        "Mirror therapy to activate ipsilateral motor cortex",
        "Constraint-induced movement therapy (CIMT) for affected limb",
        "Repetitive transcranial magnetic stimulation (rTMS) adjunct therapy",
    ],
    "generic": [
        "Active range-of-motion exercises",
        "Bilateral coordination activities",
        "Task-specific training with progressive difficulty",
    ],
}


# ═══════════════════════════════════════════════════════════════════════════
#  Main entry point
# ═══════════════════════════════════════════════════════════════════════════

def analyze_brain_scan(
    image_path: str,
    stroke_type: str,
    classification_confidence: float,
) -> dict[str, Any]:
    """
    Analyze a brain CT/MRI scan and return zone-specific severity data.

    Parameters
    ----------
    image_path : str
        Path to the saved brain scan image.
    stroke_type : str
        Predicted stroke classification (e.g. "Ischemic Stroke", "Hemorrhagic").
    classification_confidence : float
        Model confidence for the classification.

    Returns
    -------
    dict with keys:
        stroke_type, description, affected_zones, neuroplasticity_targets,
        recovery_potential, scan_metrics
    """
    img = cv2.imread(image_path)
    if img is None:
        return _fallback_analysis(stroke_type, classification_confidence)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # ── Step 1: Extract brain mask ──────────────────────────────────────
    brain_mask = _extract_brain_mask(gray)
    brain_area = float(brain_mask.sum() / 255)
    if brain_area < 200:
        return _fallback_analysis(stroke_type, classification_confidence)

    # ── Step 2: Hemisphere asymmetry ───────────────────────────────────
    midline = w // 2
    left_hemi = gray[:, :midline].astype(np.float32)
    right_hemi_raw = gray[:, midline:]
    right_hemi = cv2.flip(right_hemi_raw, 1).astype(np.float32)

    left_mask = brain_mask[:, :midline]
    right_mask = cv2.flip(brain_mask[:, midline:], 1)

    min_w = min(left_hemi.shape[1], right_hemi.shape[1])
    left_crop = left_hemi[:, :min_w]
    right_crop = right_hemi[:, :min_w]
    mask_crop = (left_mask[:, :min_w] > 0) & (right_mask[:, :min_w] > 0)

    if mask_crop.sum() > 0:
        diff = np.abs(left_crop[mask_crop] - right_crop[mask_crop])
        denom = np.maximum(left_crop[mask_crop], right_crop[mask_crop]) + 1e-6
        global_asymmetry = float(np.mean(diff / denom))
    else:
        global_asymmetry = 0.0

    # ── Step 3: Detect abnormal regions ────────────────────────────────
    brain_pixels = gray[brain_mask > 0].astype(np.float32)
    mean_int = float(brain_pixels.mean())
    std_int = float(brain_pixels.std())

    is_hemorrhagic = any(
        kw in stroke_type.lower()
        for kw in ("hemorrhagic", "haemorrhagic", "bleed", "hemorrhage")
    )
    is_ischemic = any(
        kw in stroke_type.lower()
        for kw in ("ischemic", "ischaemic", "infarct")
    )

    # Hemorrhage → bright (hyperdense), Ischemia → dark (hypodense)
    if is_hemorrhagic:
        thresh = mean_int + 1.5 * std_int
        abnormal_mask = ((gray.astype(np.float32) > thresh) & (brain_mask > 0)).astype(np.uint8)
    elif is_ischemic:
        thresh = mean_int - 1.2 * std_int
        abnormal_mask = ((gray.astype(np.float32) < thresh) & (brain_mask > 0)).astype(np.uint8)
    else:
        # Generic: look for both
        hi = mean_int + 1.5 * std_int
        lo = mean_int - 1.2 * std_int
        abnormal_mask = (
            ((gray.astype(np.float32) > hi) | (gray.astype(np.float32) < lo))
            & (brain_mask > 0)
        ).astype(np.uint8)

    # Morphological cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    abnormal_mask = cv2.morphologyEx(abnormal_mask, cv2.MORPH_CLOSE, kernel)
    abnormal_mask = cv2.morphologyEx(abnormal_mask, cv2.MORPH_OPEN, kernel)

    total_lesion_area = float(abnormal_mask.sum())
    lesion_ratio = total_lesion_area / brain_area if brain_area > 0 else 0.0

    # ── Step 4: Per-zone analysis ──────────────────────────────────────
    zone_results: list[dict[str, Any]] = []

    for zone_name, zone_def in ZONE_MAP.items():
        y0 = int(zone_def["y_range"][0] * h)
        y1 = int(zone_def["y_range"][1] * h)
        x0 = int(zone_def["x_range"][0] * w)
        x1 = int(zone_def["x_range"][1] * w)

        z_brain = brain_mask[y0:y1, x0:x1]
        z_abnormal = abnormal_mask[y0:y1, x0:x1]
        z_gray = gray[y0:y1, x0:x1]

        z_brain_area = float(z_brain.sum() / 255)
        if z_brain_area < 50:
            continue

        z_lesion_area = float(z_abnormal.sum())
        z_lesion_ratio = z_lesion_area / z_brain_area

        # Zone-level asymmetry
        z_mid = (x1 - x0) // 2
        z_left = z_gray[:, :z_mid]
        z_right_raw = z_gray[:, z_mid:]
        z_right = cv2.flip(z_right_raw, 1)
        min_zw = min(z_left.shape[1], z_right.shape[1])
        if min_zw > 5:
            z_asym = float(
                np.abs(
                    z_left[:, :min_zw].astype(float).mean()
                    - z_right[:, :min_zw].astype(float).mean()
                )
                / 255.0
            )
        else:
            z_asym = 0.0

        # Texture score (normalized std)
        z_pixels = z_gray[z_brain > 0]
        texture = float(z_pixels.std() / 255.0) if len(z_pixels) > 0 else 0.0

        # Composite severity
        severity = _compute_severity(
            z_lesion_ratio, z_asym, texture, global_asymmetry, is_hemorrhagic
        )

        if severity > 0.05:
            all_effects = REGION_EFFECTS.get(
                zone_name, ["General neural function impairment"]
            )
            # Show more effects for higher severity
            n_eff = max(1, int(len(all_effects) * min(severity * 1.6, 1.0)))
            shown = all_effects[:n_eff]

            zone_results.append(
                {
                    "zone": zone_name,
                    "region": zone_def["depth"],
                    "severity": round(min(severity, 0.99), 2),
                    "effects": shown,
                    "lesion_ratio": round(z_lesion_ratio, 4),
                    "asymmetry": round(z_asym, 4),
                }
            )

    zone_results.sort(key=lambda z: z["severity"], reverse=True)
    zone_results = zone_results[:6]

    if not zone_results:
        return _fallback_analysis(stroke_type, classification_confidence)

    # ── Step 5: Rehab recommendations ──────────────────────────────────
    rehab_targets: list[str] = []
    for zr in zone_results[:4]:
        rec = REHAB_BY_ZONE.get(zr["zone"])
        if rec and rec not in rehab_targets:
            rehab_targets.append(rec)

    stroke_key = (
        "hemorrhagic" if is_hemorrhagic else "ischemic" if is_ischemic else "generic"
    )
    for gen in GENERAL_REHAB.get(stroke_key, GENERAL_REHAB["generic"]):
        if gen not in rehab_targets:
            rehab_targets.append(gen)
    rehab_targets = rehab_targets[:6]

    # ── Step 6: Recovery potential ─────────────────────────────────────
    avg_sev = float(np.mean([z["severity"] for z in zone_results]))
    recovery = _assess_recovery(stroke_type, avg_sev, lesion_ratio, global_asymmetry)

    # ── Step 7: Affected side ─────────────────────────────────────────
    left_lesion = float(abnormal_mask[:, :midline].sum())
    right_lesion = float(abnormal_mask[:, midline:].sum())
    if left_lesion > right_lesion * 1.3:
        side = "Left hemisphere — affects right side of body"
    elif right_lesion > left_lesion * 1.3:
        side = "Right hemisphere — affects left side of body"
    else:
        side = "Bilateral or midline — may affect both sides"

    # ── Build description ─────────────────────────────────────────────
    type_label = "Hemorrhagic" if is_hemorrhagic else "Ischemic" if is_ischemic else stroke_type
    pattern = "hyperdense (bright)" if is_hemorrhagic else "hypodense (dark)" if is_ischemic else "abnormal"
    description = (
        f"{type_label} pattern detected via image analysis. "
        f"{pattern.capitalize()} region coverage: {lesion_ratio * 100:.1f}% of brain area. "
        f"Hemisphere asymmetry index: {global_asymmetry:.3f}. {side}."
    )

    return {
        "stroke_type": type_label,
        "description": description,
        "affected_zones": zone_results,
        "neuroplasticity_targets": rehab_targets,
        "recovery_potential": recovery,
        "scan_metrics": {
            "lesion_coverage_pct": round(lesion_ratio * 100, 2),
            "hemisphere_asymmetry": round(global_asymmetry, 4),
            "affected_side": side,
            "mean_intensity": round(mean_int, 1),
            "intensity_std": round(std_int, 1),
            "zones_affected": len(zone_results),
            "avg_severity": round(avg_sev, 3),
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Internal helpers
# ═══════════════════════════════════════════════════════════════════════════

def _extract_brain_mask(gray: np.ndarray) -> np.ndarray:
    """Extract brain parenchyma from CT using Otsu + morphology."""
    # Otsu threshold
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Erode to strip skull (bright ring on CT)
    kernel_lg = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    eroded = cv2.erode(binary, kernel_lg, iterations=2)

    # Largest connected component = brain
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(eroded, connectivity=8)
    if n_labels < 2:
        return eroded

    areas = stats[1:, cv2.CC_STAT_AREA]
    biggest = int(np.argmax(areas)) + 1
    mask = np.where(labels == biggest, 255, 0).astype(np.uint8)

    # Dilate back slightly
    kernel_md = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (8, 8))
    mask = cv2.dilate(mask, kernel_md, iterations=1)

    # Fill holes
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(mask, contours, -1, 255, -1)

    return mask


def _compute_severity(
    lesion_ratio: float,
    asymmetry: float,
    texture: float,
    global_asym: float,
    is_hemorrhagic: bool,
) -> float:
    """Composite severity for one zone (0-1)."""
    if is_hemorrhagic:
        raw = (
            lesion_ratio * 3.5
            + asymmetry * 2.5
            + texture * 0.8
            + global_asym * 1.2
        )
    else:
        raw = (
            lesion_ratio * 2.8
            + asymmetry * 3.0
            + texture * 1.0
            + global_asym * 1.5
        )
    normalised = min(1.0, raw / 1.5)
    return float(normalised ** 0.7)


def _assess_recovery(
    stroke_type: str,
    avg_severity: float,
    lesion_ratio: float,
    asymmetry: float,
) -> str:
    """Generate a recovery-potential paragraph from scan metrics."""
    is_h = "hemorrhagic" in stroke_type.lower()

    if avg_severity < 0.30:
        level = "High"
        if is_h:
            body = (
                f"Limited hemorrhagic involvement (avg severity {avg_severity:.0%}). "
                "Small bleeds often resolve with edema management. "
                "Early rehabilitation within 2–4 weeks can leverage peak neuroplasticity. "
                "Expected timeline: significant gains within 3–6 months."
            )
        else:
            body = (
                f"Mild ischemic changes (avg severity {avg_severity:.0%}). "
                "Penumbra tissue likely salvageable with prompt intervention. "
                "Immediate rehabilitation recommended to maximise recovery. "
                "Expected timeline: major improvement within 3–6 months."
            )
    elif avg_severity < 0.60:
        level = "Moderate"
        if is_h:
            body = (
                f"Moderate hemorrhagic involvement (avg severity {avg_severity:.0%}, "
                f"lesion coverage {lesion_ratio * 100:.1f}%). "
                "Edema resolution over 2–4 weeks will reveal true deficit extent. "
                "Structured rehabilitation should begin once medically stable. "
                "Expected timeline: 6–12 months for major functional gains."
            )
        else:
            body = (
                f"Moderate ischemic changes (avg severity {avg_severity:.0%}, "
                f"affected area {lesion_ratio * 100:.1f}%). "
                "Some tissue in ischemic penumbra may recover with time. "
                "Intensive task-specific training recommended. "
                "Expected timeline: 6–12 months with consistent therapy."
            )
    else:
        level = "Guarded"
        if is_h:
            body = (
                f"Significant hemorrhagic involvement (avg severity {avg_severity:.0%}, "
                f"lesion coverage {lesion_ratio * 100:.1f}%). "
                "Deep-structure involvement may limit motor recovery. "
                "Long-term adaptive strategies alongside rehabilitation recommended. "
                "Timeline: 12 + months; focus on compensatory techniques and assistive devices."
            )
        else:
            body = (
                f"Extensive ischemic changes (avg severity {avg_severity:.0%}, "
                f"affected area {lesion_ratio * 100:.1f}%). "
                "Core infarct tissue unlikely to recover, but peri-lesional plasticity possible. "
                "Combined pharmacological + rehabilitation approach recommended. "
                "Timeline: 12 + months with ongoing therapy; focus on functional independence."
            )

    return f"{level} — {body}"


def _fallback_analysis(stroke_type: str, confidence: float) -> dict[str, Any]:
    """Minimal response when image analysis fails."""
    st = stroke_type if "normal" not in stroke_type.lower() else "None"
    return {
        "stroke_type": st,
        "description": (
            "Unable to perform detailed image analysis. "
            "Classification is based on model prediction only."
        ),
        "affected_zones": [],
        "neuroplasticity_targets": [
            "Consult neurologist for condition-specific rehabilitation plan",
            "General range-of-motion exercises recommended",
        ],
        "recovery_potential": (
            "Assessment requires clinical evaluation — automated analysis inconclusive."
        ),
        "scan_metrics": None,
    }
