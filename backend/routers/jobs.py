"""Job CRUD, retry, and media streaming endpoints."""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Job, Stage
from backend.schemas import (
    JobCreate,
    JobCreated,
    JobDetail,
    JobSummary,
    RetryResponse,
    StageOut,
    EpisodeConfigOut,
)
from backend.services.enqueue import enqueue_job
from backend.tasks import run_podcast_job
from core.config_loader import PROJECT_ROOT, load_config

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

STAGE_ORDER = ["script", "tts", "assembly", "video"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jobs_dir() -> Path:
    return PROJECT_ROOT / load_config()["paths"]["jobs_dir"]


def _logs_dir() -> Path:
    return PROJECT_ROOT / load_config()["paths"]["logs_dir"]


def _job_dir(job_id: str) -> Path:
    return _jobs_dir() / job_id


def _get_job_or_404(db: Session, job_id: str) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return job


def _stage_outs(job: Job) -> list[StageOut]:
    by_name = {s.stage_name: s for s in job.stages}
    ordered: list[StageOut] = []
    for name in STAGE_ORDER:
        if name in by_name:
            s = by_name[name]
            ordered.append(
                StageOut(
                    stage_name=s.stage_name,
                    status=s.status,
                    error_msg=s.error_msg,
                    updated_at=s.updated_at,
                )
            )
    for s in job.stages:
        if s.stage_name not in STAGE_ORDER:
            ordered.append(
                StageOut(
                    stage_name=s.stage_name,
                    status=s.status,
                    error_msg=s.error_msg,
                    updated_at=s.updated_at,
                )
            )
    return ordered


def _reset_from_stage(db: Session, job: Job, from_stage: str) -> None:
    if from_stage not in STAGE_ORDER:
        raise HTTPException(
            status_code=400,
            detail=f"from_stage must be one of {STAGE_ORDER}",
        )
    start = STAGE_ORDER.index(from_stage)
    to_reset = set(STAGE_ORDER[start:])
    now = _now()

    existing = {s.stage_name: s for s in job.stages}
    for name in to_reset:
        if name in existing:
            existing[name].status = "pending"
            existing[name].error_msg = None
            existing[name].updated_at = now
        else:
            db.add(
                Stage(
                    job_id=job.job_id,
                    stage_name=name,
                    status="pending",
                    error_msg=None,
                    updated_at=now,
                )
            )

    # Failed TTS lines should be retryable when restarting from tts (or earlier).
    if start <= STAGE_ORDER.index("tts"):
        for line in list(job.tts_lines):
            if line.status == "failed":
                db.delete(line)

    job.status = "pending"
    job.updated_at = now


@router.post("", response_model=JobCreated, status_code=201)
def create_job(body: JobCreate, db: Session = Depends(get_db)):
    return enqueue_job(
        db,
        topic=body.topic,
        job_id=body.job_id,
        skip_video=body.skip_video,
        config=body.config,
        dispatch=True,
    )


@router.get("", response_model=list[JobSummary])
def list_jobs(db: Session = Depends(get_db)):
    rows = db.query(Job).order_by(Job.created_at.desc()).all()
    return [
        JobSummary(
            job_id=j.job_id,
            topic=j.topic,
            status=j.status,
            created_at=j.created_at,
            updated_at=j.updated_at,
        )
        for j in rows
    ]


@router.get("/{job_id}", response_model=JobDetail)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = _get_job_or_404(db, job_id)
    ep = job.episode_config
    return JobDetail(
        job_id=job.job_id,
        topic=job.topic,
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at,
        stages=_stage_outs(job),
        episode_config=(
            EpisodeConfigOut(
                target_duration_minutes=ep.target_duration_minutes,
                num_segments=ep.num_segments,
                model=ep.model,
                skip_video=ep.skip_video,
            )
            if ep
            else None
        ),
    )


@router.post("/{job_id}/retry", response_model=RetryResponse)
def retry_job(
    job_id: str,
    from_stage: str = Query(..., description="Stage to restart from"),
    db: Session = Depends(get_db),
):
    job = _get_job_or_404(db, job_id)
    # Respect original skip_video unless the user is explicitly retrying video.
    skip_video = bool(job.episode_config and job.episode_config.skip_video)
    if from_stage == "video":
        skip_video = False

    _reset_from_stage(db, job, from_stage)
    db.commit()

    async_result = run_podcast_job.delay(job.topic, job.job_id, skip_video)
    return RetryResponse(
        job_id=job.job_id,
        from_stage=from_stage,
        task_id=async_result.id,
        status=job.status,
    )


@router.get("/{job_id}/script")
def get_script(job_id: str, db: Session = Depends(get_db)):
    _get_job_or_404(db, job_id)
    path = _job_dir(job_id) / "02_script.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Script not available yet")
    with open(path) as f:
        return json.load(f)


@router.get("/{job_id}/audio")
def get_audio(job_id: str, db: Session = Depends(get_db)):
    _get_job_or_404(db, job_id)
    path = _job_dir(job_id) / "04_final_audio.wav"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio not available yet")
    return FileResponse(
        path,
        media_type="audio/wav",
        filename=f"{job_id}.wav",
    )


@router.get("/{job_id}/video")
def get_video(job_id: str, db: Session = Depends(get_db)):
    _get_job_or_404(db, job_id)
    path = _job_dir(job_id) / "05_video.mp4"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Video not available yet")
    return FileResponse(
        path,
        media_type="video/mp4",
        filename=f"{job_id}.mp4",
    )


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: str, db: Session = Depends(get_db)):
    job = _get_job_or_404(db, job_id)
    db.delete(job)
    db.commit()

    job_dir = _job_dir(job_id)
    if job_dir.exists():
        shutil.rmtree(job_dir)

    log_path = _logs_dir() / f"{job_id}.log"
    if log_path.exists():
        log_path.unlink()
