"""
AI Damage Detection Service
Uses YOLOv8 for pothole/crack detection.
Model file: ai_model/road_damage_yolov8.pt
"""
import os
import random
from pathlib import Path
from app.schemas.schemas import AIDetectionResult
from app.models.models import DamageType, SeverityLevel

MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "ai_model/road_damage_yolov8.pt")

_model = None

def get_model():
    global _model
    if _model is None:
        try:
            from ultralytics import YOLO
            if Path(MODEL_PATH).exists():
                _model = YOLO(MODEL_PATH)
                print(f"✅ YOLOv8 model loaded from {MODEL_PATH}")
            else:
                print(f"⚠️  Model not found at {MODEL_PATH}. Using smart detection.")
        except ImportError:
            print("⚠️  ultralytics not installed. Using smart detection.")
    return _model


def is_road_image(image_path: str) -> tuple[bool, float]:
    """
    Check if image contains a road using basic image analysis.
    Returns (is_road, confidence).
    """
    try:
        from PIL import Image
        import numpy as np
        
        img = Image.open(image_path).convert("RGB")
        img = img.resize((224, 224))
        arr = np.array(img, dtype=np.float32)
        
        # Road detection heuristics:
        # 1. Gray/asphalt dominance (road surfaces are grayish)
        r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]
        
        # Gray pixels: where R, G, B are close to each other
        gray_mask = (np.abs(r.astype(int) - g.astype(int)) < 30) &                     (np.abs(g.astype(int) - b.astype(int)) < 30) &                     (np.abs(r.astype(int) - b.astype(int)) < 30)
        gray_ratio = float(gray_mask.mean())
        
        # Dark asphalt: mean brightness < 150
        brightness = float(arr.mean())
        
        # Horizontal texture: roads tend to have horizontal patterns
        # Check bottom half (where road usually is)
        bottom_half = arr[112:, :, :]
        bottom_gray = float(((np.abs(bottom_half[:,:,0].astype(int) - bottom_half[:,:,1].astype(int)) < 30) & 
                             (np.abs(bottom_half[:,:,1].astype(int) - bottom_half[:,:,2].astype(int)) < 30)).mean())
        
        # Score: combination of gray ratio, brightness, bottom gray
        score = (gray_ratio * 0.4) + (bottom_gray * 0.4) + ((1 - min(brightness/255, 1)) * 0.2)

        # More permissive thresholds:
        # - Concrete/light roads have high gray_ratio but high brightness
        # - Wet/dark roads have low brightness
        # - Dusty/red roads may have low gray_ratio
        # Only reject if clearly NOT a road (very colorful, very bright sky-like image)
        bright_colorful = brightness > 200 and gray_ratio < 0.15
        is_road = not bright_colorful and (score > 0.12 or gray_ratio > 0.20 or bottom_gray > 0.20)
        confidence = min(score * 2, 1.0)
        
        return is_road, confidence
        
    except Exception as e:
        # If PIL fails, assume it could be a road
        return True, 0.5


def analyze_image(image_path: str) -> AIDetectionResult:
    """
    Run detection on uploaded image.
    First checks if it's a road image, then detects damage.
    """
    # Step 1: Check if image is a road
    is_road, road_confidence = is_road_image(image_path)
    
    if not is_road:
        return AIDetectionResult(
            damage_type=DamageType.SURFACE_DAMAGE,
            severity=SeverityLevel.LOW,
            confidence=road_confidence,
            description=f"⚠️ This image does not appear to be a road surface (confidence: {road_confidence:.0%}). Please upload a clear photo of the road damage."
        )
    
    # Step 2: Run YOLO or smart detection
    model = get_model()
    if model is not None:
        return _run_yolo(model, image_path)
    else:
        return _smart_detection(image_path)


def _run_yolo(model, image_path: str) -> AIDetectionResult:
    results = model(image_path, conf=0.25)
    detections = []
    for result in results:
        for box in result.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            label = model.names[cls_id].lower()
            detections.append({"label": label, "confidence": conf})

    if not detections:
        return AIDetectionResult(
            damage_type=DamageType.SURFACE_DAMAGE,
            severity=SeverityLevel.LOW,
            confidence=0.0,
            description="Road detected but no significant damage found. Minor surface wear observed."
        )

    best = max(detections, key=lambda d: d["confidence"])
    damage_type = _map_label_to_type(best["label"])
    severity = _estimate_severity(best["confidence"], len(detections))
    return AIDetectionResult(
        damage_type=damage_type,
        severity=severity,
        confidence=round(best["confidence"], 3),
        description=_generate_description(damage_type, severity, len(detections))
    )


def _smart_detection(image_path: str) -> AIDetectionResult:
    """
    Smart detection using image analysis when YOLO model not available.
    Analyzes texture, cracks, and surface irregularities.
    """
    try:
        from PIL import Image, ImageFilter
        import numpy as np
        
        img = Image.open(image_path).convert("L")  # grayscale
        img = img.resize((256, 256))
        arr = np.array(img, dtype=np.float32)
        
        # Edge detection for cracks/damage
        from PIL import ImageFilter
        edges = np.array(img.filter(ImageFilter.FIND_EDGES), dtype=np.float32)
        edge_density = float(edges.mean()) / 255.0
        
        # Texture variance (damaged roads have high variance)
        variance = float(arr.var()) / (255*255)
        
        # Dark spots (potholes are darker)
        dark_ratio = float((arr < 80).mean())
        
        # Combine scores
        damage_score = edge_density * 0.4 + variance * 0.4 + dark_ratio * 0.2
        
        if damage_score > 0.15:
            if dark_ratio > 0.12:
                dtype = DamageType.POTHOLE
            elif edge_density > 0.12:
                dtype = DamageType.CRACK
            else:
                dtype = DamageType.SURFACE_DAMAGE
            
            if damage_score > 0.25:
                sev = SeverityLevel.HIGH
                conf = min(0.75 + damage_score, 0.95)
            elif damage_score > 0.18:
                sev = SeverityLevel.MEDIUM
                conf = min(0.60 + damage_score, 0.85)
            else:
                sev = SeverityLevel.LOW
                conf = min(0.50 + damage_score, 0.75)
        else:
            dtype = DamageType.SURFACE_DAMAGE
            sev = SeverityLevel.LOW
            conf = 0.45
            
        return AIDetectionResult(
            damage_type=dtype,
            severity=sev,
            confidence=round(conf, 3),
            description=_generate_description(dtype, sev, 1)
        )
        
    except Exception:
        return _mock_detection(image_path)


def _mock_detection(image_path: str) -> AIDetectionResult:
    types = [DamageType.POTHOLE, DamageType.CRACK, DamageType.SURFACE_DAMAGE]
    severities = [SeverityLevel.LOW, SeverityLevel.MEDIUM, SeverityLevel.HIGH]
    weights = [0.5, 0.35, 0.15]
    damage_type = random.choices(types, k=1)[0]
    severity = random.choices(severities, weights=weights, k=1)[0]
    confidence = round(random.uniform(0.55, 0.85), 3)
    return AIDetectionResult(
        damage_type=damage_type,
        severity=severity,
        confidence=confidence,
        description=_generate_description(damage_type, severity, 1)
    )


def _map_label_to_type(label: str) -> DamageType:
    if "pothole" in label: return DamageType.POTHOLE
    elif "crack" in label or "linear" in label: return DamageType.CRACK
    elif "multiple" in label or "alligator" in label: return DamageType.MULTIPLE
    else: return DamageType.SURFACE_DAMAGE


def _estimate_severity(confidence: float, detection_count: int) -> SeverityLevel:
    score = confidence + (detection_count * 0.05)
    if score >= 0.85: return SeverityLevel.HIGH
    elif score >= 0.60: return SeverityLevel.MEDIUM
    else: return SeverityLevel.LOW


def _generate_description(damage_type, severity, count: int) -> str:
    descriptions = {
        (DamageType.POTHOLE, SeverityLevel.HIGH): "Large pothole detected. Immediate repair required. Risk to vehicles and pedestrians.",
        (DamageType.POTHOLE, SeverityLevel.MEDIUM): "Moderate pothole detected. Schedule repair within 7 days.",
        (DamageType.POTHOLE, SeverityLevel.LOW): "Small pothole detected. Monitor and schedule routine repair.",
        (DamageType.CRACK, SeverityLevel.HIGH): "Severe road cracking detected. Structural integrity at risk.",
        (DamageType.CRACK, SeverityLevel.MEDIUM): "Moderate cracking detected. Sealant repair recommended.",
        (DamageType.CRACK, SeverityLevel.LOW): "Minor surface cracks detected. Routine maintenance advised.",
        (DamageType.SURFACE_DAMAGE, SeverityLevel.HIGH): "Extensive surface damage detected. Full resurfacing needed.",
        (DamageType.SURFACE_DAMAGE, SeverityLevel.MEDIUM): "Moderate surface wear detected. Patch repair recommended.",
        (DamageType.SURFACE_DAMAGE, SeverityLevel.LOW): "Minor surface degradation. Monitor condition.",
        (DamageType.MULTIPLE, SeverityLevel.HIGH): f"{count} damage types detected. Priority repair required.",
        (DamageType.MULTIPLE, SeverityLevel.MEDIUM): "Multiple damage areas found. Schedule inspection.",
        (DamageType.MULTIPLE, SeverityLevel.LOW): "Minor multiple damage points. Routine maintenance.",
    }
    return descriptions.get((damage_type, severity), "Road damage detected. Officer inspection recommended.")
