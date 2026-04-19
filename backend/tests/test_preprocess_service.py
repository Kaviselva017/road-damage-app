import os
import numpy as np

def make_test_image(path: str, w=640, h=480):
    import cv2
    img = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)
    cv2.imwrite(path, img)

class TestCLAHE:
    def test_clahe_returns_different_path(self, tmp_path):
        img_path = str(tmp_path / "test.jpg")
        make_test_image(img_path)
        from app.services.preprocess_service import apply_clahe
        result = apply_clahe(img_path)
        assert result != img_path
        assert os.path.exists(result)
        os.unlink(result)
    
    def test_clahe_invalid_image_returns_original(self, tmp_path):
        fake = str(tmp_path / "fake.jpg")
        open(fake, 'w').write("not an image")
        from app.services.preprocess_service import apply_clahe
        result = apply_clahe(fake)
        assert result == fake

    def test_clahe_disabled_returns_original(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAHE_ENABLED", "false")
        img_path = str(tmp_path / "test.jpg")
        make_test_image(img_path)
        from app.services import preprocess_service
        import importlib
        importlib.reload(preprocess_service)
        primary, tta = preprocess_service.preprocess_for_inference(img_path)
        assert primary == img_path

class TestTTA:
    def test_tta_generates_4_variants(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TTA_ENABLED", "true")
        img_path = str(tmp_path / "test.jpg")
        make_test_image(img_path)
        from app.services import preprocess_service
        import importlib
        importlib.reload(preprocess_service)
        tta = preprocess_service.generate_tta_variants(img_path)
        assert len(tta) == 4
        for p in tta:
            assert os.path.exists(p)
            os.unlink(p)
