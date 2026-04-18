"""
backend/tests/test_ai_service.py
==================================
pytest tests for ai_service.py:
  - test_severity_mapping: all 4 bands
  - test_clahe_applied: output differs from input
  - test_onnx_fallback: mock onnxruntime, assert DamageResult returned
"""

from __future__ import annotations

import importlib
import io
import os
import sys
import types
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_jpeg_bytes(width: int = 64, height: int = 64) -> bytes:
    """Create a minimal valid JPEG from a random numpy array using cv2."""
    import cv2  # noqa: PLC0415

    img = np.random.randint(50, 200, (height, width, 3), dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok, "cv2.imencode failed in test helper"
    return buf.tobytes()


def _fresh_ai_service():
    """Force a clean import of ai_service (reset module-level globals)."""
    if "app.services.ai_service" in sys.modules:
        del sys.modules["app.services.ai_service"]
    return importlib.import_module("app.services.ai_service")


# ─────────────────────────────────────────────────────────────────────────────
# 1. Severity mapping — all 4 bands
# ─────────────────────────────────────────────────────────────────────────────

def test_severity_mapping():
    """_map_severity must return the correct label for all 4 confidence bands."""
    svc = _fresh_ai_service()

    assert svc._map_severity(0.85) == "critical"
    assert svc._map_severity(0.80) == "critical"   # boundary: >= 0.80
    assert svc._map_severity(0.79) == "high"
    assert svc._map_severity(0.60) == "high"       # boundary: >= 0.60
    assert svc._map_severity(0.59) == "medium"
    assert svc._map_severity(0.40) == "medium"     # boundary: >= 0.40
    assert svc._map_severity(0.39) == "low"
    assert svc._map_severity(0.00) == "low"


# ─────────────────────────────────────────────────────────────────────────────
# 2. CLAHE applied — output differs from input
# ─────────────────────────────────────────────────────────────────────────────

def test_clahe_applied():
    """_apply_clahe must return an array that is not identical to the input."""
    import cv2  # noqa: PLC0415

    svc = _fresh_ai_service()

    # Create a flat, dull image (very low contrast) — CLAHE should change it
    bgr = np.full((64, 64, 3), 128, dtype=np.uint8)
    result = svc._apply_clahe(bgr)

    assert result.shape == bgr.shape, "Shape must be preserved"
    assert result.dtype == bgr.dtype, "Dtype must be preserved"
    # CLAHE on a perfectly flat image may produce the same values,
    # but on real images it will differ. We test a gradient image:
    gradient = np.zeros((64, 64, 3), dtype=np.uint8)
    gradient[:, :, 0] = np.tile(np.arange(64, dtype=np.uint8), (64, 1))
    out = svc._apply_clahe(gradient)
    assert not np.array_equal(gradient, out), \
        "CLAHE output must differ from a gradient input image"


# ─────────────────────────────────────────────────────────────────────────────
# 3. ONNX fallback — mock onnxruntime, assert DamageResult returned
# ─────────────────────────────────────────────────────────────────────────────

def test_onnx_fallback(tmp_path, monkeypatch):
    """When YOLO_MODEL_PATH points to a .onnx file, use onnxruntime and return DamageResult."""
    svc = _fresh_ai_service()

    # --- create a dummy .onnx file so the path-exists check passes ---
    onnx_file = tmp_path / "best.onnx"
    onnx_file.write_bytes(b"dummy")

    monkeypatch.setenv("YOLO_MODEL_PATH", str(onnx_file))

    # --- build a minimal onnxruntime mock ---
    # Output mimics YOLOv8 ONNX shape: (1, 84, 8400)
    # One strong detection: class 3 (pothole) at confidence 0.85
    output_data = np.zeros((1, 8 + 4, 8400), dtype=np.float32)  # 4+4 classes simplified
    # We'll patch with full 84 channels (4 box + 80 classes) but only use first 4 classes
    output_data = np.zeros((1, 84, 8400), dtype=np.float32)
    # Set one anchor: cx=320, cy=320, w=100, h=100, class-3 conf=0.9
    output_data[0, 0, 0] = 320.0   # cx
    output_data[0, 1, 0] = 320.0   # cy
    output_data[0, 2, 0] = 100.0   # w
    output_data[0, 3, 0] = 100.0   # h
    output_data[0, 4 + 3, 0] = 0.9  # class_id=3, conf=0.90

    mock_input = MagicMock()
    mock_input.name = "images"

    mock_session = MagicMock()
    mock_session.get_inputs.return_value = [mock_input]
    mock_session.run.return_value = [output_data]

    mock_ort = types.ModuleType("onnxruntime")
    mock_ort.SessionOptions = MagicMock(return_value=MagicMock())
    mock_ort.InferenceSession = MagicMock(return_value=mock_session)

    # Reset module globals so _load_model() runs fresh
    svc._model = None
    svc._model_type = None
    svc._input_name = None

    with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
        jpeg_bytes = _make_jpeg_bytes()
        results = svc.analyze_image(jpeg_bytes)

    assert isinstance(results, list), "analyze_image must return a list"
    assert len(results) >= 1, "At least one detection expected"
    top = results[0]
    assert isinstance(top, svc.DamageResult), "Result must be a DamageResult"
    assert top.class_name == "pothole", f"Expected pothole, got {top.class_name}"
    assert top.confidence >= 0.5, "Confidence must be >= 0.5"
    assert top.severity in {"critical", "high", "medium", "low"}
    assert len(top.bbox) == 4, "bbox must have 4 ints [x1,y1,x2,y2]"
