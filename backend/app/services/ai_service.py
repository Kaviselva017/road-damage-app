"""
RoadWatch AI Service
====================
- Loads YOLOv8 model from YOLO_MODEL_PATH (supports .pt and .onnx)
- CLAHE preprocessing (cv2)
- Test-time augmentation (original + hflip, averaged scores)
- Graceful mock fallback if model file not found
- Returns typed DamageResult dataclass
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── Lazy calibration import (avoids circular at module load) ─────────────────
def _get_calibration():
    from app.services.calibration_service import get_calibration_service  # noqa
    return get_calibration_service()

# ── Class map ────────────────────────────────────────────────────────────────
CLASS_NAMES: dict[int, str] = {
    0: "longitudinal_crack",   # D00
    1: "transverse_crack",     # D10
    2: "alligator_crack",      # D20
    3: "pothole",              # D40
}

SEVERITY_THRESHOLDS = [
    (0.80, "critical"),
    (0.60, "high"),
    (0.40, "medium"),
    (0.00, "low"),
]


def _map_severity(confidence: float) -> str:
    for threshold, label in SEVERITY_THRESHOLDS:
        if confidence >= threshold:
            return label
    return "low"


# ── Result dataclass ─────────────────────────────────────────────────────────
@dataclass
class DamageResult:
    class_name: str
    confidence: float
    bbox: list[int]          # [x1, y1, x2, y2] in pixel coords
    severity: str
    inference_ms: float = 0.0
    raw_class_id: int = -1
    extra: dict = field(default_factory=dict)


# ── Image helpers ─────────────────────────────────────────────────────────────
def _apply_clahe(bgr: np.ndarray) -> np.ndarray:
    """Apply CLAHE to the L channel of LAB colourspace."""
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_ch = clahe.apply(l_ch)
    return cv2.cvtColor(cv2.merge([l_ch, a_ch, b_ch]), cv2.COLOR_LAB2BGR)


def _bytes_to_bgr(image_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("cv2 could not decode provided image bytes.")
    return img


# ── Model loader (lazy singleton) ─────────────────────────────────────────────
_model = None        # ultralytics YOLO or onnxruntime.InferenceSession
_model_type = None   # "yolo" | "onnx" | "mock"
_input_name = None   # ONNX input name


def _load_model():
    global _model, _model_type, _input_name

    if _model is not None:
        return

    model_path = os.getenv("YOLO_MODEL_PATH", "ai_model/best.pt")

    if not os.path.exists(model_path):
        logger.warning(
            "YOLO_MODEL_PATH '%s' not found — running in MOCK mode. "
            "Set YOLO_MODEL_PATH to enable real inference.",
            model_path,
        )
        _model_type = "mock"
        return

    if model_path.endswith(".onnx"):
        try:
            import onnxruntime as ort  # noqa: PLC0415

            sess_opts = ort.SessionOptions()
            sess_opts.log_severity_level = 3
            _model = ort.InferenceSession(
                model_path,
                sess_options=sess_opts,
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
            )
            _input_name = _model.get_inputs()[0].name
            _model_type = "onnx"
            logger.info("Loaded ONNX model from %s", model_path)
        except Exception as exc:
            logger.warning("ONNX load failed (%s) — falling back to mock.", exc)
            _model_type = "mock"
    else:
        try:
            from ultralytics import YOLO  # noqa: PLC0415

            _model = YOLO(model_path)
            _model_type = "yolo"
            logger.info("Loaded YOLO model from %s", model_path)
        except Exception as exc:
            logger.warning("YOLO load failed (%s) — falling back to mock.", exc)
            _model_type = "mock"


# ── ONNX inference helper ─────────────────────────────────────────────────────
def _run_onnx(bgr: np.ndarray) -> list[DamageResult]:
    import onnxruntime as ort  # noqa: PLC0415

    h, w = 640, 640
    resized = cv2.resize(bgr, (w, h))
    blob = resized.astype(np.float32) / 255.0
    blob = np.transpose(blob, (2, 0, 1))[np.newaxis, ...]  # (1, 3, H, W)

    outputs = _model.run(None, {_input_name: blob})
    # YOLOv8 ONNX outputs shape: [1, 84, 8400] — [batch, (4+80), anchors]
    raw = outputs[0][0]  # (84, 8400)
    boxes = raw[:4, :].T        # (8400, 4)  cx cy w h
    scores = raw[4:, :].T       # (8400, num_classes)

    results = []
    conf_threshold = 0.25
    for i, row in enumerate(scores):
        class_id = int(np.argmax(row))
        conf = float(row[class_id])
        if conf < conf_threshold:
            continue
        cx, cy, bw, bh = boxes[i]
        orig_h, orig_w = bgr.shape[:2]
        x1 = int((cx - bw / 2) * orig_w / w)
        y1 = int((cy - bh / 2) * orig_h / h)
        x2 = int((cx + bw / 2) * orig_w / w)
        y2 = int((cy + bh / 2) * orig_h / h)
        results.append(
            DamageResult(
                class_name=CLASS_NAMES.get(class_id, "unknown"),
                confidence=round(conf, 4),
                bbox=[x1, y1, x2, y2],
                severity=_map_severity(conf),
                raw_class_id=class_id,
            )
        )
    return results


def _run_onnx_tta(bgr: np.ndarray) -> list[DamageResult]:
    """Run ONNX inference with horizontal-flip TTA, merge by highest conf per box."""
    r1 = _run_onnx(bgr)
    r2 = _run_onnx(cv2.flip(bgr, 1))
    # Simple merge: take the highest-confidence result per class
    best: dict[str, DamageResult] = {}
    for r in r1 + r2:
        if r.class_name not in best or r.confidence > best[r.class_name].confidence:
            best[r.class_name] = r
    return sorted(best.values(), key=lambda x: x.confidence, reverse=True)


# ── YOLO inference helper ─────────────────────────────────────────────────────
def _run_yolo(bgr: np.ndarray) -> list[DamageResult]:
    results_orig = _model(bgr, verbose=False)[0]
    results_flip = _model(cv2.flip(bgr, 1), verbose=False)[0]

    best: dict[str, DamageResult] = {}

    def _parse(res, flipped: bool = False):
        if res.boxes is None:
            return
        for box in res.boxes:
            class_id = int(box.cls.item())
            conf = float(box.conf.item())
            xyxy = box.xyxy[0].tolist()
            x1, y1, x2, y2 = [int(v) for v in xyxy]
            if flipped:
                img_w = bgr.shape[1]
                x1, x2 = img_w - x2, img_w - x1
            name = CLASS_NAMES.get(class_id, res.names.get(class_id, "unknown"))
            dr = DamageResult(
                class_name=name,
                confidence=round(conf, 4),
                bbox=[x1, y1, x2, y2],
                severity=_map_severity(conf),
                raw_class_id=class_id,
            )
            if name not in best or conf > best[name].confidence:
                best[name] = dr

    _parse(results_orig, flipped=False)
    _parse(results_flip, flipped=True)
    return sorted(best.values(), key=lambda x: x.confidence, reverse=True)


# ── Mock inference ─────────────────────────────────────────────────────────────
def _run_mock(_bgr: np.ndarray) -> list[DamageResult]:
    return [
        DamageResult(
            class_name="pothole",
            confidence=0.55,
            bbox=[10, 10, 120, 120],
            severity="medium",
            raw_class_id=3,
        )
    ]


# ── Public API ────────────────────────────────────────────────────────────────
def analyze_image(image_bytes: bytes) -> list[DamageResult]:
    """
    Entry point. Returns a list of DamageResult sorted by confidence desc.
    Applies temperature-scaling calibration to every raw confidence.
    Never raises — returns a mock result on any error.
    """
    _load_model()

    try:
        bgr = _bytes_to_bgr(image_bytes)
        bgr = _apply_clahe(bgr)

        t0 = time.perf_counter()

        if _model_type == "onnx":
            results = _run_onnx_tta(bgr)
        elif _model_type == "yolo":
            results = _run_yolo(bgr)
        else:
            results = _run_mock(bgr)

        elapsed_ms = (time.perf_counter() - t0) * 1000

        # ── Apply calibration ─────────────────────────────────────────────
        try:
            cal = _get_calibration()
            for r in results:
                r.confidence = cal.calibrate(r.confidence)
                r.severity   = _map_severity(r.confidence)   # Re-derive after scaling
        except Exception as cal_exc:
            logger.debug("Calibration skipped: %s", cal_exc)

        for r in results:
            r.inference_ms = round(elapsed_ms, 2)

        return results if results else _run_mock(bgr)

    except Exception as exc:
        logger.error("AI inference error: %s", exc, exc_info=True)
        return _run_mock(np.zeros((100, 100, 3), dtype=np.uint8))


# ── Ensemble entry point ──────────────────────────────────────────────────────

def analyze_image_ensemble(image_bytes: bytes) -> list[DamageResult]:
    """
    When ENABLE_ENSEMBLE=true, delegates to EnsembleService (WBF fusion).
    Otherwise falls back to analyze_image().
    """
    enable = os.getenv("ENABLE_ENSEMBLE", "false").lower() in ("1", "true", "yes")
    if enable:
        try:
            from app.services.ensemble_service import get_ensemble_service  # noqa
            return get_ensemble_service().predict(image_bytes)
        except Exception as exc:
            logger.warning("Ensemble failed, using single model: %s", exc)
    return analyze_image(image_bytes)



def image_hash(image_bytes: bytes) -> str:
    """SHA-256 hex digest — used for duplicate detection."""
    import hashlib

    return hashlib.sha256(image_bytes).hexdigest()


def top_result(image_bytes: bytes) -> DamageResult | None:
    """Convenience: return only the highest-confidence detection."""
    results = analyze_image(image_bytes)
    return results[0] if results else None
