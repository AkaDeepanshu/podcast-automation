"""Celery tasks that run the podcast pipeline in the background."""

import json
import logging

import redis

from backend.celery_app import REDIS_URL, celery_app
from backend.episode_overrides import apply_episode_overrides, get_episode_config
from backend.notify.events import notify_job_finished
from backend.services.topic_sync import sync_topic_for_job
from core.config_loader import load_config, load_speakers
from run_pipeline import run_job


class RedisLogHandler(logging.Handler):
    """Publish each log record to Redis pub/sub channel logs:{job_id}."""

    def __init__(self, redis_client: redis.Redis, job_id: str):
        super().__init__()
        self.redis = redis_client
        self.channel = f"logs:{job_id}"

    def emit(self, record: logging.LogRecord) -> None:
        try:
            payload = json.dumps(
                {
                    "level": record.levelname,
                    "msg": self.format(record),
                    "ts": record.created,
                }
            )
            self.redis.publish(self.channel, payload)
        except Exception:
            self.handleError(record)


@celery_app.task(bind=True, name="backend.tasks.run_podcast_job")
def run_podcast_job(self, topic: str, job_id: str, skip_video: bool = True):
    """
    Async wrapper around run_pipeline.run_job.

    Loads EpisodeConfig for job_id (if any) and merges duration / segments /
    model / skip_video before running. Attaches RedisLogHandler for live logs.
    """
    config = load_config()
    speakers = load_speakers()
    episode = get_episode_config(job_id)
    config, effective_skip = apply_episode_overrides(config, episode, skip_video)

    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    log_handler = RedisLogHandler(redis_client, job_id)
    try:
        run_job(
            topic=topic,
            job_id=job_id,
            config=config,
            speakers=speakers,
            skip_video=effective_skip,
            log_handlers=[log_handler],
        )
        sync_topic_for_job(job_id)
        notify_job_finished(job_id, topic)
        return {"job_id": job_id, "status": "ok"}
    except Exception as exc:
        sync_topic_for_job(job_id, error=str(exc))
        notify_job_finished(job_id, topic, error=str(exc))
        raise
    finally:
        log_handler.close()
        redis_client.close()


@celery_app.task(name="backend.tasks.discover_topics")
def discover_topics(
    per_area: int = 3,
    force: bool = False,
    reason: str | None = None,
    approved_depth: int | None = None,
    buffer_depth: int | None = None,
    min_queue_depth: int | None = None,
):
    """
    LLM topic suggestions for enabled focus areas.
    Uses a Redis lock so Beat cannot stack overlapping discovery runs.
    """
    from backend.database import SessionLocal
    from backend.discovery import run_discovery, try_acquire_discovery_lock
    from backend.notify import emit

    log = logging.getLogger("discover_topics")
    if not force and not try_acquire_discovery_lock():
        return {"status": "skipped", "detail": "discovery_lock_held"}

    if reason == "queue_low":
        emit(
            "queue_low",
            {
                "depth": approved_depth if approved_depth is not None else 0,
                "buffer_depth": buffer_depth,
                "min_queue_depth": min_queue_depth if min_queue_depth is not None else "?",
            },
        )

    db = SessionLocal()
    try:
        result = run_discovery(db, per_area=per_area, notify=True, force=force)
        if result.get("status") == "skipped":
            emit(
                "discovery_skipped",
                {"detail": result.get("detail") or "skipped"},
            )
        log.info(
            "Discovery finished status=%s created=%d",
            result.get("status"),
            len(result.get("created") or []),
        )
        return result
    except Exception:
        log.exception("discover_topics failed")
        raise
    finally:
        db.close()


@celery_app.task(name="backend.tasks.automation_tick")
def automation_tick():
    """
    Celery Beat entrypoint: refill queue when low, then run next topic if due.
    """
    from datetime import datetime, timedelta, timezone

    from fastapi import HTTPException

    from backend.database import SessionLocal
    from backend.discovery import queue_buffer_depth
    from backend.models import Topic
    from backend.notify import emit
    from backend.services.automation_settings import get_or_create_settings
    from backend.services.queue_runner import claim_and_run_next
    from core.config_loader import PROJECT_ROOT, load_config
    from core.provider_usage_tracker import ProviderUsageTracker

    log = logging.getLogger("automation_tick")
    db = SessionLocal()
    try:
        settings = get_or_create_settings(db)
        now = datetime.now(timezone.utc)
        settings.last_tick_at = now.isoformat()

        if not settings.enabled:
            db.commit()
            return {"status": "disabled"}

        approved_depth = (
            db.query(Topic).filter(Topic.status == "approved").count()
        )
        buffer_depth = queue_buffer_depth(db)

        # Refill draft/approved buffer when below min (before interval gate)
        if buffer_depth < settings.min_queue_depth:
            discover_topics.delay(
                reason="queue_low",
                approved_depth=approved_depth,
                buffer_depth=buffer_depth,
                min_queue_depth=settings.min_queue_depth,
            )

        # Interval gate (minutes since last successful start)
        if settings.last_run_at and settings.interval_minutes > 0:
            try:
                last = datetime.fromisoformat(
                    settings.last_run_at.replace("Z", "+00:00")
                )
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                if now - last < timedelta(minutes=settings.interval_minutes):
                    db.commit()
                    return {"status": "too_soon"}
            except ValueError:
                pass

        # Soft Gemini quota pre-check (~7 calls/episode headroom)
        config = load_config()
        sg = config.get("script_generation") or {}
        gemini = sg.get("gemini") or {}
        daily_limit = int(gemini.get("daily_limit") or 0)
        model = gemini.get("model") or "gemini-2.5-flash"
        segments = int(sg.get("num_segments") or 6)
        needed = segments + 2  # outline + segments + buffer
        usage_path = PROJECT_ROOT / config["paths"].get(
            "usage_db", "data/state/provider_usage.db"
        )
        tracker = ProviderUsageTracker(str(usage_path))
        key = f"gemini:{model}"
        if daily_limit > 0 and tracker.is_near_daily_limit(
            key, daily_limit, headroom=needed
        ):
            if settings.last_error != "llm_quota_exhausted":
                emit(
                    "llm_quota_exhausted",
                    {"model": model, "daily_limit": daily_limit},
                )
            settings.last_error = "llm_quota_exhausted"
            db.commit()
            log.warning("Skipping tick: near Gemini daily limit (%s)", key)
            return {"status": "llm_quota_exhausted"}

        try:
            result = claim_and_run_next(
                db,
                skip_video=settings.default_skip_video,
                use_redis_lock=True,
            )
        except HTTPException as exc:
            detail = str(exc.detail)
            # Empty queue / lock held are normal — don't treat as hard error noise
            if exc.status_code in (404, 409):
                if exc.status_code == 404:
                    settings.last_error = (
                        "queue_low"
                        if approved_depth < settings.min_queue_depth
                        else None
                    )
                else:
                    settings.last_error = detail
                db.commit()
                return {"status": "skipped", "detail": detail}
            settings.last_error = detail
            db.commit()
            return {"status": "error", "detail": detail}

        settings.last_run_at = now.isoformat()
        settings.last_run_job_id = result.job_id
        settings.last_error = None
        db.commit()
        return {
            "status": "started",
            "job_id": result.job_id,
            "topic_id": result.topic_id,
        }
    except Exception as exc:
        log.exception("automation_tick failed")
        try:
            settings = get_or_create_settings(db)
            settings.last_error = str(exc)
            db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()
