"""Ai service · PY
RoadWatch AI Service — YOLOv8 Road Damage Detection
────────────────────────────────────────────────────
Public API consumed by complaints.py:

  analyze_image(image_path)  → DamageResult
  is_road_image(image_path)  → (bool, float)
  image_hash(img_bytes)      → str   (MD5 hex digest)

Model loading:
  - Reads YOLO_MODEL_PATH env var (default: ../ai_model/road_damage_yolov8.pt)
  - Reads YOLO_CONF env var for confidence threshold (default: 0.45).
    Also accepts YOLO_CONFIDENCE_THRESHOLD as a legacy alias.
  - If the .pt file is missing the service falls back to a deterministic mock
    that returns consistent results per-image (seeded by file content hash).

DamageResult dataclass:
  class_name  — normalised damage type: pothole | crack | surface_damage | multiple
  confidence  — float 0.0–1.0 (highest detection confidence across all boxes)
  bbox        — [x1, y1, x2, y2] in pixel coords, or [] if no detection
  severity    — 4-band label derived from confidence:
                  >= 0.80  →  "critical"
                  >= 0.60  →  "high"
                  >= 0.40  →  "medium"
                  <  0.40  →  "low"

Class mapping (RDD2022 → RoadWatch canonical):
  D00, D10 → crack
  D20      → surface_damage
  D40      → pothole
  If >= 2 distinct normalised classes detected → "multiple"
"""

import hashlib
import logging
import os
import random
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────
MODEL_PATH: str = os.getenv("YOLO_MODEL_PATH", "../ai_model/road_damage_yolov8.pt")

# Support YOLO_CONF (primary) and YOLO_CONFIDENCE_THRESHOLD (legacy alias)
_raw_conf: str = os.getenv("YOLO_CONF") or os.getenv("YOLO_CONFIDENCE_THRESHOLD", "0.45")
try:
    CONF_THRESHOLD: float = float(_raw_conf)
except ValueError:
    logger.warning("[AI] Invalid YOLO_CONF value '%s' — using default 0.45", _raw_conf)
    CONF_THRESHOLD = 0.45

MIN_FILE_BYTES: int = 1_000
MAX_FILE_BYTES: int = 20 * 1024 * 1024  # 20 MB

ROAD_VALID_CLASSES: set[str] = {"pothole", "crack", "surface_damage", "multiple"}

# Raw YOLO class-name → normalised RoadWatch name
_CLASS_MAP: dict[str, str] = {
    # RDD2022 code names
    "D00": "crack",
    "D10": "crack",
    "D20": "surface_damage",
    "D40": "pothole",
    # Human-readable names (for models trained with these labels)
    "pothole": "pothole",
    "crack": "crack",
    "surface_damage": "surface_damage",
    "multiple": "multiple",
    "multiple_damage": "multiple",
}

# ── LRU analysis cache ────────────────────────────────────────────────
_CACHE_SIZE: int = 128
_analysis_cache: OrderedDict = OrderedDict()

# ── Lazy model singleton ──────────────────────────────────────────────
_model = None
_model_tried: bool = False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DamageResult — typed return value for analyze_image()
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@dataclass
class DamageResult:
    """
    Typed result returned by analyze_image().

    Attributes
    ----------
    class_name  Normalised damage type: pothole | crack | surface_damage | multiple
    confidence  Highest detection confidence, range 0.0–1.0
    bbox        Bounding box [x1, y1, x2, y2] in pixels; empty list if no detection
    severity    4-band severity: critical | high | medium | low
    is_mock     True when real model was unavailable and mock mode ran
    """

    class_name: str
    confidence: float
    bbox: list[float] = field(default_factory=list)
    severity: str = "low"
    is_mock: bool = False

    @property
    def description(self) -> str:
        prefix = "[MOCK] " if self.is_mock else ""
        label = self.class_name.replace("_", " ")
        return (
            f"{prefix}{self.severity.title()} severity "
            f"{label} detected with {self.confidence:.0%} confidence."
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PUBLIC API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def image_hash(data: bytes) -> str:
    """MD5 hex digest of raw image bytes — used for duplicate detection."""
    return hashlib.md5(data).hexdigest()


def is_road_image(image_path: str) -> tuple[bool, float]:
    """
    Lightweight gate: is this upload a plausible road-damage photo?

    Returns (is_road, confidence).

    Model loaded — runs a quick inference pass. Accepts if ANY detection
    has confidence > 0.30.
    Mock mode  — validates JPEG / PNG / WebP magic bytes, returns fixed 0.80.
    """
    try:
        size = os.path.getsize(image_path)
    except OSError:
        return False, 0.0
    if size < MIN_FILE_BYTES or size > MAX_FILE_BYTES:
        return False, 0.0

    try:
        with open(image_path, "rb") as fh:
            header = fh.read(12)
    except OSError:
        return False, 0.0

    jpeg = header[:3] == b"\xff\xd8\xff"
    png = header[:8] == b"\x89PNG\r\n\x1a\n"
    webp = header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    if not (jpeg or png or webp):
        return False, 0.0

    model = load_model()
    if model is not None:
        try:
            results = model(image_path, conf=0.10, verbose=False)
            if results and results[0].boxes is not None and len(results[0].boxes) > 0:
                max_conf = float(results[0].boxes.conf.max())
                return (max_conf > 0.30), round(max_conf, 3)
            return False, 0.0
        except Exception as exc:
            logger.warning("[AI] is_road_image inference error: %s — accepting with fallback", exc)
            return True, 0.50

    # Mock mode: accept any valid image format
    return True, 0.80


def analyze_image(image_path: str) -> DamageResult:
    """
    Analyse a road-damage image and return a typed DamageResult.

    Results are LRU-cached keyed on a partial file-content hash so the same
    image is never processed twice within the same process lifetime.
    """
    try:
        with open(image_path, "rb") as f:
            file_hash = hashlib.md5(f.read(8192)).hexdigest()
    except OSError:
        file_hash = image_path

    if file_hash in _analysis_cache:
        _analysis_cache.move_to_end(file_hash)
        return _analysis_cache[file_hash]

    model = load_model()
    if model is not None:
        from app.services.preprocess_service import (
            preprocess_for_inference, TTA_ENABLED
        )
        import os
        
        temp_files = []
        try:
            primary_path, tta_paths = preprocess_for_inference(image_path)
            temp_files = [p for p in [primary_path] + tta_paths 
                          if p != image_path]
            
            if TTA_ENABLED and len(tta_paths) > 1:
                # Ensemble: run inference on all variants, merge results
                all_results = []
                for path in tta_paths:
                    r = _yolo_analyze(model, path)
                    if r is not None:
                        all_results.append(r)
                
                if not all_results:
                    result = _low_confidence_result()
                else:
                    # Pick result with highest confidence (simple ensemble)
                    result = max(all_results, key=lambda r: r.confidence)
            else:
                r = _yolo_analyze(model, primary_path)
                result = r if r else _low_confidence_result()
        
        except Exception as e:
            logger.error("analyze_image failed: %s", e, exc_info=True)
            result = _low_confidence_result()
        
        finally:
            for tf in temp_files:
                try:
                    os.unlink(tf)
                except OSError:
                    pass
    else:
        result = _mock(image_path)

    _analysis_cache[file_hash] = result
    if len(_analysis_cache) > _CACHE_SIZE:
        _analysis_cache.popitem(last=False)

    return result

def _low_confidence_result() -> DamageResult:
    return DamageResult(
        class_name="unknown",
        confidence=0.0,
        bbox=[],
        severity="low",
        is_mock=False,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  INTERNAL HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def export_to_onnx(pt_path: str) -> str:
    """
    Export best.pt to best.onnx in same directory.
    Returns path to .onnx file.
    Skips if .onnx already exists and is newer than .pt.
    """
    from ultralytics import YOLO
    
    pt_path = Path(pt_path)
    onnx_path = pt_path.with_suffix('.onnx')
    
    # Skip if already exported and up to date
    if onnx_path.exists():
        if onnx_path.stat().st_mtime >= pt_path.stat().st_mtime:
            logger.info("ONNX model already up to date: %s", onnx_path)
            return str(onnx_path)
    
    logger.info("Exporting %s to ONNX...", pt_path)
    model = YOLO(str(pt_path))
    model.export(
        format='onnx',
        imgsz=640,
        simplify=True,
        opset=17,
        dynamic=False,
    )
    logger.info("ONNX export complete: %s", onnx_path)
    return str(onnx_path)


def load_model():
    """
    Load model at startup. Priority:
    1. Use .onnx if it exists alongside the .pt (fastest, CPU-optimized)
    2. Export to .onnx if USE_ONNX=true env var is set
    3. Fall back to .pt (PyTorch, slower but always works)
    4. Fall back to mock mode if no model file found
    """
    global _model, _mock_mode
    
    model_path = os.getenv("YOLO_MODEL_PATH", "")
    use_onnx = os.getenv("USE_ONNX", "false").lower() == "true"
    
    if not model_path or not os.path.exists(model_path):
        logger.warning(
            "YOLO_MODEL_PATH not set or file not found — running in MOCK mode"
        )
        _mock_mode = True
        return
    
    try:
        from ultralytics import YOLO
        from pathlib import Path
        
        pt_path = Path(model_path)
        onnx_path = pt_path.with_suffix('.onnx')
        
        if onnx_path.exists():
            logger.info("Loading ONNX model: %s", onnx_path)
            _model = YOLO(str(onnx_path), task='detect')
        elif use_onnx:
            logger.info("USE_ONNX=true — exporting to ONNX first...")
            onnx_file = export_to_onnx(str(pt_path))
            _model = YOLO(onnx_file, task='detect')
        else:
            logger.info("Loading PyTorch model: %s", pt_path)
            _model = YOLO(str(pt_path))
        
        _mock_mode = False
        logger.info("Model loaded successfully. Mock mode: OFF")
    
    except Exception as e:
        logger.error("Failed to load model: %s — falling back to MOCK mode", e)
        _mock_mode = True
    return _model


def _severity(conf: float) -> str:
    """
    Map a raw confidence score to a 4-band severity label.

    Thresholds:
        >= 0.80  →  "critical"
        >= 0.60  →  "high"
        >= 0.40  →  "medium"
        <  0.40  →  "low"
    """
    if conf >= 0.80:
        return "critical"
    if conf >= 0.60:
        return "high"
    if conf >= 0.40:
        return "medium"
    return "low"


def _normalise_class(raw_name: str) -> str:
    """Map any raw YOLO class name to one of the 4 canonical damage types."""
    return _CLASS_MAP.get(raw_name, "pothole")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  INTERNAL — real YOLO inference path
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _yolo_analyze(model: Any, path: str) -> DamageResult:
    """
    Run YOLOv8 inference at CONF_THRESHOLD and return a DamageResult.

    Algorithm:
      1. Run model at CONF_THRESHOLD — only keep boxes above it.
      2. Collect normalised class for each surviving box.
      3. If >= 2 distinct normalised classes → class_name = "multiple".
      4. Otherwise use the class of the highest-confidence box.
      5. confidence = max box confidence; bbox = xyxy coords of that box.
    """
    results = model(path, conf=CONF_THRESHOLD, verbose=False)

    if not results or results[0].boxes is None or len(results[0].boxes) == 0:
        return DamageResult(
            class_name="surface_damage",
            confidence=0.0,
            bbox=[],
            severity="low",
            is_mock=False,
        )

    boxes = results[0].boxes
    detected_classes: set[str] = set()
    best_conf: float = 0.0
    best_class_raw: str = ""
    best_bbox: list[float] = []

    for i in range(len(boxes)):
        cls_id = int(boxes.cls[i])
        conf_val = float(boxes.conf[i])
        raw_name = model.names.get(cls_id, f"class_{cls_id}")
        norm = _normalise_class(raw_name)
        detected_classes.add(norm)

        if conf_val > best_conf:
            best_conf = conf_val
            best_class_raw = raw_name
            try:
                best_bbox = [round(float(v), 2) for v in boxes.xyxy[i].tolist()]
            except Exception:
                best_bbox = []

    class_name = "multiple" if len(detected_classes) >= 2 else _normalise_class(best_class_raw)
    conf = round(best_conf, 4)

    return DamageResult(
        class_name=class_name,
        confidence=conf,
        bbox=best_bbox,
        severity=_severity(conf),
        is_mock=False,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  INTERNAL — deterministic mock (no model file present)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _mock(path: str) -> DamageResult:
    """
    Deterministic mock — same file always produces the same result.
    Uses an MD5-seeded RNG so output is reproducible across restarts.
    """
    seed = 42
    try:
        with open(path, "rb") as f:
            seed = int(hashlib.md5(f.read(2048)).hexdigest()[:8], 16)
    except Exception:
        pass

    rng = random.Random(seed)
    damages = ["pothole", "crack", "surface_damage", "multiple"]
    class_name = rng.choices(damages, weights=[0.45, 0.30, 0.15, 0.10])[0]
    conf = round(rng.uniform(0.30, 0.95), 4)

    return DamageResult(
        class_name=class_name,
        confidence=conf,
        bbox=[],
        severity=_severity(conf),
        is_mock=True,
    )
