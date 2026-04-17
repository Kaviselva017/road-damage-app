"""
Tests for app.services.ai_service
──────────────────────────────────
Covers:
  • _yolo_analyze   — real-model path with mocked YOLO objects
  • _mock           — deterministic mock fallback
  • _severity       — confidence → severity mapping
  • image_hash      — MD5 dedup helper
  • is_road_image   — file-gate logic (mock mode)
"""

import hashlib
import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from app.services.ai_service import (
    _yolo_analyze,
    _mock,
    _severity,
    image_hash,
    is_road_image,
    _normalise_class,
    _build_description,
)


# ── Helpers ────────────────────────────────────────────────────────────

class _FakeConf:
    """Mimics a tensor with .max() and index access."""
    def __init__(self, values):
        self._v = values
    def __getitem__(self, i):
        return self._v[i]
    def __len__(self):
        return len(self._v)
    def max(self):
        return max(self._v) if self._v else 0.0

class _FakeCls:
    def __init__(self, values):
        self._v = values
    def __getitem__(self, i):
        return self._v[i]
    def __len__(self):
        return len(self._v)

class _FakeBoxes:
    def __init__(self, cls_list, conf_list):
        self.cls  = _FakeCls(cls_list)
        self.conf = _FakeConf(conf_list)
    def __len__(self):
        return len(self.conf)

class _FakeResult:
    def __init__(self, cls_list, conf_list):
        if cls_list is None:
            self.boxes = None
        else:
            self.boxes = _FakeBoxes(cls_list, conf_list)

def _make_model(names_map, cls_list, conf_list):
    """Return a callable mock model that yields one FakeResult."""
    model = MagicMock()
    model.names = names_map
    model.return_value = [_FakeResult(cls_list, conf_list)]
    return model


# ── _severity ──────────────────────────────────────────────────────────

def test_severity_high():
    assert _severity(0.80) == "high"
    assert _severity(0.99) == "high"

def test_severity_medium():
    assert _severity(0.55) == "medium"
    assert _severity(0.79) == "medium"

def test_severity_low():
    assert _severity(0.54) == "low"
    assert _severity(0.10) == "low"


# ── _normalise_class ───────────────────────────────────────────────────

def test_normalise_rdd_codes():
    assert _normalise_class("D00") == "crack"
    assert _normalise_class("D10") == "crack"
    assert _normalise_class("D20") == "surface_damage"
    assert _normalise_class("D40") == "pothole"

def test_normalise_human_names():
    assert _normalise_class("pothole") == "pothole"
    assert _normalise_class("crack") == "crack"

def test_normalise_unknown_falls_back():
    assert _normalise_class("unknown_label") == "pothole"


# ── _build_description ────────────────────────────────────────────────

def test_description_format():
    desc = _build_description("surface_damage", "high", 0.91)
    assert "High severity surface damage" in desc
    assert "91%" in desc


# ── _yolo_analyze ──────────────────────────────────────────────────────

def test_yolo_single_class_pothole():
    model = _make_model({0: "D40"}, [0, 0], [0.85, 0.60])
    result = _yolo_analyze(model, "dummy.jpg")

    assert result["damage_type"] == "pothole"
    assert result["severity"] == "high"       # 0.85 >= 0.80
    assert result["ai_confidence"] == 0.85
    assert "pothole" in result["description"].lower()

def test_yolo_single_class_crack():
    model = _make_model({0: "D00"}, [0], [0.70])
    result = _yolo_analyze(model, "dummy.jpg")

    assert result["damage_type"] == "crack"
    assert result["severity"] == "medium"     # 0.55 <= 0.70 < 0.80
    assert result["ai_confidence"] == 0.70

def test_yolo_multiple_classes():
    """Two distinct normalised classes → damage_type = 'multiple'."""
    model = _make_model(
        {0: "D40", 1: "D00"},
        [0, 1, 0],
        [0.72, 0.65, 0.50],
    )
    result = _yolo_analyze(model, "dummy.jpg")

    assert result["damage_type"] == "multiple"
    assert result["ai_confidence"] == 0.72    # max across all boxes

def test_yolo_no_detections():
    model = _make_model({0: "D40"}, None, None)
    result = _yolo_analyze(model, "dummy.jpg")

    assert result["damage_type"] == "surface_damage"
    assert result["ai_confidence"] == 0.0
    assert result["severity"] == "low"

def test_yolo_empty_boxes():
    model = _make_model({0: "D40"}, [], [])
    result = _yolo_analyze(model, "dummy.jpg")

    assert result["ai_confidence"] == 0.0


# ── _mock ──────────────────────────────────────────────────────────────

def test_mock_deterministic():
    """Same file content should yield the same mock result every time."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(b"\xff\xd8\xff" + b"\x00" * 2048)
        path = f.name
    try:
        r1 = _mock(path)
        r2 = _mock(path)
        assert r1 == r2
    finally:
        os.unlink(path)

def test_mock_has_required_keys():
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(b"\xff\xd8\xff" + b"\x00" * 2048)
        path = f.name
    try:
        result = _mock(path)
        assert "damage_type" in result
        assert "severity" in result
        assert "ai_confidence" in result
        assert "description" in result
        assert result["damage_type"] in {"pothole", "crack", "surface_damage", "multiple"}
        assert result["severity"] in {"high", "medium", "low"}
        assert "[MOCK]" in result["description"]
    finally:
        os.unlink(path)


# ── image_hash ─────────────────────────────────────────────────────────

def test_image_hash():
    data = b"some image bytes"
    expected = hashlib.md5(data).hexdigest()
    assert image_hash(data) == expected

def test_image_hash_different_inputs():
    assert image_hash(b"a") != image_hash(b"b")


# ── is_road_image (mock mode — no model) ──────────────────────────────

def test_is_road_image_valid_jpeg():
    """Valid JPEG with enough bytes should pass in mock mode."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(b"\xff\xd8\xff" + b"\x00" * 2000)
        path = f.name
    try:
        # Force mock mode by ensuring model is not loaded
        with patch("app.services.ai_service._load", return_value=None):
            is_road, conf = is_road_image(path)
            assert is_road is True
            assert conf == 0.80
    finally:
        os.unlink(path)

def test_is_road_image_too_small():
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(b"\xff\xd8\xff" + b"\x00" * 10)
        path = f.name
    try:
        is_road, conf = is_road_image(path)
        assert is_road is False
    finally:
        os.unlink(path)

def test_is_road_image_bad_magic():
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"not an image " * 200)
        path = f.name
    try:
        is_road, conf = is_road_image(path)
        assert is_road is False
    finally:
        os.unlink(path)
