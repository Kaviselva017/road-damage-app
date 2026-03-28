"""
AI Damage Detection Service
Uses YOLOv8 for pothole/crack detection when available.
Falls back to deterministic PIL heuristics when the model runtime is unavailable.
"""
import logging
import os
from pathlib import Path

from app.models.models import DamageType, SeverityLevel
from app.schemas.schemas import AIDetectionResult

BASE_DIR = Path(__file__).resolve().parents[2]
MODEL_PATH = os.getenv("YOLO_MODEL_PATH", str(BASE_DIR / "ai_model" / "road_damage_yolov8.pt"))

_model = None
logger = logging.getLogger(__name__)


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _manual_review_result() -> AIDetectionResult:
    return AIDetectionResult(
        damage_type=DamageType.SURFACE_DAMAGE,
        severity=SeverityLevel.MEDIUM,
        confidence=0.0,
        description="Road image accepted, but automated damage analysis is unavailable. Officer review required.",
    )


def get_model():
    global _model
    if _model is None:
        try:
            from ultralytics import YOLO

            if Path(MODEL_PATH).exists():
                _model = YOLO(MODEL_PATH)
                logger.info("YOLOv8 model loaded from %s", MODEL_PATH)
            else:
                logger.warning("YOLO model not found at %s. Using heuristic detection.", MODEL_PATH)
        except ImportError:
            logger.warning("ultralytics is not installed. Using heuristic detection.")
    return _model


def is_road_image(image_path: str) -> tuple[bool, float]:
    """
    Check if image contains a road using lightweight PIL heuristics.
    Returns (is_road, confidence).
    """
    try:
        from PIL import Image, ImageFilter, ImageStat

        with Image.open(image_path) as opened:
            rgb = opened.convert("RGB").resize((224, 224))

        hsv = rgb.convert("HSV")
        gray = rgb.convert("L")
        bottom_rgb = rgb.crop((0, 112, 224, 224))
        bottom_gray = bottom_rgb.convert("L")
        edge_image = gray.filter(ImageFilter.FIND_EDGES)

        brightness = ImageStat.Stat(gray).mean[0] / 255.0
        saturation = ImageStat.Stat(hsv).mean[1] / 255.0
        edge_density = ImageStat.Stat(edge_image).mean[0] / 255.0
        variance = _clamp(ImageStat.Stat(gray).var[0] / (255.0 * 255.0))
        bottom_variance = _clamp(ImageStat.Stat(bottom_gray).var[0] / (255.0 * 255.0))

        sample_pixels = list(rgb.getdata())[::8]
        bottom_pixels = list(bottom_rgb.getdata())[::4]

        def _ratio(pixels, predicate) -> float:
            if not pixels:
                return 0.0
            matches = sum(1 for pixel in pixels if predicate(pixel))
            return matches / len(pixels)

        gray_ratio = _ratio(sample_pixels, lambda pixel: max(pixel) - min(pixel) <= 32)
        bottom_gray_ratio = _ratio(bottom_pixels, lambda pixel: max(pixel) - min(pixel) <= 34)
        green_ratio = _ratio(
            sample_pixels,
            lambda pixel: pixel[1] > pixel[0] + 18 and pixel[1] > pixel[2] + 18,
        )
        blue_ratio = _ratio(
            sample_pixels,
            lambda pixel: pixel[2] > pixel[0] + 18 and pixel[2] > pixel[1] + 18,
        )

        texture_score = _clamp((edge_density * 2.8) + (variance * 3.5) + (bottom_variance * 2.2))
        road_score = (
            gray_ratio * 0.34
            + bottom_gray_ratio * 0.28
            + (1.0 - saturation) * 0.18
            + texture_score * 0.15
            + (1.0 - min(abs(brightness - 0.5) * 1.5, 1.0)) * 0.05
        )
        road_score -= (green_ratio * 0.22) + (blue_ratio * 0.18)
        road_score = _clamp(road_score)

        obviously_non_road = any(
            (
                brightness > 0.85 and edge_density < 0.02 and variance < 0.01,
                saturation > 0.45 and gray_ratio < 0.16 and bottom_gray_ratio < 0.18,
                green_ratio > 0.24 and bottom_gray_ratio < 0.18,
                blue_ratio > 0.26 and bottom_gray_ratio < 0.18,
            )
        )

        is_road = road_score >= 0.32 and not obviously_non_road
        confidence = _clamp(road_score if is_road else 1.0 - road_score, 0.5, 0.99)
        return is_road, round(confidence, 3)
    except Exception as exc:
        logger.warning("Road-image validation failed for %s: %s", image_path, exc)
        return False, 0.0


def analyze_image(image_path: str) -> AIDetectionResult:
    """
    Run detection on uploaded image.
    First checks if it's a road image, then detects damage.
    """
    is_road, road_confidence = is_road_image(image_path)

    if not is_road:
        return AIDetectionResult(
            damage_type=DamageType.SURFACE_DAMAGE,
            severity=SeverityLevel.LOW,
            confidence=road_confidence,
            description=(
                "This image does not appear to be a road surface "
                f"(confidence: {road_confidence:.0%}). Please upload a clear photo of the road damage."
            ),
        )

    model = get_model()
    if model is not None:
        return _run_yolo(model, image_path)
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
            description="Road detected but no significant damage found. Minor surface wear observed.",
        )

    best = max(detections, key=lambda detection: detection["confidence"])
    damage_type = _map_label_to_type(best["label"])
    severity = _estimate_severity(best["confidence"], len(detections))
    return AIDetectionResult(
        damage_type=damage_type,
        severity=severity,
        confidence=round(best["confidence"], 3),
        description=_generate_description(damage_type, severity, len(detections)),
    )


def _smart_detection(image_path: str) -> AIDetectionResult:
    """
    Deterministic heuristic detection used when YOLO is unavailable.
    """
    try:
        from PIL import Image, ImageFilter, ImageStat

        with Image.open(image_path) as opened:
            gray = opened.convert("L").resize((256, 256))

        edges = gray.filter(ImageFilter.FIND_EDGES)
        edge_density = ImageStat.Stat(edges).mean[0] / 255.0
        variance = _clamp(ImageStat.Stat(gray).var[0] / (255.0 * 255.0))

        pixels = list(gray.getdata())
        if not pixels:
            return _manual_review_result()

        dark_ratio = sum(1 for pixel in pixels if pixel < 80) / len(pixels)
        mid_dark_ratio = sum(1 for pixel in pixels if pixel < 120) / len(pixels)
        damage_score = (
            edge_density * 0.42
            + variance * 0.33
            + dark_ratio * 0.15
            + mid_dark_ratio * 0.10
        )

        if damage_score > 0.15:
            if dark_ratio > 0.12:
                damage_type = DamageType.POTHOLE
            elif edge_density > 0.12:
                damage_type = DamageType.CRACK
            else:
                damage_type = DamageType.SURFACE_DAMAGE

            if damage_score > 0.25:
                severity = SeverityLevel.HIGH
                confidence = min(0.75 + damage_score, 0.95)
            elif damage_score > 0.18:
                severity = SeverityLevel.MEDIUM
                confidence = min(0.60 + damage_score, 0.85)
            else:
                severity = SeverityLevel.LOW
                confidence = min(0.50 + damage_score, 0.75)
        else:
            damage_type = DamageType.SURFACE_DAMAGE
            severity = SeverityLevel.LOW
            confidence = 0.45

        return AIDetectionResult(
            damage_type=damage_type,
            severity=severity,
            confidence=round(confidence, 3),
            description=_generate_description(damage_type, severity, 1),
        )
    except Exception as exc:
        logger.warning("Heuristic damage detection failed for %s: %s", image_path, exc)
        return _manual_review_result()


def _map_label_to_type(label: str) -> DamageType:
    if "pothole" in label:
        return DamageType.POTHOLE
    if "crack" in label or "linear" in label:
        return DamageType.CRACK
    if "multiple" in label or "alligator" in label:
        return DamageType.MULTIPLE
    return DamageType.SURFACE_DAMAGE


def _estimate_severity(confidence: float, detection_count: int) -> SeverityLevel:
    score = confidence + (detection_count * 0.05)
    if score >= 0.85:
        return SeverityLevel.HIGH
    if score >= 0.60:
        return SeverityLevel.MEDIUM
    return SeverityLevel.LOW


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
