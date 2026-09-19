"""Shared job creation + Celery dispatch (used by /api/jobs and run-next)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.models import EpisodeConfig, Job
from backend.schemas import EpisodeConfigIn, JobCreated
from backend.tasks import run_podcast_job
from run_pipeline import make_job_id


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def enqueue_job(
    db: Session,
    *,
    topic: str,
    job_id: str | None = None,
    skip_video: bool = True,
    config: EpisodeConfigIn | None = None,
    dispatch: bool = True,
) -> JobCreated:
    """
    Insert Job + EpisodeConfig, optionally dispatch Celery.

    Caller owns the surrounding transaction semantics for topic claim;
    this function commits the job rows before delay() so workers see them.
    """
    resolved_id = job_id or make_job_id(topic)
    if db.get(Job, resolved_id):
        raise HTTPException(status_code=409, detail=f"Job already exists: {resolved_id}")

    now = _now()
    db.add(
        Job(
            job_id=resolved_id,
            topic=topic,
            status="pending",
            created_at=now,
            updated_at=now,
        )
    )
    db.add(
        EpisodeConfig(
            job_id=resolved_id,
            target_duration_minutes=config.target_duration_minutes if config else None,
            num_segments=config.num_segments if config else None,
            model=config.model if config else None,
            skip_video=skip_video,
        )
    )
    db.commit()

    task_id = ""
    if dispatch:
        try:
            async_result = run_podcast_job.delay(topic, resolved_id, skip_video)
            task_id = async_result.id
        except Exception as exc:
            # Leave job row; caller (run-next) may mark topic failed.
            raise HTTPException(
                status_code=503,
                detail=f"Job created but Celery dispatch failed: {exc}",
            ) from exc

    return JobCreated(
        job_id=resolved_id,
        topic=topic,
        status="pending",
        task_id=task_id,
    )
