"""Manual topic discovery trigger."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.discovery import run_discovery, try_acquire_discovery_lock

router = APIRouter(prefix="/api/discovery", tags=["discovery"])


class DiscoveryResult(BaseModel):
    status: str
    created: list[dict] = Field(default_factory=list)
    inserted_status: str | None = None
    detail: str | None = None
    task_id: str | None = None


class DiscoveryRunBody(BaseModel):
    per_area: int = Field(default=3, ge=1, le=10)
    async_run: bool = False


@router.post("/run", response_model=DiscoveryResult)
def run_discovery_endpoint(
    body: DiscoveryRunBody | None = None,
    db: Session = Depends(get_db),
):
    """
    Suggest topics for enabled focus areas (sync by default).
    Set async_run=true to enqueue Celery discover_topics instead.
    """
    opts = body or DiscoveryRunBody()
    if opts.async_run:
        from backend.tasks import discover_topics

        if not try_acquire_discovery_lock():
            raise HTTPException(
                status_code=409,
                detail="Discovery already running or recently ran",
            )
        async_result = discover_topics.delay(per_area=opts.per_area, force=True)
        return DiscoveryResult(
            status="queued",
            task_id=async_result.id,
            detail="discover_topics enqueued",
        )

    result = run_discovery(
        db,
        per_area=opts.per_area,
        notify=True,
        force=True,
    )
    return DiscoveryResult(
        status=result.get("status", "ok"),
        created=result.get("created") or [],
        inserted_status=result.get("inserted_status"),
        detail=result.get("detail"),
    )
