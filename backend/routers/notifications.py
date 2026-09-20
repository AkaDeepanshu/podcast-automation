"""Notification status + test send."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.notify import format_message, is_configured
from backend.notify.telegram import TelegramNotifier

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class NotificationStatus(BaseModel):
    telegram_configured: bool


class TestResult(BaseModel):
    status: str
    event: str = "test"


@router.get("/status", response_model=NotificationStatus)
def notification_status():
    return NotificationStatus(telegram_configured=is_configured())


@router.post("/test", response_model=TestResult)
def test_notification():
    """Send a one-off Telegram message. Requires TELEGRAM_* env vars."""
    notifier = TelegramNotifier.from_env()
    if not notifier:
        raise HTTPException(
            status_code=503,
            detail="Telegram not configured — set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env",
        )
    try:
        notifier.send(
            "test",
            {"message": format_message("test", {})},
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return TestResult(status="sent")
