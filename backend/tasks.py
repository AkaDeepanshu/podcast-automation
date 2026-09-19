"""Celery tasks that run the podcast pipeline in the background."""

from backend.celery_app import celery_app
from core.config_loader import load_config, load_speakers
from run_pipeline import run_job


@celery_app.task(bind=True, name="backend.tasks.run_podcast_job")
def run_podcast_job(self, topic: str, job_id: str, skip_video: bool = False):
    """
    Async wrapper around run_pipeline.run_job.

    Config and speakers are loaded inside the worker so the API only needs
    to pass topic / job_id / flags — no large YAML payloads on the wire.
    """
    config = load_config()
    speakers = load_speakers()
    run_job(
        topic=topic,
        job_id=job_id,
        config=config,
        speakers=speakers,
        skip_video=skip_video,
    )
    return {"job_id": job_id, "status": "ok"}
