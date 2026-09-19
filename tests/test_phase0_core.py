"""Phase 0 unit checks: episode overrides + orphan cleanup."""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.episode_overrides import EpisodeOverrides, apply_episode_overrides
from core.state_db import JobStateDB


class EpisodeOverridesTests(unittest.TestCase):
    def test_merge_duration_segments_model_and_skip(self):
        config = {
            "providers": {"script_generator": "fallback_chain"},
            "script_generation": {
                "target_duration_minutes": 30,
                "num_segments": 6,
                "gemini": {"model": "gemini-2.5-flash"},
            },
        }
        ep = EpisodeOverrides(
            target_duration_minutes=10,
            num_segments=2,
            model="gemini-2.5-flash-lite",
            skip_video=True,
        )
        merged, skip = apply_episode_overrides(config, ep, skip_video=False)
        self.assertTrue(skip)
        self.assertEqual(merged["script_generation"]["target_duration_minutes"], 10)
        self.assertEqual(merged["script_generation"]["num_segments"], 2)
        self.assertEqual(
            merged["script_generation"]["gemini"]["model"],
            "gemini-2.5-flash-lite",
        )
        # Original untouched
        self.assertEqual(config["script_generation"]["num_segments"], 6)

    def test_model_not_applied_for_groq_only(self):
        config = {
            "providers": {"script_generator": "groq"},
            "script_generation": {
                "gemini": {"model": "gemini-2.5-flash"},
                "groq": {"model": "openai/gpt-oss-20b"},
            },
        }
        ep = EpisodeOverrides(None, None, "gemini-2.5-flash-lite", False)
        merged, skip = apply_episode_overrides(config, ep, skip_video=True)
        self.assertFalse(skip)
        self.assertEqual(
            merged["script_generation"]["gemini"]["model"],
            "gemini-2.5-flash",
        )

    def test_no_row_keeps_task_skip_video(self):
        config = {"script_generation": {"num_segments": 6}}
        merged, skip = apply_episode_overrides(config, None, skip_video=True)
        self.assertTrue(skip)
        self.assertEqual(merged["script_generation"]["num_segments"], 6)


class OrphanCleanupTests(unittest.TestCase):
    def test_marks_stale_in_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "jobs.db")
            db = JobStateDB(db_path)
            stale = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
            fresh = datetime.now(timezone.utc).isoformat()

            db.create_job("stale-job", "Stale topic")
            db.set_job_status("stale-job", "in_progress")
            db.set_stage_status("stale-job", "script", "in_progress")
            # Backdate timestamps
            import sqlite3

            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    "UPDATE jobs SET updated_at = ? WHERE job_id = ?",
                    (stale, "stale-job"),
                )
                conn.execute(
                    "UPDATE stages SET updated_at = ? WHERE job_id = ?",
                    (stale, "stale-job"),
                )
                conn.commit()

            db.create_job("fresh-job", "Fresh topic")
            db.set_job_status("fresh-job", "in_progress")
            db.set_stage_status("fresh-job", "tts", "in_progress")
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    "UPDATE jobs SET updated_at = ? WHERE job_id = ?",
                    (fresh, "fresh-job"),
                )
                conn.execute(
                    "UPDATE stages SET updated_at = ? WHERE job_id = ?",
                    (fresh, "fresh-job"),
                )
                conn.commit()

            marked = db.mark_orphaned_in_progress_jobs(grace_minutes=10)
            self.assertEqual(marked, ["stale-job"])
            self.assertEqual(db.get_job("stale-job")["status"], "failed")
            self.assertEqual(db.get_job("fresh-job")["status"], "in_progress")
            self.assertEqual(db.get_stage_status("stale-job", "script"), "failed")


if __name__ == "__main__":
    unittest.main()
