"""Celery app configured with Redis as broker."""

import logging
import os

from celery import Celery
from celery.signals import worker_ready

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
ORPHAN_GRACE_MINUTES = int(os.environ.get("ORPHAN_GRACE_MINUTES", "10"))

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
    beat_schedule={
        # Checks settings.enabled + interval; cheap no-op when idle.
        "automation-tick": {
            "task": "backend.tasks.automation_tick",
            "schedule": 60.0,  # every 60 seconds
        },
    },
)

logger = logging.getLogger(__name__)


@worker_ready.connect
def _mark_orphaned_jobs_on_startup(**_kwargs):
    """Fail stuck in_progress jobs left by a previous crashed worker."""
    try:
        from core.config_loader import PROJECT_ROOT, load_config
        from core.state_db import JobStateDB

        config = load_config()
        db = JobStateDB(str(PROJECT_ROOT / config["paths"]["state_db"]))
        marked = db.mark_orphaned_in_progress_jobs(
            grace_minutes=ORPHAN_GRACE_MINUTES,
        )
        if marked:
            logger.warning(
                "Marked %d orphaned in_progress job(s) as failed: %s",
                len(marked),
                ", ".join(marked),
            )
    except Exception:
        logger.exception("Orphan job cleanup failed on worker startup")
