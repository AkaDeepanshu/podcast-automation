"""Celery app configured with Redis as broker."""

import os

from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "podcast_automation",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["backend.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Pipeline jobs are long-running (TTS/video); don't soft-time them out.
    task_time_limit=None,
    worker_prefetch_multiplier=1,
)
