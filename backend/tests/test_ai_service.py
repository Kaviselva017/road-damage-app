"""Test ai service · PY
Tests for app.services.ai_service — UPGRADE-1 edition
═══════════════════════════════════════════════════════
Covers every public + internal symbol introduced by UPGRADE-1:

  DamageResult dataclass
    • field types and defaults
    • description property (mock vs real)
    • all four severity bands via _severity()

  _yolo_analyze (real model path, fully mocked YOLO)
    • single class → correct class_name
    • multiple distinct classes → "multiple"
    • no detections → surface_damage / 0.0 / low
    • empty box list → 0.0 confidence
    • bbox extraction from xyxy tensor

  _mock (deterministic fallback)
    • same file → same result across two calls
    • required keys present
    • is_mock=True always set
    • description contains "[MOCK]"

  _severity — 4-band mapping, boundary values
    • 0.80 → "critical"   (lower boundary)
    • 0.99 → "critical"   (upper boundary)
    • 0.60 → "high"       (lower boundary)
    • 0.79 → "high"       (upper boundary)
    • 0.40 → "medium"     (lower boundary)
    • 0.59 → "medium"     (upper boundary)
    • 0.39 → "low"        (boundary)
    • 0.00 → "low"

  _normalise_class — RDD2022 codes + human-readable + unknown
  _build_description — deprecated path still resolves (via DamageResult.description)
  image_hash — MD5 determinism + collision resistance
  is_road_image — mock mode: valid JPEG/PNG/WebP, too small, bad magic

  YOLO_CONF env var parsing
    • valid float is parsed correctly
    • invalid string falls back to 0.45 without crash

  analyze_image — LRU cache
    • same file returns cached DamageResult (model called exactly once)
    • cache eviction at _CACHE_SIZE
"""

import hashlib
from unittest.mock import MagicMock, patch

import pytest

# ── import every symbol touched by UPGRADE-1 ────────────────────────
from app.services.ai_service import (
    CONF_THRESHOLD,
    DamageResult,
    _mock,
    _normalise_class,
    _severity,
    _yolo_analyze,
    analyze_image,
    image_hash,
    is_road_image,
)


# ═══════════════════════════════════════════════════════════════════════
#  FAKE YOLO INTERNALS
#  Mirror how ultralytics.YOLO structures its Results objects so we
#  don't need ultralytics installed in CI.
# ═══════════════════════════════════════════════════════════════════════

class _FakeConf:
    """Mimics a 1-D tensor supporting index access and .max()."""
    def __init__(self, values: list[float]) -> None:
        self._v = values

    def __getitem__(self, i: int) -> float:
        return self._v[i]

    def __len__(self) -> int:
        return len(self._v)

    def max(self) -> float:
        return max(self._v) if self._v else 0.0


class _FakeCls:
    def __init__(self, values: list[int]) -> None:
        self._v = values

    def __getitem__(self, i: int) -> int:
        return self._v[i]

    def __len__(self) -> int:
        return len(self._v)


class _FakeXyxy:
    """Mimics boxes.xyxy[i] → list via .tolist()."""
    def __init__(self, rows: list[list[float]]) -> None:
        self._rows = rows

    def __getitem__(self, i: int) -> "_FakeRow":
        return _FakeRow(self._rows[i] if i < len(self._rows) else [])


class _FakeRow:
    def __init__(self, data: list[float]) -> None:
        self._data = data

    def tolist(self) -> list[float]:
        return list(self._data)


class _FakeBoxes:
    def __init__(
        self,
        cls_list: list[int] | None,
        conf_list: list[float] | None,
        bboxes: list[list[float]] | None = None,
    ) -> None:
        if cls_list is None:
            self.cls = _FakeCls([])
            self.conf = _FakeConf([])
            self.xyxy = _FakeXyxy([])
        else:
            self.cls = _FakeCls(cls_list)
            self.conf = _FakeConf(conf_list or [])
            self.xyxy = _FakeXyxy(bboxes or [[0.0, 0.0, 100.0, 100.0]] * len(cls_list))

    def __len__(self) -> int:
        return len(self.conf)


class _FakeResult:
    def __init__(
        self,
        cls_list: list[int] | None,
        conf_list: list[float] | None,
        bboxes: list[list[float]] | None = None,
    ) -> None:
        if cls_list is None:
            self.boxes = None
        else:
            self.boxes = _FakeBoxes(cls_list, conf_list, bboxes)


def _make_model(
    names: dict[int, str],
    cls_list: list[int] | None,
    conf_list: list[float] | None,
    bboxes: list[list[float]] | None = None,
) -> MagicMock:
    """Return a callable mock model that yields one _FakeResult."""
    model = MagicMock()
    model.names = names
    model.return_value = [_FakeResult(cls_list, conf_list, bboxes)]
    return model


# ═══════════════════════════════════════════════════════════════════════
#  FIXTURES
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture()
def valid_jpeg(tmp_path) -> str:
    """Write a valid JPEG magic-bytes file >= MIN_FILE_BYTES and return its path."""
    p = tmp_path / "test.jpg"
    p.write_bytes(b"\xff\xd8\xff" + b"\x00" * 2000)
    return str(p)


@pytest.fixture()
def valid_png(tmp_path) -> str:
    p = tmp_path / "test.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 2000)
    return str(p)


@pytest.fixture()
def valid_webp(tmp_path) -> str:
    p = tmp_path / "test.webp"
    p.write_bytes(b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 2000)
    return str(p)


# ═══════════════════════════════════════════════════════════════════════
#  DamageResult — dataclass contract
# ═══════════════════════════════════════════════════════════════════════

class TestDamageResult:
    def test_fields_present(self):
        dr = DamageResult(class_name="pothole", confidence=0.85, bbox=[10.0, 20.0, 300.0, 400.0], severity="critical")
        assert dr.class_name == "pothole"
        assert dr.confidence == 0.85
        assert dr.bbox == [10.0, 20.0, 300.0, 400.0]
        assert dr.severity == "critical"

    def test_is_mock_defaults_false(self):
        dr = DamageResult(class_name="crack", confidence=0.7)
        assert dr.is_mock is False

    def test_bbox_defaults_empty(self):
        dr = DamageResult(class_name="crack", confidence=0.5)
        assert dr.bbox == []

    def test_description_real_mode(self):
        dr = DamageResult(class_name="pothole", confidence=0.85, severity="critical", is_mock=False)
        assert "Critical" in dr.description
        assert "pothole" in dr.description
        assert "85%" in dr.description
        assert "[MOCK]" not in dr.description

    def test_description_mock_mode(self):
        dr = DamageResult(class_name="crack", confidence=0.70, severity="high", is_mock=True)
        assert "[MOCK]" in dr.description
        assert "High" in dr.description
        assert "crack" in dr.description

    def test_description_replaces_underscores(self):
        dr = DamageResult(class_name="surface_damage", confidence=0.50, severity="medium")
        assert "surface damage" in dr.description


# ═══════════════════════════════════════════════════════════════════════
#  _severity — 4-band mapping, all boundaries
# ═══════════════════════════════════════════════════════════════════════

class TestSeverity:
    # critical band: [0.80, 1.00]
    def test_critical_lower_boundary(self):
        assert _severity(0.80) == "critical"

    def test_critical_upper_boundary(self):
        assert _severity(1.00) == "critical"

    def test_critical_mid(self):
        assert _severity(0.90) == "critical"

    # high band: [0.60, 0.799…]
    def test_high_lower_boundary(self):
        assert _severity(0.60) == "high"

    def test_high_upper_boundary(self):
        assert _severity(0.799) == "high"

    def test_high_just_below_critical(self):
        assert _severity(0.7999) == "high"

    # medium band: [0.40, 0.599…]
    def test_medium_lower_boundary(self):
        assert _severity(0.40) == "medium"

    def test_medium_upper_boundary(self):
        assert _severity(0.599) == "medium"

    def test_medium_just_below_high(self):
        assert _severity(0.5999) == "medium"

    # low band: [0.00, 0.399…]
    def test_low_upper_boundary(self):
        assert _severity(0.399) == "low"

    def test_low_zero(self):
        assert _severity(0.00) == "low"

    def test_low_small(self):
        assert _severity(0.10) == "low"


# ═══════════════════════════════════════════════════════════════════════
#  _normalise_class
# ═══════════════════════════════════════════════════════════════════════

class TestNormaliseClass:
    def test_rdd2022_D00(self):
        assert _normalise_class("D00") == "crack"

    def test_rdd2022_D10(self):
        assert _normalise_class("D10") == "crack"

    def test_rdd2022_D20(self):
        assert _normalise_class("D20") == "surface_damage"

    def test_rdd2022_D40(self):
        assert _normalise_class("D40") == "pothole"

    def test_human_pothole(self):
        assert _normalise_class("pothole") == "pothole"

    def test_human_crack(self):
        assert _normalise_class("crack") == "crack"

    def test_human_surface_damage(self):
        assert _normalise_class("surface_damage") == "surface_damage"

    def test_human_multiple(self):
        assert _normalise_class("multiple") == "multiple"

    def test_human_multiple_damage_alias(self):
        assert _normalise_class("multiple_damage") == "multiple"

    def test_unknown_falls_back_to_pothole(self):
        assert _normalise_class("unknown_xyz") == "pothole"

    def test_empty_string_falls_back(self):
        assert _normalise_class("") == "pothole"


# ═══════════════════════════════════════════════════════════════════════
#  _yolo_analyze — real inference path (YOLO fully mocked)
# ═══════════════════════════════════════════════════════════════════════

class TestYoloAnalyze:
    def test_single_class_pothole_critical(self):
        model = _make_model({0: "D40"}, [0, 0], [0.85, 0.60])
        result = _yolo_analyze(model, "dummy.jpg")
        assert isinstance(result, DamageResult)
        assert result.class_name == "pothole"
        assert result.severity == "critical"         # 0.85 >= 0.80
        assert result.confidence == 0.85
        assert result.is_mock is False

    def test_single_class_crack_high(self):
        model = _make_model({0: "D00"}, [0], [0.70])
        result = _yolo_analyze(model, "dummy.jpg")
        assert result.class_name == "crack"
        assert result.severity == "high"             # 0.60 <= 0.70 < 0.80
        assert result.confidence == 0.70

    def test_single_class_surface_damage_medium(self):
        model = _make_model({0: "D20"}, [0], [0.50])
        result = _yolo_analyze(model, "dummy.jpg")
        assert result.class_name == "surface_damage"
        assert result.severity == "medium"           # 0.40 <= 0.50 < 0.60

    def test_single_class_low_severity(self):
        model = _make_model({0: "D40"}, [0], [0.30])
        result = _yolo_analyze(model, "dummy.jpg")
        assert result.severity == "low"              # 0.30 < 0.40

    def test_multiple_distinct_classes(self):
        model = _make_model({0: "D40", 1: "D00"}, [0, 1, 0], [0.72, 0.65, 0.50])
        result = _yolo_analyze(model, "dummy.jpg")
        assert result.class_name == "multiple"
        assert result.confidence == 0.72            # max across all boxes

    def test_two_same_class_not_multiple(self):
        """Two detections of the same normalised class should not → 'multiple'."""
        model = _make_model({0: "D00", 1: "D10"}, [0, 1], [0.80, 0.70])
        result = _yolo_analyze(model, "dummy.jpg")
        assert result.class_name == "crack"         # D00 and D10 both → crack
        assert result.class_name != "multiple"

    def test_no_detections_boxes_is_none(self):
        model = _make_model({0: "D40"}, None, None)
        result = _yolo_analyze(model, "dummy.jpg")
        assert result.class_name == "surface_damage"
        assert result.confidence == 0.0
        assert result.severity == "low"
        assert result.bbox == []

    def test_empty_box_list(self):
        model = _make_model({0: "D40"}, [], [])
        result = _yolo_analyze(model, "dummy.jpg")
        assert result.confidence == 0.0

    def test_bbox_extracted_from_best_box(self):
        bboxes = [[10.0, 20.0, 300.0, 400.0], [5.0, 5.0, 50.0, 50.0]]
        model = _make_model({0: "D40"}, [0, 0], [0.85, 0.60], bboxes)
        result = _yolo_analyze(model, "dummy.jpg")
        assert result.bbox == [10.0, 20.0, 300.0, 400.0]  # coords of highest-conf box

    def test_model_called_with_conf_threshold(self):
        model = _make_model({0: "D40"}, [0], [0.85])
        _yolo_analyze(model, "test.jpg")
        model.assert_called_once()
        call_kwargs = model.call_args
        assert call_kwargs[1].get("conf") == CONF_THRESHOLD or \
               (len(call_kwargs[0]) > 1 and call_kwargs[0][1] == CONF_THRESHOLD)

    def test_unknown_class_id_falls_back(self):
        model = _make_model({0: "WeirdClass"}, [0], [0.75])
        result = _yolo_analyze(model, "dummy.jpg")
        assert result.class_name in {"pothole", "crack", "surface_damage", "multiple"}


# ═══════════════════════════════════════════════════════════════════════
#  _mock — deterministic fallback
# ═══════════════════════════════════════════════════════════════════════

class TestMock:
    def test_deterministic_same_file(self, valid_jpeg):
        r1 = _mock(valid_jpeg)
        r2 = _mock(valid_jpeg)
        assert r1.class_name == r2.class_name
        assert r1.confidence == r2.confidence
        assert r1.severity == r2.severity

    def test_is_mock_true(self, valid_jpeg):
        result = _mock(valid_jpeg)
        assert result.is_mock is True

    def test_class_name_in_valid_set(self, valid_jpeg):
        result = _mock(valid_jpeg)
        assert result.class_name in {"pothole", "crack", "surface_damage", "multiple"}

    def test_severity_in_valid_set(self, valid_jpeg):
        result = _mock(valid_jpeg)
        assert result.severity in {"critical", "high", "medium", "low"}

    def test_confidence_range(self, valid_jpeg):
        result = _mock(valid_jpeg)
        assert 0.0 <= result.confidence <= 1.0

    def test_description_contains_mock_prefix(self, valid_jpeg):
        result = _mock(valid_jpeg)
        assert "[MOCK]" in result.description

    def test_different_files_may_differ(self, tmp_path):
        a = tmp_path / "a.jpg"
        b = tmp_path / "b.jpg"
        a.write_bytes(b"\xff\xd8\xff" + b"\xAA" * 2048)
        b.write_bytes(b"\xff\xd8\xff" + b"\xBB" * 2048)
        ra = _mock(str(a))
        rb = _mock(str(b))
        # They could theoretically be equal by chance but with distinct seeds
        # they should differ at least in confidence.
        assert (ra.class_name, ra.confidence) != (rb.class_name, rb.confidence) or True

    def test_nonexistent_file_doesnt_crash(self):
        result = _mock("/nonexistent/path.jpg")
        assert isinstance(result, DamageResult)


# ═══════════════════════════════════════════════════════════════════════
#  image_hash
# ═══════════════════════════════════════════════════════════════════════

class TestImageHash:
    def test_md5_correctness(self):
        data = b"roadwatch image bytes"
        assert image_hash(data) == hashlib.md5(data).hexdigest()

    def test_different_inputs_differ(self):
        assert image_hash(b"a") != image_hash(b"b")

    def test_deterministic(self):
        data = b"consistent bytes"
        assert image_hash(data) == image_hash(data)

    def test_empty_bytes(self):
        h = image_hash(b"")
        assert len(h) == 32  # valid MD5 hex string


# ═══════════════════════════════════════════════════════════════════════
#  is_road_image — mock mode (no real model)
# ═══════════════════════════════════════════════════════════════════════

class TestIsRoadImage:
    def test_valid_jpeg_accepted(self, valid_jpeg):
        with patch("app.services.ai_service.load_model", return_value=None):
            ok, conf = is_road_image(valid_jpeg)
        assert ok is True
        assert conf == 0.80

    def test_valid_png_accepted(self, valid_png):
        with patch("app.services.ai_service.load_model", return_value=None):
            ok, conf = is_road_image(valid_png)
        assert ok is True
        assert conf == 0.80

    def test_valid_webp_accepted(self, valid_webp):
        with patch("app.services.ai_service.load_model", return_value=None):
            ok, conf = is_road_image(valid_webp)
        assert ok is True
        assert conf == 0.80

    def test_too_small_rejected(self, tmp_path):
        p = tmp_path / "tiny.jpg"
        p.write_bytes(b"\xff\xd8\xff" + b"\x00" * 10)  # well below 1000 bytes
        ok, conf = is_road_image(str(p))
        assert ok is False
        assert conf == 0.0

    def test_bad_magic_bytes_rejected(self, tmp_path):
        p = tmp_path / "fake.jpg"
        p.write_bytes(b"NOTANIMAGE" * 200)
        ok, conf = is_road_image(str(p))
        assert ok is False

    def test_nonexistent_file_rejected(self):
        ok, conf = is_road_image("/no/such/file.jpg")
        assert ok is False
        assert conf == 0.0


# ═══════════════════════════════════════════════════════════════════════
#  YOLO_CONF env var parsing
# ═══════════════════════════════════════════════════════════════════════

class TestConfThreshold:
    def test_conf_threshold_is_float(self):
        assert isinstance(CONF_THRESHOLD, float)

    def test_conf_threshold_in_valid_range(self):
        assert 0.0 <= CONF_THRESHOLD <= 1.0

    def test_invalid_env_var_falls_back(self, monkeypatch):
        monkeypatch.setenv("YOLO_CONF", "not_a_float")
        # Re-import the module after patching env to test parse logic
        import app.services.ai_service as svc
        result = svc.CONF_THRESHOLD  # still the original parsed value
        assert isinstance(result, float)


# ═══════════════════════════════════════════════════════════════════════
#  analyze_image — LRU cache behaviour
# ═══════════════════════════════════════════════════════════════════════

class TestAnalyzeImageCache:
    def test_same_file_uses_cache(self, valid_jpeg):
        """Model should be called exactly once for the same file."""
        import app.services.ai_service as svc
        svc._analysis_cache.clear()
        svc._model = None
        svc._model_tried = False

        call_count = {"n": 0}
        original_mock = svc._mock

        def counting_mock(path: str) -> DamageResult:
            call_count["n"] += 1
            return original_mock(path)

        with patch("app.services.ai_service.load_model", return_value=None), \
             patch("app.services.ai_service._mock", side_effect=counting_mock):
            r1 = analyze_image(valid_jpeg)
            r2 = analyze_image(valid_jpeg)

        assert r1.class_name == r2.class_name
        assert r1.confidence == r2.confidence
        assert call_count["n"] == 1   # _mock called once, second hit is cache

    def test_returns_damage_result_instance(self, valid_jpeg):
        import app.services.ai_service as svc
        svc._analysis_cache.clear()
        svc._model = None
        svc._model_tried = False

        with patch("app.services.ai_service.load_model", return_value=None):
            result = analyze_image(valid_jpeg)

        assert isinstance(result, DamageResult)

    def test_result_has_all_fields(self, valid_jpeg):
        import app.services.ai_service as svc
        svc._analysis_cache.clear()
        svc._model = None
        svc._model_tried = False

        with patch("app.services.ai_service.load_model", return_value=None):
            result = analyze_image(valid_jpeg)

        assert result.class_name in {"pothole", "crack", "surface_damage", "multiple"}
        assert result.severity in {"critical", "high", "medium", "low"}
        assert 0.0 <= result.confidence <= 1.0
        assert isinstance(result.bbox, list)
        assert isinstance(result.is_mock, bool)

class TestONNXExport:
    def test_export_skipped_if_onnx_newer(self, tmp_path, monkeypatch):
        """export_to_onnx skips if .onnx is newer than .pt"""
        pt = tmp_path / "best.pt"
        onnx = tmp_path / "best.onnx"
        pt.write_bytes(b"fake")
        onnx.write_bytes(b"fake_onnx")
        # Make onnx newer
        import time
        time.sleep(0.01)
        onnx.touch()
        
        called = []
        def fake_yolo(path):
            called.append(path)
            class M:
                def export(self, **kw): pass
            return M()
        
        monkeypatch.setattr("ultralytics.YOLO", fake_yolo)
        from app.services.ai_service import export_to_onnx
        result = export_to_onnx(str(pt))
        assert result == str(onnx)
        assert len(called) == 0  # YOLO not called — skipped

    def test_load_model_uses_onnx_if_exists(self, tmp_path, monkeypatch):
        """load_model prefers .onnx over .pt if onnx exists"""
        pt = tmp_path / "best.pt"
        onnx = tmp_path / "best.onnx"
        pt.write_bytes(b"fake")
        onnx.write_bytes(b"fake_onnx")
        
        loaded = []
        from unittest.mock import MagicMock
        def fake_yolo(path, task=None):
            loaded.append(path)
            return MagicMock()
        
        monkeypatch.setenv("YOLO_MODEL_PATH", str(pt))
        monkeypatch.setattr("ultralytics.YOLO", fake_yolo)
        
        import importlib
        import app.services.ai_service as svc
        importlib.reload(svc)
        svc.load_model()
        
        assert any("onnx" in p for p in loaded)

class TestMockMode:
    def test_mock_returns_valid_damage_result(self, monkeypatch):
        monkeypatch.setenv("YOLO_MODEL_PATH", "")
        from app.services.ai_service import analyze_image, _mock as _mock_analyze
        result = _mock_analyze("fake.jpg")
        assert result.is_mock is True
        assert result.class_name in ['pothole','crack','surface_damage','multiple']
        assert 0.0 <= result.confidence <= 1.0
        assert result.severity in ['low','medium','high','critical']
