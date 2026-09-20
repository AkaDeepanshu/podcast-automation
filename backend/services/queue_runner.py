"""Claim next approved topic and enqueue a pipeline job."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.models import FocusArea, Topic
from backend.schemas import RunNextResult
from backend.services.enqueue import enqueue_job
from core.config_loader import PROJECT_ROOT, load_config
from core.state_db import JobStateDB


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def claim_and_run_next(
    db: Session,
    *,
    skip_video: bool = True,
    use_redis_lock: bool = True,
) -> RunNextResult:
    """
    Atomically claim the highest-priority approved topic and dispatch Celery.

    Raises HTTPException on conflict / empty queue (same codes as the API).
    """
    from backend import locks

    state = JobStateDB(str(PROJECT_ROOT / load_config()["paths"]["state_db"]))
    if state.find_in_progress_jobs():
        raise HTTPException(
            status_code=409,
            detail="A job is already in progress; wait for it to finish",
        )

    running_topic = (
        db.query(Topic).filter(Topic.status.in_(("queued", "running"))).first()
    )
    if running_topic:
        raise HTTPException(
            status_code=409,
            detail="A topic is already queued or running",
        )

    if use_redis_lock and locks.is_held():
        raise HTTPException(
            status_code=409,
            detail="Automation lock is held; a job may still be running",
        )

    topic = (
        db.query(Topic)
        .filter(Topic.status == "approved")
        .order_by(desc(Topic.priority), Topic.created_at)
        .first()
    )
    if not topic:
        raise HTTPException(status_code=404, detail="No approved topics in the queue")

    if topic.focus_area_id:
        area = db.get(FocusArea, topic.focus_area_id)
        if area and not area.enabled:
            raise HTTPException(
                status_code=400,
                detail=f"Focus area '{area.name}' is disabled",
            )

    if use_redis_lock and not locks.try_acquire():
        raise HTTPException(
            status_code=409,
            detail="Could not acquire automation lock",
        )

    now = _now()
    topic.status = "queued"
    topic.updated_at = now
    topic.attempt_count = (topic.attempt_count or 0) + 1
    db.flush()

    try:
        created = enqueue_job(
            db,
            topic=topic.title,
            skip_video=skip_video,
            dispatch=True,
            notify_source="queue",
        )
    except HTTPException as exc:
        topic.status = "failed"
        topic.error = str(exc.detail)
        topic.updated_at = _now()
        db.commit()
        if use_redis_lock:
            locks.release()
        raise
    except Exception as exc:
        topic.status = "failed"
        topic.error = str(exc)
        topic.updated_at = _now()
        db.commit()
        if use_redis_lock:
            locks.release()
        raise

    topic.status = "running"
    topic.job_id = created.job_id
    topic.error = None
    topic.updated_at = _now()
    db.commit()

    return RunNextResult(
        topic_id=topic.id,
        job_id=created.job_id,
        topic=topic.title,
        task_id=created.task_id,
        status=topic.status,
    )
