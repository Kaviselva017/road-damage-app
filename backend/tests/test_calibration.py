"""
backend/tests/test_calibration.py
===================================
pytest tests for calibration_service.py and ensemble_service.py:

  test_temperature_scaling  — calibrated confidence < raw for overconfident preds
  test_ensemble_fallback    — missing secondary model → single-model used
"""

from __future__ import annotations

import importlib
import json
import sys
from unittest.mock import patch

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fresh(module_name: str):
    """Force a clean import (clears cached module)."""
    if module_name in sys.modules:
        del sys.modules[module_name]
    return importlib.import_module(module_name)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Temperature scaling
# ─────────────────────────────────────────────────────────────────────────────

def test_temperature_scaling():
    """
    For T > 1 (default 1.3):
      - Overconfident raw predictions (> 0.5) must be REDUCED after calibration.
      - Low-confidence predictions (< 0.5) must be INCREASED.
      - A raw confidence of exactly 0.5 must remain 0.5 (symmetric point).
    """
    cal_mod = _fresh("app.services.calibration_service")
    CalibrationService = cal_mod.CalibrationService

    cal = CalibrationService(temp=1.3)

    # --- overconfident predictions must be pulled down ---
    for raw in [0.95, 0.90, 0.85, 0.80, 0.70, 0.60, 0.55]:
        calibrated = cal.calibrate(raw)
        assert calibrated < raw, (
            f"Expected calibrate({raw}) < {raw} with T=1.3, got {calibrated}"
        )

    # --- low-confidence predictions must be pushed up ---
    for raw in [0.10, 0.20, 0.30, 0.40, 0.45]:
        calibrated = cal.calibrate(raw)
        assert calibrated > raw, (
            f"Expected calibrate({raw}) > {raw} with T=1.3, got {calibrated}"
        )

    # --- the symmetry point stays at 0.5 ---
    mid = cal.calibrate(0.5)
    assert abs(mid - 0.5) < 1e-4, f"calibrate(0.5) should be ~0.5, got {mid}"

    # --- T=1.0 must be identity ---
    cal_id = CalibrationService(temp=1.0)
    for raw in [0.3, 0.5, 0.7, 0.9]:
        assert abs(cal_id.calibrate(raw) - raw) < 1e-4, \
            f"T=1.0 should be identity for raw={raw}"

    # --- temperature range validation ---
    with pytest.raises(ValueError):
        CalibrationService(temp=0.1)   # below 0.5
    with pytest.raises(ValueError):
        CalibrationService(temp=5.0)   # above 3.0


def test_temperature_load_from_json(tmp_path):
    """load_temperature correctly reads a valid JSON file."""
    cal_mod = _fresh("app.services.calibration_service")
    CalibrationService = cal_mod.CalibrationService

    cal_file = tmp_path / "calibration.json"
    cal_file.write_text(json.dumps({"temperature": 1.8}), encoding="utf-8")

    cal = CalibrationService()
    cal.load_temperature(str(cal_file))
    assert abs(cal.temperature - 1.8) < 1e-6


def test_temperature_missing_file(caplog):
    """load_temperature with missing path logs WARNING and keeps default."""
    import logging  # noqa: PLC0415

    cal_mod = _fresh("app.services.calibration_service")
    CalibrationService = cal_mod.CalibrationService

    cal = CalibrationService(temp=1.3)
    with caplog.at_level(logging.WARNING):
        cal.load_temperature("/nonexistent/path/calibration.json")

    assert cal.temperature == 1.3
    assert any("not found" in r.message.lower() for r in caplog.records)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Ensemble fallback — missing secondary → single model used
# ─────────────────────────────────────────────────────────────────────────────

def test_ensemble_fallback(monkeypatch, tmp_path):
    """
    When YOLO_MODEL2_PATH is not set (or points to a missing file), EnsembleService
    must fall back to single-model mode (primary only) without raising.
    """
    # Ensure secondary is NOT configured
    monkeypatch.delenv("YOLO_MODEL2_PATH", raising=False)
    monkeypatch.setenv("ENABLE_ENSEMBLE", "false")

    # --- clear cached modules so globals reset ---
    for mod in list(sys.modules.keys()):
        if "ai_service" in mod or "ensemble_service" in mod or "calibration_service" in mod:
            del sys.modules[mod]

    # --- mock primary analyze_image to return a known DamageResult ---
    from app.services.ai_service import DamageResult  # noqa: PLC0415

    expected = [
        DamageResult(
            class_name="pothole",
            confidence=0.75,
            bbox=[10, 10, 100, 100],
            severity="high",
        )
    ]

    import app.services.ensemble_service as ens_mod  # noqa: PLC0415

    # Reset the singleton + secondary-loaded flag
    ens_mod._ensemble_service = None
    ens_mod._secondary_loaded = False
    ens_mod._secondary_model  = None

    with patch("app.services.ensemble_service.analyze_image", return_value=expected):
        svc = ens_mod.EnsembleService()
        # Force secondary check
        svc._has_secondary = False

        import numpy as np  # noqa: PLC0415
        import cv2          # noqa: PLC0415

        # Build a tiny valid JPEG
        img = np.zeros((64, 64, 3), dtype=np.uint8)
        _, buf = cv2.imencode(".jpg", img)
        image_bytes = buf.tobytes()

        with patch("app.services.ensemble_service._bytes_to_bgr",
                   return_value=np.zeros((64, 64, 3), dtype=np.uint8)), \
             patch("app.services.ensemble_service._apply_clahe",
                   side_effect=lambda x: x), \
             patch("app.services.ensemble_service.analyze_image",
                   return_value=expected):
            results = svc.predict(image_bytes)

    assert isinstance(results, list), "predict() must return a list"
    assert len(results) == 1, "Single-model fallback should return exactly 1 result"
    assert results[0].class_name == "pothole"
    assert results[0].confidence == pytest.approx(0.75, abs=1e-4)
