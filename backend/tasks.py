"""Celery tasks that run the podcast pipeline in the background."""

import json
import logging

import redis

from backend.celery_app import REDIS_URL, celery_app
from backend.episode_overrides import apply_episode_overrides, get_episode_config
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
        return {"job_id": job_id, "status": "ok"}
    except Exception as exc:
        sync_topic_for_job(job_id, error=str(exc))
        raise
    finally:
        log_handler.close()
        redis_client.close()
