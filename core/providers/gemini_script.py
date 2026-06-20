"""
Gemini implementation of ScriptGenerator.

Uses the `google-genai` SDK with JSON-mode structured output so we never
have to regex-parse freeform text out of the model's response.

Requires env var: GEMINI_API_KEY
"""

import json
import os
import time

from google import genai
from google.genai import types

from core.interfaces import ScriptGenerator, OutlineSegment, DialogueLine


OUTLINE_SCHEMA = {
    "type": "object",
    "properties": {
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "segment_number": {"type": "integer"},
                    "theme": {"type": "string"},
                    "beats": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "target_minutes": {"type": "number"},
                },
                "required": ["segment_number", "theme", "beats", "target_minutes"],
            },
        }
    },
    "required": ["segments"],
}

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string", "enum": ["A", "B"]},
                    "text": {"type": "string"},
                    "emotion": {"type": "string"},
                },
                "required": ["speaker", "text"],
            },
        }
    },
    "required": ["lines"],
}


class GeminiScriptGenerator(ScriptGenerator):
    def __init__(self, model: str = "gemini-2.0-flash", temperature: float = 1.0,
                 max_output_tokens: int = 8192, api_key: str | None = None):
        api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY not set. Copy .env.example to .env and add "
                "your key, e.g.: cp .env.example .env"
            )
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

    # -------------------------------------------------------------------
    def _generate_json(self, prompt: str, schema: dict, max_retries: int = 3) -> dict:
        """Call Gemini with JSON-mode output, retrying on parse/API failure."""
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=self.temperature,
                        max_output_tokens=self.max_output_tokens,
                        response_mime_type="application/json",
                        response_schema=schema,
                    ),
                )
                return json.loads(response.text)
            except Exception as e:
                last_error = e
                wait = 2 ** attempt
                print(f"  [gemini] attempt {attempt}/{max_retries} failed: {e}. "
                      f"Retrying in {wait}s...")
                time.sleep(wait)
        raise RuntimeError(f"Gemini generation failed after {max_retries} attempts: {last_error}")

    # -------------------------------------------------------------------
    def generate_outline(
        self,
        topic: str,
        num_segments: int,
        target_duration_minutes: float,
        speakers: dict,
    ) -> list[OutlineSegment]:
        speaker_desc = "\n".join(
            f"- Speaker {key} ({info['name']}, {info['gender']}): {info['persona'].strip()}"
            for key, info in speakers.items()
        )
        minutes_per_segment = target_duration_minutes / num_segments

        prompt = f"""You are planning a {target_duration_minutes:.0f}-minute, two-person
conversational podcast episode on the topic: "{topic}"

Speakers:
{speaker_desc}

Create an outline of exactly {num_segments} segments, each covering a distinct
angle or sub-topic so the conversation progresses logically and doesn't repeat
itself. Each segment should target about {minutes_per_segment:.1f} minutes of
spoken dialogue.

For each segment provide:
- segment_number (1 to {num_segments}, in order)
- theme: a short label for what this segment covers
- beats: 3-5 specific talking points / questions / examples to hit in this segment
- target_minutes: the target duration for this segment

Make the progression feel natural: start with framing/context, build through
detail and differing perspectives, and end with synthesis or takeaways.
Avoid generic beats — be specific to the topic "{topic}"."""

        data = self._generate_json(prompt, OUTLINE_SCHEMA)
        segments = [OutlineSegment.from_dict(s) for s in data["segments"]]
        segments.sort(key=lambda s: s.segment_number)
        return segments

    # -------------------------------------------------------------------
    def generate_segment_script(
        self,
        topic: str,
        outline_segment: OutlineSegment,
        speakers: dict,
        previous_context: str,
        target_word_count: int,
    ) -> list[DialogueLine]:
        speaker_desc = "\n".join(
            f"- Speaker {key} ({info['name']}, {info['gender']}): {info['persona'].strip()}"
            for key, info in speakers.items()
        )
        beats_str = "\n".join(f"- {b}" for b in outline_segment.beats)

        continuity_block = ""
        if previous_context.strip():
            continuity_block = f"""
The conversation so far ended with:
\"\"\"
{previous_context.strip()}
\"\"\"
Continue naturally from this — do not reintroduce the topic or speakers,
just keep talking as if mid-conversation.
"""

        prompt = f"""Write one segment of dialogue for a two-person conversational
podcast on "{topic}".

Speakers:
{speaker_desc}
{continuity_block}
This segment's theme: {outline_segment.theme}
Talking points to cover (don't list them mechanically — weave them into
natural back-and-forth conversation):
{beats_str}

Requirements:
- Alternate speakers naturally (not strictly every line — people interrupt,
  add quick reactions, ask follow-ups)
- Target approximately {target_word_count} words of total spoken dialogue
  for this segment
- Sound like real spoken conversation: contractions, occasional incomplete
  sentences, natural reactions — NOT a scripted lecture
- AVOID overused filler phrases like "that's such a great point", "absolutely",
  "I couldn't agree more", "great question" — vary how speakers react and
  agree/disagree
- Do not include stage directions, sound effects, or narration — only
  spoken lines
- Each line should be a single speaker turn (don't combine both speakers
  in one entry)

Output the dialogue as a list of lines, each with the speaker key
("A" or "B"), the text, and optionally a one-word emotion hint
(e.g. "curious", "amused", "thoughtful")."""

        data = self._generate_json(prompt, SCRIPT_SCHEMA)
        lines = []
        for raw in data["lines"]:
            lines.append(DialogueLine(
                speaker=raw["speaker"],
                text=raw["text"].strip(),
                emotion=raw.get("emotion"),
                segment_index=outline_segment.segment_number,
            ))
        return lines