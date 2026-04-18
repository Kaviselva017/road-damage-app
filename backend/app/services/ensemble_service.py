"""
backend/app/services/ensemble_service.py
==========================================
Weighted Box Fusion (WBF) ensemble for the RoadWatch detection pipeline.

  pip install ensemble-boxes==1.0.9

Two-model setup:
  primary   weight 0.6  ← YOLO_MODEL_PATH
  secondary weight 0.4  ← YOLO_MODEL2_PATH  (optional)

If the secondary model file is absent the service transparently falls back to
the primary model result without raising.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

import numpy as np

from app.services.ai_service import (
    CLASS_NAMES,
    DamageResult,
    _apply_clahe,
    _bytes_to_bgr,
    _load_model,
    _map_severity,
    _model,
    _model_type,
    _run_mock,
    analyze_image,
)

logger = logging.getLogger(__name__)

# ── WBF constants ─────────────────────────────────────────────────────────────
PRIMARY_WEIGHT   = 0.6
SECONDARY_WEIGHT = 0.4
IOU_THR          = 0.55
SKIP_BOX_THR     = 0.25
CONF_TYPE        = "avg"   # "avg" or "max"


def _det_to_wbf(dets: list[DamageResult], img_w: int, img_h: int) -> tuple[list, list, list]:
    """Convert DamageResult list → WBF boxes/scores/labels (normalised coords)."""
    boxes, scores, labels = [], [], []
    for d in dets:
        x1, y1, x2, y2 = d.bbox
        boxes.append([
            max(0.0, x1 / img_w),
            max(0.0, y1 / img_h),
            min(1.0, x2 / img_w),
            min(1.0, y2 / img_h),
        ])
        scores.append(d.confidence)
        labels.append(d.raw_class_id if d.raw_class_id >= 0 else 0)
    return boxes, scores, labels


def _wbf_to_dets(
    boxes: np.ndarray,
    scores: np.ndarray,
    labels: np.ndarray,
    img_w: int,
    img_h: int,
) -> list[DamageResult]:
    results = []
    for box, conf, cls_id in zip(boxes, scores, labels):
        x1 = int(box[0] * img_w)
        y1 = int(box[1] * img_h)
        x2 = int(box[2] * img_w)
        y2 = int(box[3] * img_h)
        cls_id = int(cls_id)
        results.append(
            DamageResult(
                class_name=CLASS_NAMES.get(cls_id, "unknown"),
                confidence=round(float(conf), 4),
                bbox=[x1, y1, x2, y2],
                severity=_map_severity(float(conf)),
                raw_class_id=cls_id,
            )
        )
    return sorted(results, key=lambda r: r.confidence, reverse=True)


# ── Secondary model loader ────────────────────────────────────────────────────
_secondary_model = None
_secondary_type  = None
_secondary_input = None
_secondary_loaded = False   # Guard against repeated failed load attempts


def _load_secondary() -> bool:
    """Try to load the secondary model. Returns True if successful."""
    global _secondary_model, _secondary_type, _secondary_input, _secondary_loaded

    if _secondary_loaded:
        return _secondary_model is not None

    _secondary_loaded = True
    path = os.getenv("YOLO_MODEL2_PATH", "")

    if not path or not os.path.exists(path):
        logger.info(
            "EnsembleService: secondary model not configured or not found at '%s' — "
            "using single-model mode.",
            path or "<YOLO_MODEL2_PATH not set>",
        )
        return False

    if path.endswith(".onnx"):
        try:
            import onnxruntime as ort  # noqa: PLC0415

            opts = ort.SessionOptions()
            opts.log_severity_level = 3
            _secondary_model = ort.InferenceSession(
                path, sess_options=opts,
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
            )
            _secondary_input = _secondary_model.get_inputs()[0].name
            _secondary_type  = "onnx"
            logger.info("EnsembleService: secondary ONNX model loaded from %s", path)
            return True
        except Exception as exc:
            logger.warning("EnsembleService: secondary ONNX load failed: %s", exc)
            return False
    else:
        try:
            from ultralytics import YOLO  # noqa: PLC0415

            _secondary_model = YOLO(path)
            _secondary_type  = "yolo"
            logger.info("EnsembleService: secondary YOLO model loaded from %s", path)
            return True
        except Exception as exc:
            logger.warning("EnsembleService: secondary YOLO load failed: %s", exc)
            return False


def _infer_secondary(bgr) -> list[DamageResult]:
    """Run inference with the secondary model."""
    import cv2  # noqa: PLC0415

    if _secondary_type == "onnx":
        from app.services.ai_service import _run_onnx_tta as _onnx_tta  # noqa: PLC0415
        # Temporarily swap the global model pointer
        import app.services.ai_service as _svc  # noqa: PLC0415
        prev_model = _svc._model
        prev_input = _svc._input_name
        _svc._model      = _secondary_model
        _svc._input_name = _secondary_input
        try:
            return _onnx_tta(bgr)
        finally:
            _svc._model      = prev_model
            _svc._input_name = prev_input

    elif _secondary_type == "yolo":
        from app.services.ai_service import _run_yolo  # noqa: PLC0415
        import app.services.ai_service as _svc  # noqa: PLC0415
        prev_model = _svc._model
        _svc._model = _secondary_model
        try:
            return _run_yolo(bgr)
        finally:
            _svc._model = prev_model

    return []


# ── EnsembleService ───────────────────────────────────────────────────────────

class EnsembleService:
    """
    Combines predictions from primary (weight=0.6) and optional secondary
    (weight=0.4) model using Weighted Box Fusion.

    Falls back silently to single-model mode when the secondary model is absent.
    """

    def __init__(self) -> None:
        self._has_secondary: bool | None = None  # Lazily resolved

    def _ensure_loaded(self):
        if self._has_secondary is None:
            # Ensure primary is loaded
            _load_model()
            self._has_secondary = _load_secondary()

    def predict(self, image_bytes: bytes) -> list[DamageResult]:
        """
        Run ensemble prediction on raw image bytes.
        Returns list of DamageResult sorted by confidence desc.
        """
        import cv2  # noqa: PLC0415

        self._ensure_loaded()

        try:
            bgr = _bytes_to_bgr(image_bytes)
            bgr = _apply_clahe(bgr)
            img_h, img_w = bgr.shape[:2]
        except Exception as exc:
            logger.error("EnsembleService: image decode failed: %s", exc)
            return _run_mock(np.zeros((100, 100, 3), dtype=np.uint8))

        # ── Primary inference ─────────────────────────────────────────────────
        primary_dets: list[DamageResult] = analyze_image(image_bytes)

        if not self._has_secondary:
            return primary_dets          # Single-model fallback

        # ── Secondary inference ───────────────────────────────────────────────
        try:
            secondary_dets = _infer_secondary(bgr)
        except Exception as exc:
            logger.warning("EnsembleService: secondary inference failed: %s", exc)
            return primary_dets

        if not primary_dets and not secondary_dets:
            return _run_mock(bgr)

        # ── WBF ───────────────────────────────────────────────────────────────
        try:
            from ensemble_boxes import weighted_boxes_fusion  # noqa: PLC0415

            p_boxes, p_scores, p_labels = _det_to_wbf(primary_dets,   img_w, img_h)
            s_boxes, s_scores, s_labels = _det_to_wbf(secondary_dets, img_w, img_h)

            all_boxes  = [p_boxes,  s_boxes]
            all_scores = [p_scores, s_scores]
            all_labels = [p_labels, s_labels]
            weights    = [PRIMARY_WEIGHT, SECONDARY_WEIGHT]

            fused_boxes, fused_scores, fused_labels = weighted_boxes_fusion(
                all_boxes, all_scores, all_labels,
                weights=weights,
                iou_thr=IOU_THR,
                skip_box_thr=SKIP_BOX_THR,
                conf_type=CONF_TYPE,
            )

            return _wbf_to_dets(fused_boxes, fused_scores, fused_labels, img_w, img_h)

        except ImportError:
            logger.warning(
                "ensemble-boxes not installed — falling back to primary model. "
                "Run: pip install ensemble-boxes==1.0.9"
            )
            return primary_dets
        except Exception as exc:
            logger.warning("EnsembleService: WBF failed: %s — using primary only.", exc)
            return primary_dets


# ── Module-level singleton ─────────────────────────────────────────────────────

_ensemble_service: EnsembleService | None = None


def get_ensemble_service() -> EnsembleService:
    global _ensemble_service
    if _ensemble_service is None:
        _ensemble_service = EnsembleService()
    return _ensemble_service
