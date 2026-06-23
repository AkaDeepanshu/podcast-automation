"""
Stage 3: Audio assembly.

Takes the per-line .wav files produced by the TTS stage and combines them
into one continuous episode file:
    1. Per-line loudness normalization (TTS calls vary in volume/energy —
       this stage makes them consistent before stitching)
    2. Pause insertion (shorter between turns, longer between segments —
       this is what makes it sound like a conversation, not a wall of audio)
    3. Concatenation in line order
    4. Final mastering pass (overall loudness target + peak limiting)

Skips/handles missing or failed lines gracefully (logs a gap rather than
crashing the whole assembly) — a job should still produce a usable file
even if 2 out of 250 lines failed TTS and weren't retried yet.
"""

import json
from pathlib import Path

import numpy as np
import soundfile as sf
import pyloudnorm as pyln
from pydub import AudioSegment

from core.interfaces import DialogueLine


# LUFS target for per-line normalization before stitching. -20 LUFS is a
# reasonable conversational-podcast target (commercial loudness norms like
# Spotify/YouTube sit around -14 to -16 LUFS, but we normalize lines to a
# slightly quieter common level first, then do a final master pass at the
# end to bring the whole episode to target).
PER_LINE_TARGET_LUFS = -20.0
FINAL_MASTER_TARGET_LUFS = -16.0

# Minimum audio length (seconds) for reliable LUFS measurement. Below this,
# pyloudnorm's block-based ITU-R BS.1770 algorithm can't measure reliably,
# so we skip normalization and just use the raw line (rare — usually only
# single-word interjections).
MIN_DURATION_FOR_LUFS_SECONDS = 0.5


def _normalize_line_audio(audio_path: str, target_lufs: float = PER_LINE_TARGET_LUFS) -> AudioSegment:
    """
    Load a line's wav, loudness-normalize it, return as an AudioSegment
    ready for concatenation. Falls back to the raw (unnormalized) audio if
    the clip is too short/silent to measure reliably, rather than crashing
    the whole assembly over one short interjection.
    """
    data, rate = sf.read(audio_path)
    duration = len(data) / rate

    if duration < MIN_DURATION_FOR_LUFS_SECONDS:
        normalized = data
    else:
        meter = pyln.Meter(rate)
        loudness = meter.integrated_loudness(data)
        if loudness == float("-inf"):
            # essentially silent clip — nothing to normalize, leave as-is
            normalized = data
        else:
            normalized = pyln.normalize.loudness(data, loudness, target_lufs)
            # guard against clipping from normalization gain on quiet clips
            peak = np.max(np.abs(normalized)) if len(normalized) else 0.0
            if peak > 0.99:
                normalized = normalized / peak * 0.99

    # Write to a temp buffer pydub can read, preserving sample rate
    tmp_path = audio_path + ".norm.wav"
    sf.write(tmp_path, normalized, rate)
    segment = AudioSegment.from_wav(tmp_path)
    Path(tmp_path).unlink(missing_ok=True)
    return segment


def _master_final_audio(combined: AudioSegment, target_lufs: float = FINAL_MASTER_TARGET_LUFS) -> AudioSegment:
    """Final loudness pass on the fully assembled episode."""
    samples = np.array(combined.get_array_of_samples()).astype(np.float64)
    if combined.channels == 2:
        samples = samples.reshape((-1, 2))
    samples /= float(1 << (8 * combined.sample_width - 1))  # normalize int range to [-1, 1]

    meter = pyln.Meter(combined.frame_rate)
    loudness = meter.integrated_loudness(samples)
    if loudness == float("-inf"):
        return combined

    mastered = pyln.normalize.loudness(samples, loudness, target_lufs)
    peak = np.max(np.abs(mastered)) if mastered.size else 0.0
    if peak > 0.99:
        mastered = mastered / peak * 0.99

    mastered_int = (mastered * (1 << (8 * combined.sample_width - 1))).astype(
        np.int16 if combined.sample_width == 2 else np.int32
    )

    return AudioSegment(
        mastered_int.tobytes(),
        frame_rate=combined.frame_rate,
        sample_width=combined.sample_width,
        channels=combined.channels,
    )


def run_assembly_stage(
    job_dir: Path,
    job_id: str,
    lines: list[DialogueLine],
    tts_results: list[dict],
    assembly_config: dict,
    log,
) -> Path:
    """
    Assembles all successfully-synthesized lines into one episode audio
    file.

    Writes:
        job_dir/04_final_audio.wav

    Returns the path to the final audio file.
    """
    output_path = job_dir / "04_final_audio.wav"

    pause_between_turns_ms = assembly_config.get("pause_between_turns_ms", 400)
    pause_between_segments_ms = assembly_config.get("pause_between_segments_ms", 900)

    # Map line_index -> result for quick lookup, only keep successes
    result_by_index = {r["line_index"]: r for r in tts_results}

    combined = AudioSegment.empty()
    skipped = []
    prev_segment_index = None
    total_lines = len(lines)

    for i, line in enumerate(lines):
        result = result_by_index.get(line.line_index)
        if not result or not result.get("success") or not Path(result.get("audio_path", "")).exists():
            skipped.append(line.line_index)
            log.warning(
                f"  Line {line.line_index} ({line.speaker}) has no usable audio "
                f"— skipping in assembly (gap left in conversation flow)."
            )
            continue

        # Pause logic: longer pause at segment boundaries, normal pause between turns
        if combined.duration_seconds > 0:
            if prev_segment_index is not None and line.segment_index != prev_segment_index:
                combined += AudioSegment.silent(
                    duration=pause_between_segments_ms, frame_rate=combined.frame_rate or 24000
                )
            else:
                combined += AudioSegment.silent(
                    duration=pause_between_turns_ms, frame_rate=combined.frame_rate or 24000
                )

        line_audio = _normalize_line_audio(result["audio_path"])
        combined += line_audio
        prev_segment_index = line.segment_index

        if i % 30 == 0:
            log.info(f"  Assembly progress: {i + 1}/{total_lines} lines stitched")

    if combined.duration_seconds == 0:
        raise RuntimeError(
            "Assembly produced zero audio — no lines had usable TTS output. "
            "Check the TTS stage results before re-running assembly."
        )

    log.info(
        f"Stitching complete: {total_lines - len(skipped)}/{total_lines} lines used, "
        f"raw duration {combined.duration_seconds:.1f}s. Applying final mastering pass..."
    )

    mastered = _master_final_audio(combined)
    mastered.export(str(output_path), format="wav")

    log.info(
        f"Assembly stage complete: {output_path} "
        f"({mastered.duration_seconds:.1f}s / {mastered.duration_seconds / 60:.1f} min)"
    )

    if skipped:
        log.warning(
            f"{len(skipped)} line(s) were skipped due to missing/failed audio: {skipped}. "
            f"Episode has gaps at those points. Retry TTS for those lines and re-run "
            f"assembly to fill them in."
        )

    # Write a small manifest noting what went into this assembly, useful
    # for debugging gaps later without re-deriving it from the state DB.
    manifest_path = job_dir / "04_assembly_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump({
            "total_lines": total_lines,
            "lines_used": total_lines - len(skipped),
            "skipped_line_indices": skipped,
            "final_duration_seconds": mastered.duration_seconds,
        }, f, indent=2)

    return output_path
