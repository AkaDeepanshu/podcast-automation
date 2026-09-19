"""Topic queue + focus areas + run-next."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import FocusArea, Topic
from backend.schemas import (
    FocusAreaCreate,
    FocusAreaOut,
    FocusAreaUpdate,
    RunNextResult,
    TopicCreate,
    TopicOut,
    TopicUpdate,
)
from backend.services.enqueue import enqueue_job
from core.config_loader import PROJECT_ROOT, load_config
from core.state_db import JobStateDB

router = APIRouter(tags=["topics"])

TOPIC_STATUSES = {
    "draft",
    "approved",
    "queued",
    "running",
    "done",
    "failed",
    "skipped",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _topic_out(t: Topic) -> TopicOut:
    return TopicOut(
        id=t.id,
        title=t.title,
        focus_area_id=t.focus_area_id,
        focus_area_name=t.focus_area.name if t.focus_area else None,
        source=t.source,
        status=t.status,
        priority=t.priority,
        created_at=t.created_at,
        updated_at=t.updated_at,
        job_id=t.job_id,
        error=t.error,
        attempt_count=t.attempt_count,
    )


# ---- Focus areas ----

@router.get("/api/focus-areas", response_model=list[FocusAreaOut])
def list_focus_areas(db: Session = Depends(get_db)):
    rows = db.query(FocusArea).order_by(FocusArea.name).all()
    return [
        FocusAreaOut(
            id=r.id, name=r.name, enabled=r.enabled, created_at=r.created_at
        )
        for r in rows
    ]


@router.post("/api/focus-areas", response_model=FocusAreaOut, status_code=201)
def create_focus_area(body: FocusAreaCreate, db: Session = Depends(get_db)):
    existing = db.query(FocusArea).filter(FocusArea.name == body.name.strip()).first()
    if existing:
        raise HTTPException(status_code=409, detail="Focus area already exists")
    row = FocusArea(
        name=body.name.strip(),
        enabled=body.enabled,
        created_at=_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return FocusAreaOut(
        id=row.id, name=row.name, enabled=row.enabled, created_at=row.created_at
    )


@router.patch("/api/focus-areas/{focus_id}", response_model=FocusAreaOut)
def update_focus_area(
    focus_id: int, body: FocusAreaUpdate, db: Session = Depends(get_db)
):
    row = db.get(FocusArea, focus_id)
    if not row:
        raise HTTPException(status_code=404, detail="Focus area not found")
    if body.name is not None:
        row.name = body.name.strip()
    if body.enabled is not None:
        row.enabled = body.enabled
    db.commit()
    db.refresh(row)
    return FocusAreaOut(
        id=row.id, name=row.name, enabled=row.enabled, created_at=row.created_at
    )


@router.delete("/api/focus-areas/{focus_id}", status_code=204)
def delete_focus_area(focus_id: int, db: Session = Depends(get_db)):
    row = db.get(FocusArea, focus_id)
    if not row:
        raise HTTPException(status_code=404, detail="Focus area not found")
    linked = db.query(Topic).filter(Topic.focus_area_id == focus_id).count()
    if linked:
        raise HTTPException(
            status_code=400,
            detail=f"Focus area has {linked} topic(s); reassign or delete them first",
        )
    db.delete(row)
    db.commit()


# ---- Topics ----

@router.get("/api/topics", response_model=list[TopicOut])
def list_topics(
    status: str | None = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Topic)
    if status:
        q = q.filter(Topic.status == status)
    rows = q.order_by(desc(Topic.priority), desc(Topic.created_at)).all()
    return [_topic_out(t) for t in rows]


@router.post("/api/topics", response_model=TopicOut, status_code=201)
def create_topic(body: TopicCreate, db: Session = Depends(get_db)):
    if body.status not in ("draft", "approved"):
        raise HTTPException(
            status_code=400, detail="New topics must be draft or approved"
        )
    if body.focus_area_id is not None and not db.get(FocusArea, body.focus_area_id):
        raise HTTPException(status_code=400, detail="focus_area_id not found")

    now = _now()
    topic = Topic(
        title=body.title.strip(),
        focus_area_id=body.focus_area_id,
        source=body.source,
        status=body.status,
        priority=body.priority,
        created_at=now,
        updated_at=now,
    )
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return _topic_out(topic)


@router.patch("/api/topics/{topic_id}", response_model=TopicOut)
def update_topic(topic_id: int, body: TopicUpdate, db: Session = Depends(get_db)):
    topic = db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    if topic.status in ("queued", "running"):
        raise HTTPException(status_code=400, detail="Cannot edit a topic mid-run")

    if body.title is not None:
        topic.title = body.title.strip()
    if body.focus_area_id is not None:
        if body.focus_area_id and not db.get(FocusArea, body.focus_area_id):
            raise HTTPException(status_code=400, detail="focus_area_id not found")
        topic.focus_area_id = body.focus_area_id or None
    if body.priority is not None:
        topic.priority = body.priority
    if body.status is not None:
        if body.status not in TOPIC_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status")
        topic.status = body.status

    topic.updated_at = _now()
    db.commit()
    db.refresh(topic)
    return _topic_out(topic)


@router.delete("/api/topics/{topic_id}", status_code=204)
def delete_topic(topic_id: int, db: Session = Depends(get_db)):
    topic = db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    if topic.status in ("queued", "running"):
        raise HTTPException(status_code=400, detail="Cannot delete a topic mid-run")
    db.delete(topic)
    db.commit()


@router.post("/api/topics/{topic_id}/approve", response_model=TopicOut)
def approve_topic(topic_id: int, db: Session = Depends(get_db)):
    topic = db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    if topic.status not in ("draft", "failed", "skipped"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve topic in status={topic.status}",
        )
    topic.status = "approved"
    topic.error = None
    topic.updated_at = _now()
    db.commit()
    db.refresh(topic)
    return _topic_out(topic)


@router.post("/api/queue/run-next", response_model=RunNextResult)
def run_next(db: Session = Depends(get_db)):
    """
    Claim the highest-priority approved topic and enqueue a pipeline job.
    """
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

    now = _now()
    topic.status = "queued"
    topic.updated_at = now
    topic.attempt_count = (topic.attempt_count or 0) + 1
    db.flush()

    try:
        created = enqueue_job(
            db,
            topic=topic.title,
            skip_video=True,
            dispatch=True,
        )
    except HTTPException as exc:
        topic.status = "failed"
        topic.error = str(exc.detail)
        topic.updated_at = _now()
        db.commit()
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
