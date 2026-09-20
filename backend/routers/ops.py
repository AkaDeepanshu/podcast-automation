"""Operational health: Redis, Celery workers, quota, queue depth."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend import locks
from backend.celery_app import REDIS_URL, celery_app
from backend.database import get_db
from backend.discovery import queue_buffer_depth
from backend.models import Topic
from backend.notify import is_configured as telegram_configured
from backend.services.automation_settings import get_or_create_settings
from core.config_loader import PROJECT_ROOT, load_config
from core.provider_usage_tracker import ProviderUsageTracker
from core.state_db import JobStateDB

router = APIRouter(prefix="/api/ops", tags=["ops"])


class QuotaInfo(BaseModel):
    key: str
    used_today: int
    daily_limit: int
    headroom_needed: int
    near_limit: bool


class OpsStatus(BaseModel):
    ok: bool
    redis_ok: bool
    workers_online: int = 0
    worker_names: list[str] = Field(default_factory=list)
    beat_hint: str = (
        "Beat is a separate process — confirm `celery … beat` is running "
        "if automation is enabled and last_tick_at is stale."
    )
    telegram_configured: bool
    automation_enabled: bool
    lock_held: bool
    approved_queue_depth: int
    buffer_queue_depth: int
    min_queue_depth: int
    interval_minutes: int
    last_tick_at: str | None
    last_run_at: str | None
    last_error: str | None
    in_progress_jobs: list[str] = Field(default_factory=list)
    gemini_quota: QuotaInfo | None = None
    checks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


def _redis_ok() -> bool:
    import redis

    client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=1)
    try:
        return bool(client.ping())
    except Exception:
        return False
    finally:
        client.close()


def _worker_info() -> tuple[int, list[str]]:
    try:
        insp = celery_app.control.inspect(timeout=1.0)
        ping = insp.ping() if insp else None
        if not ping:
            return 0, []
        return len(ping), sorted(ping.keys())
    except Exception:
        return 0, []


def _gemini_quota() -> QuotaInfo:
    config = load_config()
    sg = config.get("script_generation") or {}
    gemini = sg.get("gemini") or {}
    daily_limit = int(gemini.get("daily_limit") or 0)
    model = gemini.get("model") or "gemini-2.5-flash"
    segments = int(sg.get("num_segments") or 6)
    headroom = segments + 2
    key = f"gemini:{model}"
    usage_path = PROJECT_ROOT / config["paths"].get(
        "usage_db", "data/state/provider_usage.db"
    )
    tracker = ProviderUsageTracker(str(usage_path))
    used = tracker.get_today_count(key)
    near = (
        daily_limit > 0
        and tracker.is_near_daily_limit(key, daily_limit, headroom=headroom)
    )
    return QuotaInfo(
        key=key,
        used_today=used,
        daily_limit=daily_limit,
        headroom_needed=headroom,
        near_limit=near,
    )


@router.get("/status", response_model=OpsStatus)
def ops_status(db: Session = Depends(get_db)):
    settings = get_or_create_settings(db)
    redis_ok = _redis_ok()
    workers_online, worker_names = _worker_info() if redis_ok else (0, [])
    approved = db.query(Topic).filter(Topic.status == "approved").count()
    buffer = queue_buffer_depth(db)
    tg = telegram_configured()
    quota = _gemini_quota()

    state = JobStateDB(str(PROJECT_ROOT / load_config()["paths"]["state_db"]))
    in_progress = [j["job_id"] for j in state.find_in_progress_jobs()]

    checks: list[str] = []
    recs: list[str] = []

    if not redis_ok:
        checks.append("redis_down")
        recs.append("Start Redis: `docker compose up -d`")
    if workers_online < 1:
        checks.append("no_workers")
        recs.append(
            "Start worker: `celery -A backend.celery_app worker --concurrency=1 --loglevel=info`"
        )
    if settings.enabled and workers_online < 1:
        checks.append("automation_without_worker")
    if not tg:
        checks.append("telegram_unconfigured")
        recs.append("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env for alerts")
    if settings.enabled and approved < settings.min_queue_depth and buffer < settings.min_queue_depth:
        checks.append("queue_below_min")
        recs.append(
            "Approve more topics or wait for discovery; check focus areas are enabled"
        )
    if quota.near_limit:
        checks.append("gemini_near_limit")
        recs.append(
            f"Gemini usage {quota.used_today}/{quota.daily_limit} — "
            "automation will skip new episodes until tomorrow (or raise daily_limit / use fallback)"
        )
    if in_progress:
        checks.append("job_in_progress")
    if settings.interval_minutes < 60 and settings.enabled:
        recs.append(
            "interval_minutes is under 60 — fine for testing; use ~1440 for one episode/day"
        )

    ok = redis_ok and workers_online >= 1 and not quota.near_limit

    return OpsStatus(
        ok=ok,
        redis_ok=redis_ok,
        workers_online=workers_online,
        worker_names=worker_names,
        telegram_configured=tg,
        automation_enabled=settings.enabled,
        lock_held=locks.is_held(),
        approved_queue_depth=approved,
        buffer_queue_depth=buffer,
        min_queue_depth=settings.min_queue_depth,
        interval_minutes=settings.interval_minutes,
        last_tick_at=settings.last_tick_at,
        last_run_at=settings.last_run_at,
        last_error=settings.last_error,
        in_progress_jobs=in_progress,
        gemini_quota=quota,
        checks=checks,
        recommendations=recs,
    )
