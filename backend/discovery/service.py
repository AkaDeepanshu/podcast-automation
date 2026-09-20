"""Run topic discovery against enabled focus areas and insert Topic rows."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.discovery.llm import LLMTopicDiscovery, normalize_title
from backend.models import FocusArea, Job, Topic
from backend.notify import emit
from backend.services.automation_settings import get_or_create_settings
from core.config_loader import PROJECT_ROOT, load_config
from core.provider_usage_tracker import ProviderUsageTracker

log = logging.getLogger(__name__)

DEFAULT_PER_AREA = 3
DISCOVERY_LOCK_KEY = "automation:discovery_lock"
DISCOVERY_LOCK_TTL = 30 * 60  # don't stack LLM discovery more often than this


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def existing_title_keys(db: Session) -> set[str]:
    keys: set[str] = set()
    for (title,) in db.query(Topic.title).all():
        keys.add(normalize_title(title))
    for (topic,) in (
        db.query(Job.topic).order_by(Job.created_at.desc()).limit(200).all()
    ):
        keys.add(normalize_title(topic))
    return keys


def queue_buffer_depth(db: Session) -> int:
    """draft + approved count — discovery refill target."""
    return (
        db.query(Topic)
        .filter(Topic.status.in_(("draft", "approved")))
        .count()
    )


def quota_allows_discovery(headroom_extra: int = 1) -> bool:
    """True if we still have room for one episode plus discovery calls."""
    config = load_config()
    sg = config.get("script_generation") or {}
    gemini = sg.get("gemini") or {}
    daily_limit = int(gemini.get("daily_limit") or 0)
    if daily_limit <= 0:
        return True
    model = gemini.get("model") or "gemini-2.5-flash"
    segments = int(sg.get("num_segments") or 6)
    needed = segments + 2 + max(1, headroom_extra)
    usage_path = PROJECT_ROOT / config["paths"].get(
        "usage_db", "data/state/provider_usage.db"
    )
    tracker = ProviderUsageTracker(str(usage_path))
    return not tracker.is_near_daily_limit(
        f"gemini:{model}", daily_limit, headroom=needed
    )


def try_acquire_discovery_lock(ttl: int = DISCOVERY_LOCK_TTL) -> bool:
    import redis
    from backend.celery_app import REDIS_URL

    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        return bool(client.set(DISCOVERY_LOCK_KEY, "1", nx=True, ex=ttl))
    finally:
        client.close()


def run_discovery(
    db: Session,
    *,
    per_area: int = DEFAULT_PER_AREA,
    notify: bool = True,
    force: bool = False,
) -> dict:
    """
    Suggest titles per enabled focus area and insert Topic rows.

    Status: draft if require_approval else approved. source=auto.
    """
    settings = get_or_create_settings(db)
    areas = (
        db.query(FocusArea)
        .filter(FocusArea.enabled.is_(True))
        .order_by(FocusArea.name)
        .all()
    )
    if not areas:
        return {"status": "skipped", "detail": "no_enabled_focus_areas", "created": []}

    if not force and not quota_allows_discovery(headroom_extra=len(areas)):
        return {"status": "skipped", "detail": "llm_quota_exhausted", "created": []}

    status = "draft" if settings.require_approval else "approved"
    exclude = existing_title_keys(db)
    discovery = LLMTopicDiscovery()
    created: list[dict] = []
    now = _now()

    for area in areas:
        try:
            titles = discovery.suggest_titles(
                area.name, count=per_area, exclude=exclude
            )
        except Exception as exc:
            log.warning("Discovery failed for focus area %s: %s", area.name, exc)
            continue

        for title in titles:
            key = normalize_title(title)
            if key in exclude:
                continue
            exclude.add(key)
            topic = Topic(
                title=title,
                focus_area_id=area.id,
                source="auto",
                status=status,
                priority=0,
                created_at=now,
                updated_at=now,
            )
            db.add(topic)
            db.flush()
            created.append(
                {
                    "id": topic.id,
                    "title": title,
                    "focus_area": area.name,
                    "status": status,
                }
            )

    db.commit()

    if created and notify:
        emit(
            "topics_suggested",
            {
                "count": len(created),
                "titles": [c["title"] for c in created],
                "status": status,
            },
        )

    return {
        "status": "ok" if created else "empty",
        "created": created,
        "inserted_status": status,
    }
