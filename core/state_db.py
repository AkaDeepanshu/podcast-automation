"""
Job/stage state tracking using SQLite.

Lets the pipeline resume from the last completed stage instead of
re-running everything after a crash — important at 4-5 episodes/week run
unattended via cron.
"""

import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | in_progress | completed | failed
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stages (
    job_id TEXT NOT NULL,
    stage_name TEXT NOT NULL,                 -- e.g. outline, script, tts
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | in_progress | completed | failed
    error_msg TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (job_id, stage_name),
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

CREATE TABLE IF NOT EXISTS tts_lines (
    job_id TEXT NOT NULL,
    line_index INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | completed | failed
    audio_path TEXT,
    error_msg TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (job_id, line_index)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStateDB:
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

    # -------------------------------------------------------------------
    # Job-level
    # -------------------------------------------------------------------
    def create_job(self, job_id: str, topic: str):
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO jobs (job_id, topic, status, created_at, updated_at) "
                "VALUES (?, ?, 'pending', ?, ?)",
                (job_id, topic, _now(), _now()),
            )

    def set_job_status(self, job_id: str, status: str):
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status = ?, updated_at = ? WHERE job_id = ?",
                (status, _now(), job_id),
            )

    def get_job(self, job_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            return dict(row) if row else None

    def find_in_progress_jobs(self) -> list[dict]:
        """Useful at startup to detect crashed/orphaned jobs before starting a new one."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status = 'in_progress'"
            ).fetchall()
            return [dict(r) for r in rows]

    # -------------------------------------------------------------------
    # Stage-level
    # -------------------------------------------------------------------
    def set_stage_status(self, job_id: str, stage_name: str, status: str, error_msg: str = None):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO stages (job_id, stage_name, status, error_msg, updated_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(job_id, stage_name) DO UPDATE SET "
                "status=excluded.status, error_msg=excluded.error_msg, updated_at=excluded.updated_at",
                (job_id, stage_name, status, error_msg, _now()),
            )

    def get_stage_status(self, job_id: str, stage_name: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT status FROM stages WHERE job_id = ? AND stage_name = ?",
                (job_id, stage_name),
            ).fetchone()
            return row["status"] if row else None

    def is_stage_completed(self, job_id: str, stage_name: str) -> bool:
        return self.get_stage_status(job_id, stage_name) == "completed"

    def get_all_stages(self, job_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM stages WHERE job_id = ? ORDER BY updated_at",
                (job_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # -------------------------------------------------------------------
    # Per-line TTS tracking (fine-grained resumability within the TTS stage)
    # -------------------------------------------------------------------
    def set_line_status(self, job_id: str, line_index: int, status: str,
                          audio_path: str = None, error_msg: str = None):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO tts_lines (job_id, line_index, status, audio_path, error_msg, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(job_id, line_index) DO UPDATE SET "
                "status=excluded.status, audio_path=excluded.audio_path, "
                "error_msg=excluded.error_msg, updated_at=excluded.updated_at",
                (job_id, line_index, status, audio_path, error_msg, _now()),
            )

    def get_completed_lines(self, job_id: str) -> set:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT line_index FROM tts_lines WHERE job_id = ? AND status = 'completed'",
                (job_id,),
            ).fetchall()
            return {r["line_index"] for r in rows}

    def get_failed_lines(self, job_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tts_lines WHERE job_id = ? AND status = 'failed'",
                (job_id,),
            ).fetchall()
            return [dict(r) for r in rows]
