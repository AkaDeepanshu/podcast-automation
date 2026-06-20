"""
Stage 2: TTS synthesis.

Synthesizes each dialogue line individually (not the whole script in one
call) and tracks completion per-line in SQLite. This means a crash at line
180/250 resumes from line 180, not from zero — important at 30-min episode
length where a full run is hundreds of TTS calls.
"""

from pathlib import Path

from core.interfaces import TTSEngine, DialogueLine
from core.state_db import JobStateDB


def run_tts_stage(
    job_dir: Path,
    job_id: str,
    lines: list[DialogueLine],
    tts_engine: TTSEngine,
    speakers: dict,
    state_db: JobStateDB,
    log,
) -> list[dict]:
    """
    Synthesizes audio for every line in `lines`.

    Writes:
        job_dir/03_audio_lines/line_{index:04d}_{speaker}.wav

    Returns a list of dicts describing each line's audio result, in line
    order — used by the (not-yet-built) assembly stage.
    """
    audio_dir = job_dir / "03_audio_lines"
    audio_dir.mkdir(parents=True, exist_ok=True)

    already_done = state_db.get_completed_lines(job_id)
    if already_done:
        log.info(
            f"Resuming TTS stage: {len(already_done)}/{len(lines)} lines "
            f"already synthesized."
        )

    results = []
    failures = []

    for line in lines:
        voice_id = speakers[line.speaker]["voice_id"]
        output_filename = f"line_{line.line_index:04d}_{line.speaker}.wav"
        output_path = audio_dir / output_filename

        if line.line_index in already_done and output_path.exists():
            results.append({
                "line_index": line.line_index,
                "speaker": line.speaker,
                "audio_path": str(output_path),
                "success": True,
            })
            continue

        result = tts_engine.synthesize_line(
            line=line,
            voice_id=voice_id,
            output_path=str(output_path),
        )

        if result.success:
            state_db.set_line_status(
                job_id, line.line_index, "completed", audio_path=result.audio_path
            )
            results.append({
                "line_index": line.line_index,
                "speaker": line.speaker,
                "audio_path": result.audio_path,
                "duration_seconds": result.duration_seconds,
                "success": True,
            })
        else:
            state_db.set_line_status(
                job_id, line.line_index, "failed", error_msg=result.error
            )
            failures.append(line.line_index)
            results.append({
                "line_index": line.line_index,
                "speaker": line.speaker,
                "success": False,
                "error": result.error,
            })
            log.warning(f"  Line {line.line_index} ({line.speaker}) failed: {result.error}")

        if line.line_index % 20 == 0:
            log.info(f"  TTS progress: {line.line_index + 1}/{len(lines)} lines")

    log.info(
        f"TTS stage complete: {len(results) - len(failures)}/{len(lines)} succeeded, "
        f"{len(failures)} failed."
    )

    if failures:
        log.warning(
            f"Failed line indices: {failures}. These will produce gaps in the "
            f"assembled audio unless retried. Re-run the pipeline to retry "
            f"failed lines only."
        )

    return results
