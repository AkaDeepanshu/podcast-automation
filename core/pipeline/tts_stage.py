"""
Stage 2: TTS synthesis.

Synthesizes each dialogue line individually (not the whole script in one
call) and tracks completion per-line in SQLite. This means a crash at line
180/250 resumes from line 180, not from zero — important at 30-min episode
length where a full run is hundreds of TTS calls.
"""

import re
from pathlib import Path

from core.interfaces import TTSEngine, DialogueLine
from core.state_db import JobStateDB


def sanitize_for_tts(text: str) -> str:
    """
    Strips markdown emphasis/formatting artifacts that LLMs sometimes add
    for written-text emphasis (*word*, _word_, **word**) but that a TTS
    engine has no concept of — it just reads the literal symbol characters
    out loud (e.g. "*focused*" becomes "asterisk focused asterisk").

    This is a backstop: the generation prompt already asks the model not
    to use markdown, but LLMs don't follow every instruction every time,
    so this catches what slips through before it ever reaches the TTS
    engine. Applied only at synthesis time — the original script JSON is
    left untouched as the model actually wrote it.
    """
    # Bold/italic markers: **word**, *word*, __word__, _word_
    # Applied narrowest-first so **word** doesn't leave stray single * behind.
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"\b_(.+?)_\b", r"\1", text)

    # Markdown headers / bullet markers occasionally leaking into dialogue
    text = re.sub(r"^#+\s*", "", text)
    text = re.sub(r"^[-•]\s*", "", text)

    # Collapse any double-spacing left behind by the above substitutions
    text = re.sub(r"\s{2,}", " ", text).strip()

    return text


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

        # Synthesize a sanitized copy of the line, not the original object
        # in place — keeps 02_script.json as the model actually wrote it.
        sanitized_text = sanitize_for_tts(line.text)
        if sanitized_text != line.text:
            log.info(
                f"  Line {line.line_index}: stripped markdown artifacts "
                f"before synthesis (original text unchanged in script file)."
            )
        line_for_tts = DialogueLine(
            speaker=line.speaker,
            text=sanitized_text,
            emotion=line.emotion,
            segment_index=line.segment_index,
            line_index=line.line_index,
        )

        result = tts_engine.synthesize_line(
            line=line_for_tts,
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
