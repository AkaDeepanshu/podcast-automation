"""Build payloads and emit job lifecycle notifications."""

from __future__ import annotations

from backend.notify import emit
from core.config_loader import PROJECT_ROOT, load_config
from core.state_db import JobStateDB


def _failed_stage(state: JobStateDB, job_id: str) -> tuple[str | None, str | None]:
    stages = state.get_all_stages(job_id)
    for stage in reversed(stages):
        if stage.get("status") == "failed":
            return stage.get("stage_name"), stage.get("error_msg")
    return None, None


def notify_job_started(
    job_id: str,
    topic: str,
    *,
    source: str = "manual",
) -> None:
    emit(
        "episode_started",
        {"job_id": job_id, "topic": topic, "source": source},
    )


def notify_job_finished(job_id: str, topic: str, *, error: str | None = None) -> None:
    """Emit episode_completed or episode_failed after topic sync."""
    config = load_config()
    state = JobStateDB(str(PROJECT_ROOT / config["paths"]["state_db"]))
    job = state.get_job(job_id)
    status = (job or {}).get("status")

    if status in ("completed", "completed_with_warnings"):
        jobs_dir = PROJECT_ROOT / config["paths"]["jobs_dir"]
        audio_path = jobs_dir / job_id / "04_final_audio.wav"
        emit(
            "episode_completed",
            {
                "job_id": job_id,
                "topic": topic,
                "status": status,
                "audio_hint": str(audio_path) if audio_path.exists() else f"/episodes/{job_id}",
            },
        )
        return

    if status == "failed" or error:
        stage, stage_err = _failed_stage(state, job_id)
        emit(
            "episode_failed",
            {
                "job_id": job_id,
                "topic": topic,
                "stage": stage or "unknown",
                "error": error or stage_err or "job_failed",
            },
        )
