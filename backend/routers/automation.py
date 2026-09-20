"""Automation settings + start/stop/run-now."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend import locks
from backend.database import get_db
from backend.models import Topic
from backend.schemas import (
    AutomationSettingsOut,
    AutomationSettingsUpdate,
    RunNextResult,
)
from backend.services.automation_settings import get_or_create_settings
from backend.services.queue_runner import claim_and_run_next

router = APIRouter(prefix="/api/automation", tags=["automation"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_out(row, db: Session) -> AutomationSettingsOut:
    depth = db.query(Topic).filter(Topic.status == "approved").count()
    return AutomationSettingsOut(
        enabled=row.enabled,
        require_approval=row.require_approval,
        min_queue_depth=row.min_queue_depth,
        interval_minutes=row.interval_minutes,
        timezone=row.timezone,
        default_skip_video=row.default_skip_video,
        last_tick_at=row.last_tick_at,
        last_run_at=row.last_run_at,
        last_run_job_id=row.last_run_job_id,
        last_error=row.last_error,
        lock_held=locks.is_held(),
        approved_queue_depth=depth,
    )


@router.get("", response_model=AutomationSettingsOut)
def get_automation(db: Session = Depends(get_db)):
    row = get_or_create_settings(db)
    return _to_out(row, db)


@router.put("", response_model=AutomationSettingsOut)
def put_automation(body: AutomationSettingsUpdate, db: Session = Depends(get_db)):
    row = get_or_create_settings(db)
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return _to_out(row, db)


@router.post("/start", response_model=AutomationSettingsOut)
def start_automation(db: Session = Depends(get_db)):
    from backend.notify import emit

    row = get_or_create_settings(db)
    row.enabled = True
    row.last_error = None
    db.commit()
    db.refresh(row)
    emit("automation_started", {})
    return _to_out(row, db)


@router.post("/stop", response_model=AutomationSettingsOut)
def stop_automation(db: Session = Depends(get_db)):
    from backend.notify import emit

    row = get_or_create_settings(db)
    row.enabled = False
    db.commit()
    db.refresh(row)
    emit("automation_stopped", {})
    return _to_out(row, db)


@router.post("/run-now", response_model=RunNextResult)
def run_now(db: Session = Depends(get_db)):
    """Bypass interval; still respects lock, in-progress jobs, and quota is skipped for manual."""
    row = get_or_create_settings(db)
    try:
        result = claim_and_run_next(
            db,
            skip_video=row.default_skip_video,
            use_redis_lock=True,
        )
    except HTTPException as exc:
        row.last_error = str(exc.detail)
        db.commit()
        raise

    row.last_run_at = _now()
    row.last_run_job_id = result.job_id
    row.last_error = None
    db.commit()
    return result
