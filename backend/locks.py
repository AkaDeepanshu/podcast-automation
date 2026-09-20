"""Redis single-job lock for automation / run-next."""

from __future__ import annotations

import redis

from backend.celery_app import REDIS_URL

LOCK_KEY = "automation:job_lock"
# Longer than a typical audio-only episode; refresh not required for v1.
DEFAULT_TTL_SECONDS = 3 * 60 * 60


def _client() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def try_acquire(ttl_seconds: int = DEFAULT_TTL_SECONDS) -> bool:
    client = _client()
    try:
        return bool(client.set(LOCK_KEY, "1", nx=True, ex=ttl_seconds))
    finally:
        client.close()


def release() -> None:
    client = _client()
    try:
        client.delete(LOCK_KEY)
    finally:
        client.close()


def is_held() -> bool:
    client = _client()
    try:
        return bool(client.exists(LOCK_KEY))
    finally:
        client.close()
