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
from backend.services.automation_settings import get_or_create_settings
from backend.services.queue_runner import claim_and_run_next

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
    settings = get_or_create_settings(db)
    status = body.status
    if settings.require_approval and status == "approved":
        # Still allow explicit approved from UI checkbox
        pass
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
        status=status,
        priority=body.priority,
        created_at=now,
        updated_at=now,
    )
    db.add(topic)
    db.commit()
    db.refresh(topic)
    from backend.notify import emit

    emit(
        "topic_added",
        {"title": topic.title, "status": topic.status, "source": topic.source},
    )
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
    from backend.notify import emit

    emit("topic_approved", {"title": topic.title, "topic_id": topic.id})
    return _topic_out(topic)


@router.post("/api/queue/run-next", response_model=RunNextResult)
def run_next(db: Session = Depends(get_db)):
    settings = get_or_create_settings(db)
    result = claim_and_run_next(
        db,
        skip_video=settings.default_skip_video,
        use_redis_lock=True,
    )
    settings.last_run_at = _now()
    settings.last_run_job_id = result.job_id
    settings.last_error = None
    db.commit()
    return result
