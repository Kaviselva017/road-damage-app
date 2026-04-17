"""
RoadWatch AI Service — YOLOv8 Road Damage Detection
────────────────────────────────────────────────────
Public API consumed by complaints.py:

  analyze_image(image_path)  → dict  (damage_type, severity, ai_confidence, description)
  is_road_image(image_path)  → (bool, float)
  image_hash(img_bytes)      → str   (MD5 hex digest)

Model loading:
  - Reads YOLO_MODEL_PATH env var (default: ../ai_model/road_damage_yolov8.pt)
  - If the .pt file is missing the service falls back to a deterministic mock
    that returns consistent results per-image (seeded by file content hash).

Class mapping:
  The RDD2022 label set uses D00/D10/D20/D40 codes.  We normalise to:
    D00, D10 → crack
    D20      → surface_damage
    D40      → pothole
  If ≥ 2 distinct normalised classes are detected → "multiple".
"""

import hashlib
import logging
import os
import random
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────
MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "../ai_model/road_damage_yolov8.pt")

MIN_FILE_BYTES = 1_000          # reject obviously empty / corrupt uploads
MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 MB hard cap

ROAD_VALID_CLASSES = {"pothole", "crack", "surface_damage", "multiple"}

# Raw YOLO class-name → normalised RoadWatch name
_CLASS_MAP = {
    # RDD2022 code names
    "D00":              "crack",
    "D10":              "crack",
    "D20":              "surface_damage",
    "D40":              "pothole",
    # Human-readable names (if the model was trained with these)
    "pothole":          "pothole",
    "crack":            "crack",
    "surface_damage":   "surface_damage",
    "multiple":         "multiple",
    "multiple_damage":  "multiple",
}

# ── LRU analysis cache (avoids re-processing the same image) ──────────
_CACHE_SIZE = 128
_analysis_cache: OrderedDict = OrderedDict()

# ── Lazy model singleton ──────────────────────────────────────────────
_model = None
_model_tried = False


def _load():
    """Lazy-load the YOLO model exactly once."""
    global _model, _model_tried
    if _model_tried:
        return _model
    _model_tried = True

    resolved = Path(MODEL_PATH)
    if not resolved.exists():
        logger.warning("[AI] Model not found at %s — using mock mode", MODEL_PATH)
        return None
    try:
        from ultralytics import YOLO
        _model = YOLO(str(resolved))
        logger.info("[AI] YOLOv8 loaded from %s", resolved)
    except Exception as exc:
        logger.error("[AI] Failed to load model: %s — using mock mode", exc)
    return _model


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PUBLIC API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def image_hash(data: bytes) -> str:
    """MD5 hex digest of raw image bytes — used for duplicate detection."""
    return hashlib.md5(data).hexdigest()


def is_road_image(image_path: str) -> Tuple[bool, float]:
    """
    Lightweight gate: is this upload a plausible road-damage photo?

    Returns ``(is_road, confidence)``.

    * **Model loaded** — runs a quick inference pass.  Accepts the image if
      ANY detection has confidence > 0.30.
    * **Mock mode** — validates JPEG / PNG / WebP magic bytes and accepts
      with a fixed confidence of 0.80.
    """
    # ── Size sanity check ──
    try:
        size = os.path.getsize(image_path)
    except OSError:
        return False, 0.0
    if size < MIN_FILE_BYTES or size > MAX_FILE_BYTES:
        return False, 0.0

    # ── Magic-byte check ──
    try:
        with open(image_path, "rb") as fh:
            header = fh.read(12)
    except OSError:
        return False, 0.0

    jpeg = header[:3] == b"\xff\xd8\xff"
    png  = header[:8] == b"\x89PNG\r\n\x1a\n"
    webp = header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    if not (jpeg or png or webp):
        return False, 0.0

    # ── Model inference (if available) ──
    model = _load()
    if model is not None:
        try:
            results = model(image_path, conf=0.10, verbose=False)
            if results and results[0].boxes is not None and len(results[0].boxes) > 0:
                max_conf = float(results[0].boxes.conf.max())
                if max_conf > 0.30:
                    return True, round(max_conf, 3)
                return False, round(max_conf, 3)
            return False, 0.0
        except Exception as exc:
            logger.warning("[AI] is_road_image inference error: %s — accepting with fallback", exc)
            return True, 0.50

    # ── Mock mode: accept any valid image format ──
    return True, 0.80


def analyze_image(image_path: str) -> Dict[str, object]:
    """
    Analyse a road-damage image and return a classification dict.

    Return shape (guaranteed)::

        {
            "damage_type":   "pothole" | "crack" | "surface_damage" | "multiple",
            "severity":      "high" | "medium" | "low",
            "ai_confidence": float,       # 0.0 – 1.0
            "description":   str,
        }

    Results are LRU-cached keyed on a partial file-content hash.
    """
    # ── Cache lookup ──
    try:
        with open(image_path, "rb") as f:
            file_hash = hashlib.md5(f.read(8192)).hexdigest()
    except OSError:
        file_hash = image_path

    if file_hash in _analysis_cache:
        _analysis_cache.move_to_end(file_hash)
        return _analysis_cache[file_hash]

    # ── Run inference ──
    model = _load()
    if model is not None:
        try:
            result = _yolo_analyze(model, image_path)
        except Exception as exc:
            logger.warning("[AI] Inference error: %s — falling back to mock", exc)
            result = _mock(image_path)
    else:
        result = _mock(image_path)

    # ── Store in cache ──
    _analysis_cache[file_hash] = result
    if len(_analysis_cache) > _CACHE_SIZE:
        _analysis_cache.popitem(last=False)

    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  INTERNAL — real YOLO inference
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _severity(conf: float) -> str:
    """Map a confidence value to a severity label."""
    if conf >= 0.80:
        return "high"
    if conf >= 0.55:
        return "medium"
    return "low"


def _normalise_class(raw_name: str) -> str:
    """Map any raw YOLO class name to one of the 4 canonical damage types."""
    return _CLASS_MAP.get(raw_name, "pothole")


def _build_description(damage_type: str, sev: str, conf: float) -> str:
    """Generate a human-readable description string."""
    return (
        f"{sev.title()} severity {damage_type.replace('_', ' ')} "
        f"detected with {conf:.0%} confidence."
    )


def _yolo_analyze(model, path: str) -> Dict[str, object]:
    """
    Run full YOLOv8 inference and return the standardised result dict.

    Logic:
      1. Run inference at conf=0.01 to capture everything.
      2. Collect the normalised class name for every detection.
      3. If ≥ 2 *distinct* normalised classes → ``damage_type = "multiple"``.
      4. Otherwise use the class of the highest-confidence detection.
      5. ``ai_confidence`` = max detection confidence across all boxes.
    """
    results = model(path, conf=0.01, verbose=False)

    # No detections at all
    if not results or results[0].boxes is None or len(results[0].boxes) == 0:
        return {
            "damage_type":   "surface_damage",
            "severity":      "low",
            "ai_confidence": 0.0,
            "description":   "No significant road damage detected in the image.",
        }

    boxes = results[0].boxes

    # Gather per-box class names and confidences
    detected_classes: Set[str] = set()
    best_conf = 0.0
    best_class_raw = ""

    for i in range(len(boxes)):
        cls_id   = int(boxes.cls[i])
        conf_val = float(boxes.conf[i])
        raw_name = model.names.get(cls_id, f"class_{cls_id}")
        norm     = _normalise_class(raw_name)
        detected_classes.add(norm)

        if conf_val > best_conf:
            best_conf = conf_val
            best_class_raw = raw_name

    # Decide damage_type
    if len(detected_classes) >= 2:
        damage_type = "multiple"
    else:
        damage_type = _normalise_class(best_class_raw)

    conf = round(best_conf, 4)
    sev  = _severity(conf)

    return {
        "damage_type":   damage_type,
        "severity":      sev,
        "ai_confidence": conf,
        "description":   _build_description(damage_type, sev, conf),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  INTERNAL — deterministic mock (no model file)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _mock(path: str) -> Dict[str, object]:
    """
    Deterministic mock — same file always produces the same classification.
    Uses an MD5-seeded RNG so results are reproducible across runs.
    """
    seed = 42
    try:
        with open(path, "rb") as f:
            seed = int(hashlib.md5(f.read(2048)).hexdigest()[:8], 16)
    except Exception:
        pass

    rng = random.Random(seed)
    damages = ["pothole", "crack", "surface_damage", "multiple"]
    damage  = rng.choices(damages, weights=[0.45, 0.30, 0.15, 0.10])[0]
    conf    = round(rng.uniform(0.30, 0.95), 4)
    sev     = _severity(conf)

    return {
        "damage_type":   damage,
        "severity":      sev,
        "ai_confidence": conf,
        "description":   f"[MOCK] {_build_description(damage, sev, conf)}",
    }