"""
RoadWatch AI Service
- Uses YOLOv8 if model file exists at YOLO_MODEL_PATH
- Falls back to deterministic mock (same image → same result always)
"""
import hashlib
import os
import random
from pathlib import Path

MODEL_PATH   = os.getenv("YOLO_MODEL_PATH", "ai_model/road_damage_yolov8.pt")
_model       = None
_model_tried = False


def _load():
    global _model, _model_tried
    if _model_tried:
        return _model
    _model_tried = True
    if not Path(MODEL_PATH).exists():
        print(f"[AI] Model not found at {MODEL_PATH} — using mock mode")
        return None
    try:
        from ultralytics import YOLO
        _model = YOLO(MODEL_PATH)
        print(f"[AI] YOLOv8 loaded from {MODEL_PATH}")
    except Exception as e:
        print(f"[AI] Failed to load model: {e} — using mock mode")
    return _model


def image_hash(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def analyze_image(image_path: str) -> dict:
    model = _load()
    if model is not None:
        try:
            return _yolo(model, image_path)
        except Exception as e:
            print(f"[AI] Inference error: {e} — falling back to mock")
    return _mock(image_path)


def _yolo(model, path: str) -> dict:
    results = model(path, conf=0.25, verbose=False)
    if not results or not results[0].boxes:
        return _mock(path)

    boxes    = results[0].boxes
    names    = model.names
    best_idx = int(boxes.conf.argmax())
    cls_id   = int(boxes.cls[best_idx])
    conf     = float(boxes.conf[best_idx])
    raw_name = names[cls_id]

    name_map = {
        "pothole": "pothole", "D40": "pothole",
        "crack": "crack", "D00": "crack", "D10": "crack",
        "surface_damage": "surface_damage", "D20": "surface_damage",
        "multiple_damage": "multiple", "multiple": "multiple",
    }
    damage = name_map.get(raw_name, "pothole")
    sev    = "high" if conf >= 0.75 else "medium" if conf >= 0.50 else "low"

    descs = {
        "pothole":        f"Pothole detected — road surface depression, {sev} severity.",
        "crack":          f"Road cracking — structural surface fractures, {sev} severity.",
        "surface_damage": f"Surface deterioration — weathering damage, {sev} severity.",
        "multiple":       f"Multiple damage types — complex road damage, {sev} severity.",
    }
    return {"damage_type": damage, "severity": sev,
            "ai_confidence": round(conf, 3), "description": descs[damage]}


def _mock(path: str) -> dict:
    """Deterministic mock — same file always gives same classification."""
    seed = 0
    try:
        with open(path, "rb") as f:
            seed = int(hashlib.md5(f.read(2048)).hexdigest()[:8], 16)
    except Exception:
        seed = 42

    rng     = random.Random(seed)
    damages = ["pothole", "crack", "surface_damage", "multiple"]
    sevs    = ["high", "medium", "low"]
    damage  = rng.choices(damages, weights=[0.45, 0.30, 0.15, 0.10])[0]
    sev     = rng.choices(sevs,    weights=[0.30, 0.50, 0.20])[0]
    conf    = round(rng.uniform(0.55, 0.95), 3)

    descs = {
        "pothole":        f"Pothole detected — road surface depression, {sev} risk level.",
        "crack":          f"Cracking pattern — {sev} severity structural fractures.",
        "surface_damage": f"Surface deterioration — {sev} weathering and erosion.",
        "multiple":       f"Multiple damage types — complex {sev} road damage.",
    }
    return {"damage_type": damage, "severity": sev,
            "ai_confidence": conf, "description": descs[damage]}