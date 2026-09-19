#!/usr/bin/env python3
"""
Main pipeline entrypoint.

Stages: topic -> script (outline + dialogue) -> TTS audio per line
-> assembled, mastered episode audio -> video with subtitles + waveform.

Usage:
    python run_pipeline.py --topic "The history of mechanical keyboards"
    python run_pipeline.py --topic "..." --job-id my_custom_id
    python run_pipeline.py --resume my_custom_id
    python run_pipeline.py --topic "..." --skip-video   # audio only, skip video stage

Requires:
    GEMINI_API_KEY set in .env (copy .env.example to .env and fill it in)
    GROQ_API_KEY set in .env  (fallback, free at https://console.groq.com)
"""

import argparse
import json
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path

from core.config_loader import load_config, load_speakers, PROJECT_ROOT
from core.provider_factory import get_script_generator, get_tts_engine
from core.state_db import JobStateDB
from core.logging_setup import get_job_logger
from core.interfaces import DialogueLine
from core.pipeline.script_stage import run_script_stage
from core.pipeline.tts_stage import run_tts_stage
from core.pipeline.assembly_stage import run_assembly_stage
from core.pipeline.video_stage import run_video_stage


def slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].strip("-")


def make_job_id(topic: str) -> str:
    date_str = datetime.now().strftime("%Y%m%d")
    slug = slugify(topic)
    short_uuid = uuid.uuid4().hex[:6]
    return f"{date_str}_{slug}_{short_uuid}"


def run_job(
    topic: str,
    job_id: str,
    config: dict,
    speakers: dict,
    skip_video: bool = False,
    log_handlers: list | None = None,
):
    jobs_dir = PROJECT_ROOT / config["paths"]["jobs_dir"]
    job_dir = jobs_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    logs_dir = PROJECT_ROOT / config["paths"]["logs_dir"]
    log = get_job_logger(job_id, str(logs_dir), extra_handlers=log_handlers)

    state_db_path = PROJECT_ROOT / config["paths"]["state_db"]
    state_db = JobStateDB(str(state_db_path))

    log.info(f"=== Job {job_id} ===")
    log.info(f"Topic: {topic}")

    state_db.create_job(job_id, topic)
    state_db.set_job_status(job_id, "in_progress")

    try:
        # ---- Stage: Script generation ----
        if state_db.is_stage_completed(job_id, "script"):
            log.info("Stage [script] already completed, loading existing script.")
            with open(job_dir / "02_script.json") as f:
                lines = [DialogueLine.from_dict(d) for d in json.load(f)]
        else:
            state_db.set_stage_status(job_id, "script", "in_progress")
            try:
                script_generator = get_script_generator(config)
                lines = run_script_stage(
                    job_dir=job_dir,
                    topic=topic,
                    script_generator=script_generator,
                    speakers=speakers,
                    sg_config=config["script_generation"],
                    log=log,
                )
                state_db.set_stage_status(job_id, "script", "completed")
            except Exception as e:
                state_db.set_stage_status(job_id, "script", "failed", error_msg=str(e))
                raise

        # ---- Stage: TTS synthesis ----
        tts_results_path = job_dir / "03_tts_results.json"
        tts_had_failures = False

        if state_db.is_stage_completed(job_id, "tts"):
            log.info("Stage [tts] already completed, loading existing results.")
            with open(tts_results_path) as f:
                tts_results = json.load(f)
        else:
            state_db.set_stage_status(job_id, "tts", "in_progress")
            try:
                tts_engine = get_tts_engine(config)
                tts_results = run_tts_stage(
                    job_dir=job_dir,
                    job_id=job_id,
                    lines=lines,
                    tts_engine=tts_engine,
                    speakers=speakers,
                    state_db=state_db,
                    log=log,
                )
                with open(tts_results_path, "w") as f:
                    json.dump(tts_results, f, indent=2)

                failed = [r for r in tts_results if not r["success"]]
                if failed:
                    tts_had_failures = True
                    state_db.set_stage_status(
                        job_id, "tts", "failed",
                        error_msg=f"{len(failed)} line(s) failed synthesis"
                    )
                    log.error(
                        f"TTS stage finished with {len(failed)} failed line(s). "
                        f"Re-run with --resume {job_id} to retry just those lines."
                    )
                else:
                    state_db.set_stage_status(job_id, "tts", "completed")
            except Exception as e:
                state_db.set_stage_status(job_id, "tts", "failed", error_msg=str(e))
                raise

        # If we loaded an already-"failed"-but-present tts stage from a
        # prior partial run, reflect that in the job-level summary too.
        if state_db.get_stage_status(job_id, "tts") == "failed":
            tts_had_failures = True

        # ---- Stage: Audio assembly ----
        # Runs even if some TTS lines failed — produces a best-effort episode
        # with gaps noted, rather than blocking entirely on partial failures.
        #
        # Special case: if assembly previously completed but left gaps (per
        # its manifest) and TTS no longer has failures (i.e. this is a resume
        # after retrying failed lines), force a re-assembly so the
        # previously-missing lines get included rather than leaving stale
        # gaps in 04_final_audio.wav.
        assembly_manifest_path = job_dir / "04_assembly_manifest.json"
        assembly_previously_completed = state_db.is_stage_completed(job_id, "assembly")

        force_reassembly = False
        if assembly_previously_completed and not tts_had_failures and assembly_manifest_path.exists():
            with open(assembly_manifest_path) as f:
                prior_manifest = json.load(f)
            if prior_manifest.get("skipped_line_indices"):
                force_reassembly = True

        if assembly_previously_completed and not force_reassembly:
            log.info("Stage [assembly] already completed, skipping.")
        else:
            if force_reassembly:
                log.info(
                    "Re-running assembly: previous run had gaps and TTS "
                    "retries since then appear to have resolved them."
                )
            state_db.set_stage_status(job_id, "assembly", "in_progress")
            try:
                final_audio_path = run_assembly_stage(
                    job_dir=job_dir,
                    job_id=job_id,
                    lines=lines,
                    tts_results=tts_results,
                    assembly_config=config["tts"],
                    log=log,
                )
                state_db.set_stage_status(job_id, "assembly", "completed")
            except Exception as e:
                state_db.set_stage_status(job_id, "assembly", "failed", error_msg=str(e))
                raise

        # ---- Stage: Video generation ----
        if skip_video:
            log.info("Stage [video] skipped (--skip-video flag set).")
        elif state_db.is_stage_completed(job_id, "video"):
            log.info("Stage [video] already completed, skipping.")
        else:
            state_db.set_stage_status(job_id, "video", "in_progress")
            try:
                run_video_stage(
                    job_dir=job_dir,
                    lines=[l.to_dict() for l in lines],
                    tts_results=tts_results,
                    assembly_config=config["tts"],
                    video_config=config.get("video", {}),
                    log=log,
                    assets_dir=PROJECT_ROOT / config["paths"].get(
                        "assets_dir", "data/assets"
                    ),
                )
                state_db.set_stage_status(job_id, "video", "completed")
            except Exception as e:
                state_db.set_stage_status(job_id, "video", "failed", error_msg=str(e))
                raise

        if tts_had_failures:
            state_db.set_job_status(job_id, "completed_with_warnings")
            log.warning(
                f"=== Job {job_id} finished WITH WARNINGS === "
                f"Some TTS lines failed — final audio has gaps at those points. "
                f"See {tts_results_path} for which lines, or re-run "
                f"--resume {job_id} to retry failed lines and re-assemble."
            )
        else:
            state_db.set_job_status(job_id, "completed")
            log.info(f"=== Job {job_id} finished ===")

        log.info(f"Script:      {job_dir / '02_script.json'}")
        log.info(f"Audio lines: {job_dir / '03_audio_lines'}")
        log.info(f"Final audio: {job_dir / '04_final_audio.wav'}")
        if not skip_video:
            log.info(f"Video:       {job_dir / '05_video.mp4'}")

    except Exception as e:
        state_db.set_job_status(job_id, "failed")
        log.error(f"Job failed: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description="Podcast automation pipeline")
    parser.add_argument("--topic", type=str, help="Episode topic")
    parser.add_argument("--job-id", type=str, default=None,
                         help="Custom job ID (default: auto-generated from topic + date)")
    parser.add_argument("--resume", type=str, default=None,
                         help="Resume an existing job by ID (topic is read from state DB)")
    parser.add_argument("--skip-video", action="store_true",
                         help="Skip the video generation stage (produce audio only)")
    args = parser.parse_args()

    config = load_config()
    speakers = load_speakers()

    if args.resume:
        state_db_path = PROJECT_ROOT / config["paths"]["state_db"]
        state_db = JobStateDB(str(state_db_path))
        job = state_db.get_job(args.resume)
        if not job:
            print(f"No job found with id: {args.resume}")
            sys.exit(1)
        run_job(topic=job["topic"], job_id=args.resume, config=config,
                speakers=speakers, skip_video=args.skip_video)
        return

    if not args.topic:
        print("Error: --topic is required (or use --resume <job_id>)")
        sys.exit(1)

    job_id = args.job_id or make_job_id(args.topic)
    run_job(topic=args.topic, job_id=job_id, config=config,
            speakers=speakers, skip_video=args.skip_video)


if __name__ == "__main__":
    main()
