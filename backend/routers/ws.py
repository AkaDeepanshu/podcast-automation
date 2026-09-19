"""WebSocket /ws/jobs/{job_id}/logs — Redis pub/sub → browser."""

import asyncio
import json
from pathlib import Path

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.celery_app import REDIS_URL
from core.config_loader import PROJECT_ROOT, load_config

router = APIRouter(tags=["websocket"])

REPLAY_LINES = 200


def _log_path(job_id: str) -> Path:
    logs_dir = PROJECT_ROOT / load_config()["paths"]["logs_dir"]
    return logs_dir / f"{job_id}.log"


def _replay_payloads(job_id: str) -> list[dict]:
    path = _log_path(job_id)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    payloads = []
    for line in lines[-REPLAY_LINES:]:
        level = "INFO"
        if " [WARNING] " in line:
            level = "WARNING"
        elif " [ERROR] " in line:
            level = "ERROR"
        elif " [DEBUG] " in line:
            level = "DEBUG"
        payloads.append({"level": level, "msg": line, "ts": None, "replay": True})
    return payloads


@router.websocket("/ws/jobs/{job_id}/logs")
async def job_logs_ws(websocket: WebSocket, job_id: str):
    await websocket.accept()

    for payload in _replay_payloads(job_id):
        await websocket.send_json(payload)

    client = aioredis.from_url(REDIS_URL, decode_responses=True)
    pubsub = client.pubsub()
    channel = f"logs:{job_id}"
    await pubsub.subscribe(channel)

    async def forward_pubsub():
        async for message in pubsub.listen():
            if message is None:
                continue
            if message.get("type") != "message":
                continue
            data = message.get("data")
            if not data:
                continue
            # RedisLogHandler already publishes JSON strings.
            try:
                payload = json.loads(data)
            except (TypeError, json.JSONDecodeError):
                payload = {"level": "INFO", "msg": str(data), "ts": None}
            await websocket.send_json(payload)

    forward_task = asyncio.create_task(forward_pubsub())
    try:
        while True:
            # Keep the socket open until the client disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        forward_task.cancel()
        try:
            await forward_task
        except asyncio.CancelledError:
            pass
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        await client.aclose()
