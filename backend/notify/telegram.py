"""Telegram Bot API notifier (one HTTP POST per message)."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

from backend.notify.base import format_message

log = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token = token.strip()
        self.chat_id = str(chat_id).strip()

    @classmethod
    def from_env(cls) -> TelegramNotifier | None:
        token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip().strip('"').strip("'")
        chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip().strip('"').strip("'")
        if not token or not chat_id:
            return None
        return cls(token, chat_id)

    def send(self, event: str, payload: dict) -> None:
        text = format_message(event, payload)
        url = f"{TELEGRAM_API}/bot{self.token}/sendMessage"
        body = json.dumps(
            {
                "chat_id": self.chat_id,
                "text": text,
                "disable_web_page_preview": True,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            if not data.get("ok"):
                log.warning("Telegram API not ok: %s", data)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            log.warning("Telegram HTTP %s: %s", exc.code, detail)
            raise RuntimeError(f"Telegram send failed ({exc.code}): {detail}") from exc
        except Exception as exc:
            log.warning("Telegram send failed: %s", exc)
            raise
