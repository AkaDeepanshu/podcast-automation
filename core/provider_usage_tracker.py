"""
Local daily call-count tracking per provider/model.

This does NOT replace the provider's own rate-limit error handling — it's
a pre-emptive check so the pipeline can skip straight to a fallback
provider instead of making a call that's very likely to fail with a 429,
when we already know (from local history) that we're near/at the daily
cap for a given provider+model today.

Counts reset naturally since they're scoped to calendar date (Pacific time,
matching Gemini's reset schedule — close enough for Groq's UTC-based reset
too, since this is a soft pre-check, not an authoritative limit).
"""

import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from contextlib import contextmanager


SCHEMA = """
CREATE TABLE IF NOT EXISTS provider_usage (
    provider_model TEXT NOT NULL,   -- e.g. "gemini:gemini-2.5-flash"
    usage_date TEXT NOT NULL,       -- YYYY-MM-DD (Pacific time, to roughly match Gemini's reset)
    call_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (provider_model, usage_date)
);
"""


def _pacific_today() -> str:
    # Approximate Pacific time without a tz database dependency: UTC-8.
    # Good enough for a soft daily-budget heuristic, not billing-grade.
    pacific_now = datetime.now(timezone.utc) - timedelta(hours=8)
    return pacific_now.strftime("%Y-%m-%d")


class ProviderUsageTracker:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def record_call(self, provider_model: str, n: int = 1):
        today = _pacific_today()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO provider_usage (provider_model, usage_date, call_count) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(provider_model, usage_date) DO UPDATE SET "
                "call_count = call_count + excluded.call_count",
                (provider_model, today, n),
            )

    def get_today_count(self, provider_model: str) -> int:
        today = _pacific_today()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT call_count FROM provider_usage WHERE provider_model = ? AND usage_date = ?",
                (provider_model, today),
            ).fetchone()
            return row["call_count"] if row else 0

    def is_near_daily_limit(self, provider_model: str, daily_limit: int, headroom: int = 1) -> bool:
        """
        Returns True if today's recorded usage is within `headroom` calls of
        `daily_limit`. Used to pre-emptively skip to a fallback provider
        rather than burn a call that's very likely to 429.
        """
        if daily_limit <= 0:
            return False  # no known limit configured — don't pre-emptively block
        return self.get_today_count(provider_model) >= (daily_limit - headroom)
