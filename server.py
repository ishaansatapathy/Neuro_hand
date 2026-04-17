"""
=============================================================================
 REHAB AI — FastAPI Backend Server
=============================================================================

 Endpoints:
   POST   /api/scan/upload         Upload brain MRI, classify stroke type
   GET    /api/hand/reference     Load healthy-hand reference JSON
   POST   /api/hand/reference     Save healthy-hand reference (angles, wrist)
   POST   /api/scan/analyze/{id}   Get detailed analysis of uploaded scan
   POST   /api/session/start       Start a new rehab session
   GET    /api/session/{id}        Get session status
   POST   /api/session/{id}/end    End session and save results
   GET    /api/sessions            List all sessions (history)
   POST   /api/voice/generate      Pre-generate all voice phrases
   GET    /api/voice/status        Check which phrases are cached
   GET    /api/voice/play/{key}    Serve a cached voice file
   GET    /api/patient             Get patient profile
   POST   /api/patient             Update patient profile
   WS     /ws/session/{id}         Real-time session updates

 Run:
   py -3 server.py
   or: uvicorn server:app --reload --port 8000
=============================================================================
"""
from __future__ import annotations

import json
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from gesture_constants import GESTURE_IDS

# -- Paths -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SCANS_DIR = DATA_DIR / "scans"
SESSIONS_DIR = DATA_DIR / "sessions"
PATIENT_PATH = DATA_DIR / "patient_profile.json"
VOICE_DIR = DATA_DIR / "voice_cache"

for d in [SCANS_DIR, SESSIONS_DIR, VOICE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# -- App ---------------------------------------------------------------------
app = FastAPI(title="Rehab AI", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -- Brain scan model (lazy-loaded) ------------------------------------------
_scan_model = None
_scan_metadata = None


def _resolve_scan_paths() -> tuple[Path, Path] | None:
    """Prefer models/brain_scan_classifier.* (v2), else legacy brain_scan_efficientnet_b0.*."""
    mdir = BASE_DIR / "models"
    primary = mdir / "brain_scan_classifier.pt"
    meta_p = mdir / "brain_scan_classifier_meta.json"
    if primary.exists():
        return primary, meta_p
    legacy = mdir / "brain_scan_efficientnet_b0.pt"
    meta_l = mdir / "brain_scan_efficientnet_b0_meta.json"
    if legacy.exists():
        return legacy, meta_l
    return None


def _build_scan_classifier(arch: str, num_classes: int, dropout: float):
    """Must match train_brain_scan.build_classifier_model (Dropout + Linear head)."""
    import torch
    from torchvision import models

    arch = arch.lower().strip()
    if arch == "efficientnet_b2":
        m = models.efficientnet_b2(weights=None)
    elif arch == "efficientnet_b1":
        m = models.efficientnet_b1(weights=None)
    else:
        m = models.efficientnet_b0(weights=None)
    in_features = m.classifier[-1].in_features
    m.classifier = torch.nn.Sequential(
        torch.nn.Dropout(p=dropout, inplace=True),
        torch.nn.Linear(in_features, num_classes),
    )
    return m


def _load_scan_model():
    global _scan_model, _scan_metadata
    if _scan_model is not None:
        return

    resolved = _resolve_scan_paths()
    if resolved is None:
        print("[server] Brain scan model not found — scan classification disabled")
        return

    scan_path, meta_path = resolved

    try:
        import torch

        meta: dict[str, Any] = {}
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())

        checkpoint = torch.load(
            str(scan_path), map_location="cpu", weights_only=False,
        )

        for key in ("img_size", "arch", "classifier_dropout", "n_classes"):
            if meta.get(key) is None and key in checkpoint:
                meta[key] = checkpoint[key]

        _scan_metadata = meta

        num_classes = int(meta.get("n_classes", checkpoint.get("n_classes", 7)))
        arch = str(meta.get("arch", checkpoint.get("arch", "efficientnet_b0")))
        dropout = float(meta.get("classifier_dropout", checkpoint.get("classifier_dropout", 0.35)))

        model = _build_scan_classifier(arch, num_classes, dropout)
        state = checkpoint["model_state_dict"]
        try:
            model.load_state_dict(state, strict=True)
        except Exception:
            model.load_state_dict(state, strict=False)
        model.eval()
        _scan_model = model
        print(f"[server] Brain scan model loaded: {arch} | {num_classes} classes | {scan_path.name}")
    except Exception as e:
        print(f"[server] Failed to load scan model: {e}")


def _api_to_legacy_stroke_name(api_prediction: str, raw_prediction: str | None) -> str:
    """Map compact API labels to legacy stroke_analysis keys."""
    if api_prediction == "Uncertain" and raw_prediction:
        api_prediction = raw_prediction
    m = {
        "Hemorrhagic": "Hemorrhagic Stroke",
        "Ischemic": "Ischemic Stroke",
        "Normal": "Normal",
        "Uncertain": "Normal",
        "Rejected": "Normal",
    }
    return m.get(api_prediction, api_prediction if "Stroke" in api_prediction else "Normal")


def _classify_scan(image_path: str) -> dict[str, Any]:
    """
    Brain scan: Part 1 pipeline (grayscale → 224 → CNN/dummy) + Part 2 rule-based region.
    Adds `classification` and `brain_region` payloads alongside legacy fields.
    """
    from ml.brain_scan_pipeline import (
        build_brain_region_for_prediction,
        is_likely_medical_image,
        run_classification,
    )

    import math

    ok_med, reason = is_likely_medical_image(image_path)
    if not ok_med:
        br = build_brain_region_for_prediction("Rejected", 0.0, image_path)
        return {
            "success": True,
            "predicted_class": "Rejected",
            "confidence": 0.0,
            "all_predictions": {},
            "entropy": 1.0,
            "classification": {
                "prediction": "Rejected",
                "confidence": 0.0,
                "top_predictions": [],
                "rejected": True,
                "reject_reason": reason,
            },
            "brain_region": br,
            "warning": "Image does not look like a medical brain scan (heuristic check).",
            "is_low_confidence": True,
            "stroke_analysis": _build_stroke_analysis("Normal", 0.0),
        }

    _load_scan_model()

    part = run_classification(image_path, _scan_model, _scan_metadata)
    api_pred = str(part["prediction"])
    conf = float(part["confidence"])
    raw_pred = part.get("raw_prediction")
    top_list = part.get("top_predictions", [])
    all_preds = {x["label"]: float(x["probability"]) for x in top_list}

    legacy = _api_to_legacy_stroke_name(api_pred, str(raw_pred) if raw_pred else None)
    br = build_brain_region_for_prediction(api_pred, conf, image_path)

    probs_vals = [float(x["probability"]) for x in top_list]
    if probs_vals:
        ent = -sum(p * math.log(p + 1e-10) for p in probs_vals)
        entropy_ratio = ent / math.log(len(probs_vals)) if len(probs_vals) > 1 else 0.0
    else:
        entropy_ratio = 0.0

    result: dict[str, Any] = {
        "success": True,
        "predicted_class": legacy,
        "confidence": round(conf, 4),
        "all_predictions": dict(sorted(all_preds.items(), key=lambda x: x[1], reverse=True)),
        "entropy": round(entropy_ratio, 4),
        "classification": {
            "prediction": api_pred,
            "confidence": conf,
            "top_predictions": top_list,
        },
        "brain_region": br,
    }
    if part.get("uncertain"):
        result["classification"]["uncertain"] = True
        result["warning"] = (
            "Uncertain — model confidence is below 0.7. "
            "Use a clear CT/MRI brain scan or consult a clinician."
        )
        result["is_low_confidence"] = True
    if _scan_model is None:
        result["classification"]["backend"] = "dummy"
        base_w = result.get("warning", "")
        extra = " No model checkpoint found — using random dummy classifier."
        result["warning"] = (base_w + extra).strip()

    result["stroke_analysis"] = _build_stroke_analysis(legacy, conf)

    return result


def _build_stroke_analysis(predicted_class: str, confidence: float) -> dict[str, Any]:
    """Map predicted class to affected brain zones and neuroplasticity guidance."""

    STROKE_ZONE_DATA = {
        "Ischemic Stroke": {
            "stroke_type": "Ischemic",
            "description": "Blood clot blocks blood flow to a brain region, causing oxygen deprivation and tissue death in the affected vascular territory.",
            "affected_zones": [
                {
                    "zone": "Middle Cerebral Artery (MCA) Territory",
                    "region": "lateral",
                    "severity": 0.85,
                    "effects": [
                        "Contralateral hemiparesis (arm > leg)",
                        "Sensory loss on opposite side",
                        "Aphasia (if dominant hemisphere)",
                        "Spatial neglect (if non-dominant hemisphere)",
                    ],
                },
                {
                    "zone": "Frontal Lobe — Motor Cortex",
                    "region": "frontal",
                    "severity": 0.75,
                    "effects": [
                        "Voluntary movement impairment",
                        "Fine motor control deficit",
                        "Motor planning difficulty (apraxia)",
                    ],
                },
                {
                    "zone": "Parietal Lobe — Sensory Cortex",
                    "region": "parietal",
                    "severity": 0.60,
                    "effects": [
                        "Reduced proprioception",
                        "Tactile discrimination impairment",
                        "Difficulty with spatial awareness",
                    ],
                },
                {
                    "zone": "Basal Ganglia",
                    "region": "deep",
                    "severity": 0.45,
                    "effects": [
                        "Movement initiation problems",
                        "Bradykinesia",
                        "Muscle tone abnormalities",
                    ],
                },
            ],
            "neuroplasticity_targets": [
                "Repetitive task-specific training to strengthen surviving neural pathways",
                "Mirror therapy to activate ipsilateral motor cortex",
                "Constraint-induced movement therapy (CIMT) for affected limb",
                "Bilateral arm training for interhemispheric facilitation",
            ],
            "recovery_potential": "High — ischemic penumbra tissue can recover with early rehabilitation. Peak neuroplasticity window: first 3-6 months.",
        },
        "Hemorrhagic Stroke": {
            "stroke_type": "Hemorrhagic",
            "description": "Ruptured blood vessel causes bleeding into brain tissue, creating pressure damage and inflammation in deep brain structures.",
            "affected_zones": [
                {
                    "zone": "Basal Ganglia / Putamen",
                    "region": "deep",
                    "severity": 0.90,
                    "effects": [
                        "Severe contralateral hemiplegia",
                        "Movement coordination breakdown",
                        "Involuntary movements (dyskinesia)",
                    ],
                },
                {
                    "zone": "Internal Capsule",
                    "region": "deep",
                    "severity": 0.85,
                    "effects": [
                        "Dense motor pathway disruption",
                        "Pure motor or sensory stroke pattern",
                        "Corticospinal tract damage",
                    ],
                },
                {
                    "zone": "Thalamus",
                    "region": "deep",
                    "severity": 0.70,
                    "effects": [
                        "Contralateral sensory loss",
                        "Central post-stroke pain",
                        "Attention and memory deficits",
                    ],
                },
                {
                    "zone": "Frontal Lobe (secondary)",
                    "region": "frontal",
                    "severity": 0.40,
                    "effects": [
                        "Executive function impairment",
                        "Motor planning difficulty",
                        "Behavioral changes",
                    ],
                },
            ],
            "neuroplasticity_targets": [
                "Progressive resistance training for deep brain pathway activation",
                "Proprioceptive neuromuscular facilitation (PNF) patterns",
                "Rhythmic auditory stimulation for motor timing recovery",
                "Functional electrical stimulation (FES) assisted training",
            ],
            "recovery_potential": "Moderate — hemorrhagic strokes cause more initial damage but edema resolution allows significant recovery. Timeline: 6-12 months for major gains.",
        },
        "Stroke": {
            "stroke_type": "Stroke (Unspecified)",
            "description": "Brain tissue damage from disrupted blood supply. Further imaging may clarify the specific stroke subtype.",
            "affected_zones": [
                {
                    "zone": "Motor Cortex",
                    "region": "frontal",
                    "severity": 0.70,
                    "effects": [
                        "Contralateral weakness",
                        "Fine motor impairment",
                        "Movement initiation difficulty",
                    ],
                },
                {
                    "zone": "Sensory Cortex",
                    "region": "parietal",
                    "severity": 0.55,
                    "effects": [
                        "Sensory processing deficit",
                        "Proprioception impairment",
                    ],
                },
                {
                    "zone": "White Matter Tracts",
                    "region": "deep",
                    "severity": 0.50,
                    "effects": [
                        "Signal transmission disruption",
                        "Coordination deficits",
                    ],
                },
            ],
            "neuroplasticity_targets": [
                "Task-specific repetitive training",
                "Active range of motion exercises",
                "Bilateral coordination activities",
            ],
            "recovery_potential": "Variable — depends on stroke subtype and size. Early rehabilitation is critical.",
        },
        "Normal": {
            "stroke_type": "None",
            "description": "No stroke pathology detected. Brain scan appears normal.",
            "affected_zones": [],
            "neuroplasticity_targets": [],
            "recovery_potential": "N/A — no stroke detected.",
        },
    }

    DEFAULT_ANALYSIS = {
        "stroke_type": "Non-stroke Condition",
        "description": f"Detected: {predicted_class}. This is not a primary stroke classification.",
        "affected_zones": [],
        "neuroplasticity_targets": [
            "Consult neurologist for condition-specific rehabilitation plan",
        ],
        "recovery_potential": "Varies by condition — specialist evaluation recommended.",
    }

    analysis = STROKE_ZONE_DATA.get(predicted_class, DEFAULT_ANALYSIS)
    return {
        **analysis,
        "predicted_class": predicted_class,
        "confidence": round(confidence, 4),
    }


# -- Session store (in-memory + file-backed) ---------------------------------
_sessions: dict[str, dict] = {}


def _save_session(session_id: str):
    path = SESSIONS_DIR / f"{session_id}.json"
    path.write_text(json.dumps(_sessions[session_id], indent=2, default=str))


def _load_all_sessions() -> list[dict]:
    sessions = []
    for p in sorted(SESSIONS_DIR.glob("*.json"), reverse=True):
        try:
            sessions.append(json.loads(p.read_text()))
        except Exception:
            pass
    return sessions


# -- Models ------------------------------------------------------------------

class PatientProfile(BaseModel):
    name: str = ""
    age: int = 0
    affected_side: str = "right"
    condition: str = ""
    therapist: str = ""
    notes: str = ""

class SessionStart(BaseModel):
    affected_hand: str = "right"
    exercises: list[str] = Field(default_factory=lambda: list(GESTURE_IDS))
    difficulty: str = "medium"
    duration_minutes: int = 5

class SessionUpdate(BaseModel):
    score: int = 0
    gesture: str = ""
    match_pct: float = 0.0
    confidence: float = 0.0


# -- Scan Endpoints ----------------------------------------------------------

@app.post("/api/scan/upload")
async def upload_scan(file: UploadFile = File(...)):
    scan_id = str(uuid.uuid4())[:8]
    ext = Path(file.filename or "scan.jpg").suffix or ".jpg"
    save_path = SCANS_DIR / f"{scan_id}{ext}"

    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    result = _classify_scan(str(save_path))

    scan_record = {
        "scan_id": scan_id,
        "filename": file.filename,
        "path": str(save_path),
        "uploaded_at": datetime.now().isoformat(),
        **result,
    }

    record_path = SCANS_DIR / f"{scan_id}.json"
    record_path.write_text(json.dumps(scan_record, indent=2))

    return scan_record


@app.get("/api/scan/{scan_id}")
async def get_scan(scan_id: str):
    record_path = SCANS_DIR / f"{scan_id}.json"
    if not record_path.exists():
        raise HTTPException(404, "Scan not found")
    return json.loads(record_path.read_text())


@app.get("/api/scans")
async def list_scans():
    scans = []
    for p in sorted(SCANS_DIR.glob("*.json"), reverse=True):
        try:
            scans.append(json.loads(p.read_text()))
        except Exception:
            pass
    return scans


@app.get("/api/scan/latest-analysis")
async def latest_scan_analysis():
    """Return the most recent scan with full stroke zone analysis."""
    scans = []
    for p in sorted(SCANS_DIR.glob("*.json"), reverse=True):
        try:
            scans.append(json.loads(p.read_text()))
        except Exception:
            pass
    if not scans:
        return {"has_scan": False}
    latest = scans[0]
    if "stroke_analysis" not in latest and latest.get("predicted_class"):
        latest["stroke_analysis"] = _build_stroke_analysis(
            latest["predicted_class"], latest.get("confidence", 0)
        )
    return {"has_scan": True, **latest}


# -- Session Endpoints -------------------------------------------------------

@app.post("/api/session/start")
async def start_session(config: SessionStart):
    session_id = str(uuid.uuid4())[:8]
    session = {
        "session_id": session_id,
        "status": "active",
        "started_at": datetime.now().isoformat(),
        "ended_at": None,
        "config": config.model_dump(),
        "score": 0,
        "exercises_completed": 0,
        "total_exercises": len(config.exercises) * 3,
        "timeline": [],
        "duration_seconds": 0,
    }
    _sessions[session_id] = session
    _save_session(session_id)
    return session


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    if session_id in _sessions:
        return _sessions[session_id]
    path = SESSIONS_DIR / f"{session_id}.json"
    if path.exists():
        return json.loads(path.read_text())
    raise HTTPException(404, "Session not found")


@app.post("/api/session/{session_id}/update")
async def update_session(session_id: str, update: SessionUpdate):
    if session_id not in _sessions:
        raise HTTPException(404, "Session not found or not active")

    session = _sessions[session_id]
    session["score"] = update.score
    session["timeline"].append({
        "time": datetime.now().isoformat(),
        "gesture": update.gesture,
        "match_pct": update.match_pct,
        "confidence": update.confidence,
        "score": update.score,
    })
    _save_session(session_id)
    return {"status": "updated"}


@app.post("/api/session/{session_id}/end")
async def end_session(session_id: str):
    if session_id not in _sessions:
        raise HTTPException(404, "Session not found")

    session = _sessions[session_id]
    session["status"] = "completed"
    session["ended_at"] = datetime.now().isoformat()

    start = datetime.fromisoformat(session["started_at"])
    end = datetime.fromisoformat(session["ended_at"])
    session["duration_seconds"] = int((end - start).total_seconds())

    if session["timeline"]:
        matches = [e["match_pct"] for e in session["timeline"]]
        session["avg_match"] = round(sum(matches) / len(matches) * 100, 1)
        session["peak_match"] = round(max(matches) * 100, 1)
        session["exercises_completed"] = len(session["timeline"])

    _save_session(session_id)
    return session


@app.get("/api/sessions")
async def list_sessions():
    return _load_all_sessions()


# -- Patient Profile ---------------------------------------------------------

@app.get("/api/hand/reference")
async def get_hand_reference():
    """Healthy-hand reference JSON (Part 5)."""
    try:
        from reference_store import load_reference
    except ImportError:
        return {}
    ref = load_reference()
    return ref if ref is not None else {}


@app.post("/api/hand/reference")
async def post_hand_reference(payload: dict[str, Any]):
    """Save personalized reference angles (angles + wrist)."""
    try:
        from reference_store import save_reference
    except ImportError:
        raise HTTPException(501, "reference_store not available")
    path = save_reference(payload)
    return {"ok": True, "path": str(path)}


@app.get("/api/patient")
async def get_patient():
    if PATIENT_PATH.exists():
        return json.loads(PATIENT_PATH.read_text())
    return PatientProfile().model_dump()


@app.post("/api/patient")
async def update_patient(profile: PatientProfile):
    PATIENT_PATH.write_text(json.dumps(profile.model_dump(), indent=2))
    return profile.model_dump()


# -- Voice Endpoints ---------------------------------------------------------

@app.post("/api/voice/generate")
async def generate_voices():
    from voice_feedback import VoiceFeedback
    vf = VoiceFeedback()
    results = vf.generate_all()
    return {
        "generated": sum(v for v in results.values()),
        "total": len(results),
        "details": results,
    }


@app.get("/api/voice/status")
async def voice_status():
    from voice_feedback import VoiceFeedback
    vf = VoiceFeedback()
    status = vf.cache_status()
    return {
        "cached": sum(v for v in status.values()),
        "total": len(status),
        "phrases": status,
    }


@app.get("/api/voice/play/{key}")
async def play_voice(key: str):
    path = VOICE_DIR / f"{key}.mp3"
    if not path.exists():
        raise HTTPException(404, f"Voice file not found: {key}")
    return FileResponse(str(path), media_type="audio/mpeg")


# -- WebSocket for real-time session updates ---------------------------------

_ws_connections: dict[str, list[WebSocket]] = {}


@app.websocket("/ws/session/{session_id}")
async def session_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()

    if session_id not in _ws_connections:
        _ws_connections[session_id] = []
    _ws_connections[session_id].append(websocket)

    try:
        while True:
            data = await websocket.receive_json()

            if session_id in _sessions:
                session = _sessions[session_id]
                session["score"] = data.get("score", session["score"])
                session["timeline"].append({
                    "time": datetime.now().isoformat(),
                    **data,
                })

            for ws in _ws_connections.get(session_id, []):
                if ws != websocket:
                    try:
                        await ws.send_json(data)
                    except Exception:
                        pass
    except Exception:
        pass
    finally:
        if session_id in _ws_connections:
            _ws_connections[session_id] = [
                ws for ws in _ws_connections[session_id] if ws != websocket
            ]


# -- Health check ------------------------------------------------------------

@app.get("/api/posses")
async def list_posses_images():
    """List reference images from website/public/posses/ folder."""
    posses_dir = BASE_DIR / "website" / "public" / "posses"
    if not posses_dir.exists():
        return {"images": []}
    images = sorted(
        f.name for f in posses_dir.iterdir()
        if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )
    return {"images": images}


@app.get("/api/health")
async def health():
    _load_scan_model()
    return {
        "status": "ok",
        "scan_model": _scan_model is not None,
        "voice_dir": str(VOICE_DIR),
        "sessions_count": len(list(SESSIONS_DIR.glob("*.json"))),
    }


# -- Static files (posses reference images) ----------------------------------
_posses_dir = BASE_DIR / "website" / "public" / "posses"
if _posses_dir.exists():
    app.mount("/posses", StaticFiles(directory=str(_posses_dir)), name="posses")

# -- Main --------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("  REHAB AI — Backend Server")
    print("  http://localhost:8000")
    print("  Docs: http://localhost:8000/docs")
    print("=" * 60)
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
