import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "roadwatch",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks.inference_task"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.tasks.inference_task.run_inference": {"queue": "inference"},
        "app.tasks.inference_task.run_escalation": {"queue": "default"},
    },
    beat_schedule={
        "sla-escalation-check": {
            "task": "app.tasks.inference_task.run_escalation",
            "schedule": 3600.0,
        },
    },
)
