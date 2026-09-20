"""Notification interface and shared message formatting."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol


class Notifier(Protocol):
    def send(self, event: str, payload: dict) -> None: ...


class NullNotifier:
    """No-op when Telegram (or other channels) are not configured."""

    def send(self, event: str, payload: dict) -> None:
        return


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def format_message(event: str, payload: dict) -> str:
    """Human-readable Telegram / chat message for a notification event."""
    stamp = _ts()

    if event == "episode_started":
        topic = payload.get("topic") or "episode"
        job_id = payload.get("job_id") or "?"
        source = payload.get("source") or "manual"
        return "\n".join(
            [
                "▶️ Episode started",
                f"Topic: {topic}",
                f"Job: {job_id}",
                f"Source: {source}",
                stamp,
            ]
        )

    if event == "episode_completed":
        topic = payload.get("topic") or "episode"
        job_id = payload.get("job_id") or "?"
        audio = payload.get("audio_hint") or ""
        lines = [
            "✅ Episode ready",
            f"Topic: {topic}",
            f"Job: {job_id}",
        ]
        if audio:
            lines.append(f"Audio: {audio}")
        lines.append("Upload to YouTube when convenient.")
        lines.append(stamp)
        return "\n".join(lines)

    if event == "episode_failed":
        topic = payload.get("topic") or "episode"
        job_id = payload.get("job_id") or "?"
        stage = payload.get("stage") or "unknown"
        error = payload.get("error") or "unknown error"
        return "\n".join(
            [
                "❌ Episode failed",
                f"Topic: {topic}",
                f"Job: {job_id}",
                f"Stage: {stage}",
                f"Error: {error}",
                stamp,
            ]
        )

    if event == "automation_started":
        return "\n".join(
            [
                "🟢 Automation enabled",
                "Beat will dequeue approved topics on schedule.",
                stamp,
            ]
        )

    if event == "automation_stopped":
        return "\n".join(
            [
                "⏸ Automation disabled",
                "Scheduled runs paused. Manual Run next still works.",
                stamp,
            ]
        )

    if event == "topic_approved":
        title = payload.get("title") or "topic"
        return "\n".join(
            [
                "👍 Topic approved",
                f"Title: {title}",
                stamp,
            ]
        )

    if event == "topic_added":
        title = payload.get("title") or "topic"
        status = payload.get("status") or "draft"
        return "\n".join(
            [
                "📝 Topic added",
                f"Title: {title}",
                f"Status: {status}",
                stamp,
            ]
        )

    if event == "queue_low":
        depth = payload.get("depth", 0)
        minimum = payload.get("min_queue_depth", payload.get("min", "?"))
        buffer = payload.get("buffer_depth")
        extra = f" (buffer {buffer})" if buffer is not None else ""
        return "\n".join(
            [
                "⚠️ Topic queue low",
                f"Approved: {depth}{extra} (min {minimum})",
                "Discovery will try to refill. Approve drafts if needed.",
                stamp,
            ]
        )

    if event == "llm_quota_exhausted":
        model = payload.get("model") or "gemini"
        return "\n".join(
            [
                "⚠️ LLM quota near daily limit",
                f"Model: {model}",
                "Skipped starting a new episode / discovery.",
                stamp,
            ]
        )

    if event == "topics_suggested":
        titles = payload.get("titles") or []
        status = payload.get("status") or "draft"
        count = payload.get("count", len(titles))
        lines = [
            f"💡 Suggested {count} topic(s) ({status})",
        ]
        for title in titles[:10]:
            lines.append(f"• {title}")
        if len(titles) > 10:
            lines.append(f"…and {len(titles) - 10} more")
        if status == "draft":
            lines.append("Approve them in Studio → Topics when ready.")
        lines.append(stamp)
        return "\n".join(lines)

    if event == "discovery_skipped":
        detail = payload.get("detail") or "unknown"
        return "\n".join(
            [
                "⏭ Topic discovery skipped",
                f"Reason: {detail}",
                stamp,
            ]
        )

    if event == "test":
        return payload.get("message") or f"Podcast Studio notification test ✅\n{stamp}"

    # Fallback for unknown events
    bits = [f"📢 {event}", stamp]
    for key, value in payload.items():
        bits.append(f"{key}: {value}")
    return "\n".join(bits)
