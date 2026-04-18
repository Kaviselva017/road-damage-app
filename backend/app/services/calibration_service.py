"""
backend/app/services/calibration_service.py
=============================================
Temperature scaling is a post-hoc calibration technique that divides the
model's logit by a scalar temperature T before applying softmax.

  calibrated_conf = sigmoid(logit(raw_conf) / T)

For T > 1 the calibrated confidence is *lower* than the raw confidence,
correcting the over-confidence that is typical of modern deep neural networks.
Valid temperature range: [0.5, 3.0].  Default: 1.3
"""

from __future__ import annotations

import json
import logging
import math
import os

logger = logging.getLogger(__name__)

_DEFAULT_TEMPERATURE = 1.3
_MIN_TEMPERATURE = 0.5
_MAX_TEMPERATURE = 3.0

# Tiny epsilon to guard against log(0) / log(1) numerical issues
_EPS = 1e-7


def _logit(p: float) -> float:
    """Inverse sigmoid: logit(p) = log(p / (1 - p))."""
    p = max(_EPS, min(1.0 - _EPS, p))
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    """σ(x) = 1 / (1 + e^{-x})."""
    return 1.0 / (1.0 + math.exp(-x))


class CalibrationService:
    """
    Post-hoc confidence calibration via temperature scaling.

    Usage::

        cal = CalibrationService(temp=1.3)
        calibrated = cal.calibrate(raw_conf=0.92)   # → ~0.81
    """

    def __init__(self, temp: float = _DEFAULT_TEMPERATURE) -> None:
        self._temperature: float = _DEFAULT_TEMPERATURE
        self.set_temperature(temp)

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def temperature(self) -> float:
        return self._temperature

    # ── Mutation ──────────────────────────────────────────────────────────────

    def set_temperature(self, temp: float) -> None:
        if not (_MIN_TEMPERATURE <= temp <= _MAX_TEMPERATURE):
            raise ValueError(
                f"Temperature must be in [{_MIN_TEMPERATURE}, {_MAX_TEMPERATURE}], got {temp}"
            )
        self._temperature = float(temp)

    # ── Core calibration ──────────────────────────────────────────────────────

    def calibrate(self, raw_conf: float) -> float:
        """
        Apply temperature scaling and return calibrated confidence in [0, 1].

        calibrated = σ(logit(raw_conf) / T)
        """
        logit_val = _logit(raw_conf)
        scaled    = logit_val / self._temperature
        return round(_sigmoid(scaled), 6)

    # ── Persistence ───────────────────────────────────────────────────────────

    def load_temperature(self, path: str) -> None:
        """
        Load temperature from a JSON file.  Expected format::

            {"temperature": 1.25}

        If the file is missing or malformed, logs a WARNING and keeps the
        current (default) temperature.
        """
        if not os.path.exists(path):
            logger.warning(
                "Calibration file not found: '%s' — using default temperature %.2f",
                path,
                self._temperature,
            )
            return

        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)

            temp = float(data["temperature"])

            if not (_MIN_TEMPERATURE <= temp <= _MAX_TEMPERATURE):
                logger.warning(
                    "Temperature %.2f in '%s' is outside [%.1f, %.1f] — using default %.2f",
                    temp, path, _MIN_TEMPERATURE, _MAX_TEMPERATURE, self._temperature,
                )
                return

            self._temperature = temp
            logger.info("Calibration temperature set to %.4f from '%s'", temp, path)

        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            logger.warning(
                "Failed to parse calibration file '%s': %s — using default temperature %.2f",
                path, exc, self._temperature,
            )


# ── Module-level singleton ────────────────────────────────────────────────────

_calibration_service: CalibrationService | None = None


def get_calibration_service() -> CalibrationService:
    """Return (or lazily create) the module-level CalibrationService."""
    global _calibration_service
    if _calibration_service is None:
        cal_path = os.getenv("CALIBRATION_PATH", "ai_model/calibration.json")
        _calibration_service = CalibrationService()
        _calibration_service.load_temperature(cal_path)
    return _calibration_service
