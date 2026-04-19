from unittest.mock import MagicMock, patch
import pytest

class TestInferenceTask:
    def test_task_registered(self):
        import app.tasks.inference_task
        from app.celery_app import celery_app
        assert "app.tasks.inference_task.run_inference" in celery_app.tasks
    
    def test_escalation_task_registered(self):
        import app.tasks.inference_task
        from app.celery_app import celery_app
        assert "app.tasks.inference_task.run_escalation" in celery_app.tasks
    
    def test_img_bytes_hex_roundtrip(self):
        original = b'\xff\xd8\xff\xe0test'
        hex_str = original.hex()
        recovered = bytes.fromhex(hex_str)
        assert recovered == original
    
    def test_use_celery_env_flag(self, monkeypatch):
        monkeypatch.setenv("USE_CELERY", "true")
        import importlib, app.api.complaints as c
        importlib.reload(c)
        assert c.USE_CELERY is True
        
        monkeypatch.setenv("USE_CELERY", "false")
        importlib.reload(c)
        assert c.USE_CELERY is False
