"""
Stage 1: Script generation.

Orchestrates: outline generation -> chunked segment-by-segment dialogue
generation -> writes the full structured script to disk.

This stage owns the anti-repetition strategy: generating in chunks with
only a short rolling context window (not the whole growing script) keeps
prompts small and avoids the model settling into repetitive rhythms that
single-shot 30-min generation tends to produce.
"""

import json
from pathlib import Path

from core.interfaces import ScriptGenerator, DialogueLine, OutlineSegment


def _last_n_words(lines: list[DialogueLine], n_lines: int = 6) -> str:
    """Build a short continuity snippet from the tail of the previous segment."""
    tail = lines[-n_lines:] if len(lines) > n_lines else lines
    return "\n".join(f"{l.speaker}: {l.text}" for l in tail)


def _contains_forbidden_phrase(text: str, forbidden_phrases: list[str]) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in forbidden_phrases)


def run_script_stage(
    job_dir: Path,
    topic: str,
    script_generator: ScriptGenerator,
    speakers: dict,
    sg_config: dict,
    log,
) -> list[DialogueLine]:
    """
    Runs the full script generation stage for a job.

    Writes:
        job_dir/01_outline.json
        job_dir/02_script.json

    Returns the full list of DialogueLine for the episode.
    """
    outline_path = job_dir / "01_outline.json"
    script_path = job_dir / "02_script.json"

    # ---- Outline (skip if already generated — resumability) ----
    if outline_path.exists():
        log.info("Outline already exists, loading from disk.")
        with open(outline_path) as f:
            outline_data = json.load(f)
        outline = [OutlineSegment.from_dict(s) for s in outline_data]
    else:
        log.info(f"Generating outline for topic: {topic!r}")
        outline = script_generator.generate_outline(
            topic=topic,
            num_segments=sg_config["num_segments"],
            target_duration_minutes=sg_config["target_duration_minutes"],
            speakers=speakers,
        )
        with open(outline_path, "w") as f:
            json.dump([s.to_dict() for s in outline], f, indent=2)
        log.info(f"Outline written: {len(outline)} segments -> {outline_path}")

    # ---- Chunked script generation (skip if already generated) ----
    if script_path.exists():
        log.info("Script already exists, loading from disk.")
        with open(script_path) as f:
            script_data = json.load(f)
        return [DialogueLine.from_dict(d) for d in script_data]

    words_per_minute = sg_config["words_per_minute"]
    forbidden_phrases = sg_config.get("forbidden_phrases", [])
    max_retries = sg_config.get("max_retries_per_segment", 3)

    all_lines: list[DialogueLine] = []
    global_line_index = 0

    for segment in outline:
        target_word_count = int(segment.target_minutes * words_per_minute)
        previous_context = _last_n_words(all_lines) if all_lines else ""

        log.info(
            f"Generating segment {segment.segment_number}/{len(outline)} "
            f"({segment.theme!r}, ~{target_word_count} words)..."
        )

        segment_lines = None
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                candidate = script_generator.generate_segment_script(
                    topic=topic,
                    outline_segment=segment,
                    speakers=speakers,
                    previous_context=previous_context,
                    target_word_count=target_word_count,
                )
                if not candidate:
                    raise ValueError("model returned zero lines")

                # Quality check: flag (not hard-fail on) forbidden filler phrases
                flagged = [
                    l for l in candidate
                    if _contains_forbidden_phrase(l.text, forbidden_phrases)
                ]
                if flagged and attempt < max_retries:
                    log.warning(
                        f"  Segment {segment.segment_number} contains "
                        f"{len(flagged)} overused filler phrase(s), regenerating "
                        f"(attempt {attempt}/{max_retries})..."
                    )
                    last_error = "forbidden phrases present"
                    continue

                segment_lines = candidate
                break

            except Exception as e:
                last_error = str(e)
                log.warning(
                    f"  Segment {segment.segment_number} generation failed "
                    f"(attempt {attempt}/{max_retries}): {e}"
                )

        if segment_lines is None:
            raise RuntimeError(
                f"Failed to generate segment {segment.segment_number} "
                f"after {max_retries} attempts: {last_error}"
            )

        # Assign global line indices now that we know ordering
        for line in segment_lines:
            line.line_index = global_line_index
            global_line_index += 1
            all_lines.append(line)

        log.info(
            f"  Segment {segment.segment_number} done: {len(segment_lines)} lines."
        )

        # Write incrementally — if a later segment fails, you don't lose
        # the segments that already succeeded.
        with open(script_path, "w") as f:
            json.dump([l.to_dict() for l in all_lines], f, indent=2)

    total_words = sum(len(l.text.split()) for l in all_lines)
    estimated_minutes = total_words / words_per_minute
    log.info(
        f"Script generation complete: {len(all_lines)} lines, "
        f"~{total_words} words, ~{estimated_minutes:.1f} min estimated runtime."
    )

    return all_lines
