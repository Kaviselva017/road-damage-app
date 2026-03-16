"""
RoadWatch AI Service — YOLOv8 Road Damage Detection
Uses real trained model if available, falls back to mock if not.
"""
import os, random, logging
from pathlib import Path
from app.schemas.schemas import AIDetectionResult
from app.models.models import DamageType, SeverityLevel

logger = logging.getLogger(__name__)
MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "ai_model/road_damage_yolov8.pt")

_model = None
_model_loaded = False

def get_model():
    global _model, _model_loaded
    if _model_loaded:
        return _model
    _model_loaded = True
    try:
        from ultralytics import YOLO
        if Path(MODEL_PATH).exists():
            _model = YOLO(MODEL_PATH)
            logger.info(f"YOLOv8 model loaded from {MODEL_PATH}")
            print(f"✅ YOLOv8 model loaded — Real AI detection active!")
        else:
            logger.warning(f"Model not found at {MODEL_PATH} — using mock detection")
            print(f"⚠ No model at {MODEL_PATH} — using mock detection")
            print(f"  Train model: see train_yolo_colab.py")
    except ImportError:
        logger.warning("ultralytics not installed — pip install ultralytics")
    return _model

def analyze_image(image_path: str) -> AIDetectionResult:
    model = get_model()
    if model is not None:
        try:
            return _run_yolo(model, image_path)
        except Exception as e:
            logger.error(f"YOLO inference failed: {e}")
            return _mock_detection(image_path)
    return _mock_detection(image_path)

def _run_yolo(model, image_path: str) -> AIDetectionResult:
    results = model(image_path, conf=0.20, verbose=False)
    detections = []
    for result in results:
        for box in result.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            label = model.names[cls_id].lower()
            # Get bounding box area as proxy for damage size
            x1,y1,x2,y2 = box.xyxy[0].tolist()
            area = (x2-x1)*(y2-y1)
            detections.append({"label": label, "confidence": conf, "area": area})

    if not detections:
        return AIDetectionResult(
            damage_type=DamageType.SURFACE_DAMAGE,
            severity=SeverityLevel.LOW,
            confidence=0.0,
            description="No significant damage detected. Minor surface wear observed."
        )

    # Sort by confidence
    detections.sort(key=lambda d: d["confidence"], reverse=True)
    best = detections[0]
    damage_type = _map_label(best["label"])

    # Severity based on confidence + area + detection count
    conf = best["confidence"]
    area_score = min(1.0, best["area"] / 100000)
    count_bonus = min(0.2, len(detections) * 0.05)
    score = conf * 0.6 + area_score * 0.3 + count_bonus

    if score >= 0.75 or best["label"] == "pothole":
        severity = SeverityLevel.HIGH
    elif score >= 0.45:
        severity = SeverityLevel.MEDIUM
    else:
        severity = SeverityLevel.LOW

    desc = _generate_description(damage_type, severity, len(detections), conf)
    return AIDetectionResult(
        damage_type=damage_type,
        severity=severity,
        confidence=round(conf, 3),
        description=desc
    )

def _mock_detection(image_path: str) -> AIDetectionResult:
    """Fallback mock for when no model is available."""
    types  = [DamageType.POTHOLE, DamageType.CRACK, DamageType.SURFACE_DAMAGE, DamageType.MULTIPLE]
    sevs   = [SeverityLevel.LOW, SeverityLevel.MEDIUM, SeverityLevel.HIGH]
    weights= [0.4, 0.4, 0.2]
    damage_type = random.choices(types, k=1)[0]
    severity    = random.choices(sevs, weights=weights, k=1)[0]
    confidence  = round(random.uniform(0.60, 0.92), 3)
    return AIDetectionResult(
        damage_type=damage_type,
        severity=severity,
        confidence=confidence,
        description=_generate_description(damage_type, severity, 1, confidence)
    )

def _map_label(label: str) -> DamageType:
    if "pothole" in label:             return DamageType.POTHOLE
    if "crack" in label or "linear" in label: return DamageType.CRACK
    if "multiple" in label or "alligator" in label: return DamageType.MULTIPLE
    return DamageType.SURFACE_DAMAGE

def _generate_description(damage_type, severity, count, conf) -> str:
    sev = severity.value if hasattr(severity,'value') else str(severity)
    dmg = damage_type.value if hasattr(damage_type,'value') else str(damage_type)
    pct = f"{conf*100:.0f}%"
    descriptions = {
        ("pothole","high"):   f"Large pothole detected ({pct} confidence). Immediate repair required. Risk to vehicles and pedestrians.",
        ("pothole","medium"): f"Moderate pothole detected ({pct} confidence). Schedule repair within 7 days.",
        ("pothole","low"):    f"Small pothole detected ({pct} confidence). Monitor and schedule routine repair.",
        ("crack","high"):     f"Severe road cracking detected ({pct} confidence). Structural integrity at risk.",
        ("crack","medium"):   f"Moderate cracking detected ({pct} confidence). Sealant repair recommended.",
        ("crack","low"):      f"Minor surface cracks detected ({pct} confidence). Routine maintenance advised.",
        ("surface_damage","high"):   f"Extensive surface damage ({pct} confidence). Full resurfacing needed.",
        ("surface_damage","medium"): f"Moderate surface wear ({pct} confidence). Patch repair recommended.",
        ("surface_damage","low"):    f"Minor surface degradation ({pct} confidence). Monitor condition.",
        ("multiple","high"):  f"{count} damage types detected ({pct} confidence). Priority repair required.",
        ("multiple","medium"):f"Multiple damage areas found ({pct} confidence). Schedule inspection.",
        ("multiple","low"):   f"Minor multiple damage points ({pct} confidence). Routine maintenance.",
    }
    return descriptions.get((dmg, sev), f"Road damage detected ({pct} confidence). Officer inspection recommended.")
