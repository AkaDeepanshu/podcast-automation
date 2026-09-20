"""Sync topic_queue rows when a linked pipeline job finishes."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.database import SessionLocal
from backend.models import Topic
from core.config_loader import PROJECT_ROOT, load_config
from core.state_db import JobStateDB


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sync_topic_for_job(job_id: str, error: str | None = None) -> None:
    """
    Update any Topic linked to job_id from the authoritative JobStateDB status.
    completed / completed_with_warnings → done; failed → failed.
    Releases the automation Redis lock when the topic leaves running.
    """
    from backend import locks

    config = load_config()
    state = JobStateDB(str(PROJECT_ROOT / config["paths"]["state_db"]))
    job = state.get_job(job_id)
    if not job:
        return

    job_status = job["status"]
    db = SessionLocal()
    try:
        topic = db.query(Topic).filter(Topic.job_id == job_id).first()
        if not topic:
            if job_status in ("completed", "completed_with_warnings", "failed"):
                locks.release()
            return

        now = _now()
        if job_status in ("completed", "completed_with_warnings"):
            topic.status = "done"
            topic.error = None
            locks.release()
        elif job_status == "failed":
            topic.status = "failed"
            topic.error = error or "job_failed"
            locks.release()
        else:
            return

        topic.updated_at = now
        db.commit()
    finally:
        db.close()
