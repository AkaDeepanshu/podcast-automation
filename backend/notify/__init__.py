"""Outbound notifications (Telegram first)."""

from __future__ import annotations

import logging

from dotenv import load_dotenv

from backend.notify.base import Notifier, NullNotifier, format_message
from backend.notify.telegram import TelegramNotifier
from core.config_loader import PROJECT_ROOT

log = logging.getLogger(__name__)

__all__ = [
    "Notifier",
    "NullNotifier",
    "TelegramNotifier",
    "emit",
    "format_message",
    "get_notifier",
    "is_configured",
]


def _reload_env() -> None:
    """Pick up .env changes without requiring a full process restart."""
    load_dotenv(PROJECT_ROOT / ".env", override=True)


def is_configured() -> bool:
    _reload_env()
    return TelegramNotifier.from_env() is not None


def get_notifier() -> Notifier:
    _reload_env()
    return TelegramNotifier.from_env() or NullNotifier()


def emit(event: str, payload: dict | None = None) -> None:
    """
    Fire-and-forget notification. Never raises into the pipeline.
    (Test endpoint calls TelegramNotifier.send directly so failures surface.)
    """
    payload = payload or {}
    try:
        notifier = get_notifier()
        if isinstance(notifier, NullNotifier):
            log.warning(
                "Telegram not configured — skipped event=%s (set TELEGRAM_BOT_TOKEN "
                "and TELEGRAM_CHAT_ID in .env, then restart worker/API if needed)",
                event,
            )
            return
        notifier.send(event, payload)
        log.info("Telegram sent event=%s", event)
    except Exception:
        log.exception("Notification emit failed for event=%s", event)
