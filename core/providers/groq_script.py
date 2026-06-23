"""
Groq implementation of ScriptGenerator.

Groq runs open-weight models (Llama, etc.) on custom LPU hardware and offers
a free tier with no credit card required. Its free-tier daily request limits
are typically much higher than Gemini's (hundreds to low-thousands RPD vs.
tens of RPD), which makes it a strong fallback when Gemini's free quota is
exhausted -- at the cost of somewhat lower dialogue quality from the
open-weight model vs. Gemini's.

Uses Structured Outputs (response_format={"type": "json_schema", ...}) for
the same reliable JSON parsing guarantee as the Gemini provider.

Requires env var: GROQ_API_KEY (free, no card, from https://console.groq.com)
"""

import json
import os
import time

from groq import Groq, RateLimitError, APIStatusError

from core.interfaces import ScriptGenerator, OutlineSegment, DialogueLine


OUTLINE_JSON_SCHEMA = {
    "name": "podcast_outline",
    "schema": {
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
                    "additionalProperties": False,
                },
            }
        },
        "required": ["segments"],
        "additionalProperties": False,
    },
}

SCRIPT_JSON_SCHEMA = {
    "name": "podcast_script_segment",
    "schema": {
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
                    "required": ["speaker", "text", "emotion"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["lines"],
        "additionalProperties": False,
    },
}


class GroqScriptGenerator(ScriptGenerator):
    def __init__(self, model: str = "llama-3.3-70b-versatile", temperature: float = 1.0,
                 max_output_tokens: int = 8192, api_key: str | None = None,
                 usage_tracker=None, daily_limit: int = 0):
        api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY not set. Get a free key (no card required) at "
                "https://console.groq.com/keys and add it to .env"
            )
        self.client = Groq(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.usage_tracker = usage_tracker
        self.daily_limit = daily_limit
        self._usage_key = f"groq:{model}"

    # -------------------------------------------------------------------
    def _generate_json(self, prompt: str, json_schema: dict, max_retries: int = 3) -> dict:
        if self.usage_tracker and self.daily_limit > 0:
            if self.usage_tracker.is_near_daily_limit(self._usage_key, self.daily_limit):
                raise RuntimeError(
                    f"Groq model '{self.model}' is at/near its tracked daily "
                    f"limit ({self.usage_tracker.get_today_count(self._usage_key)}"
                    f"/{self.daily_limit} calls today, per local tracking) — "
                    f"skipping call to avoid a near-certain 429."
                )

        # Ensure the word "json" appears in the prompt — required by Groq when
        # using response_format=json_object. Also helps steer open-weight models.
        augmented_prompt = prompt
        if "json" not in prompt.lower():
            augmented_prompt = prompt + "\n\nRespond with a valid JSON object only."

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                # Prefer json_schema (Structured Outputs) — more reliable and
                # does NOT require the word "json" in the prompt.
                # Falls back to json_object if the model doesn't support it.
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": augmented_prompt}],
                        temperature=self.temperature,
                        max_tokens=self.max_output_tokens,
                        response_format={
                            "type": "json_schema",
                            "json_schema": {
                                "name": json_schema["name"],
                                "strict": False,  # strict=True is more limiting on llama models
                                "schema": json_schema["schema"],
                            },
                        },
                    )
                except APIStatusError as schema_err:
                    # Model doesn't support json_schema — fall back to json_object
                    if schema_err.status_code in (400, 422):
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=[{"role": "user", "content": augmented_prompt}],
                            temperature=self.temperature,
                            max_tokens=self.max_output_tokens,
                            response_format={"type": "json_object"},
                        )
                    else:
                        raise

                if self.usage_tracker:
                    self.usage_tracker.record_call(self._usage_key)
                return json.loads(response.choices[0].message.content)

            except RateLimitError as e:
                if self.usage_tracker:
                    self.usage_tracker.record_call(self._usage_key)
                raise RuntimeError(
                    f"Groq model '{self.model}' hit a rate limit: {e}. "
                    f"Check current limits at https://console.groq.com/settings/limits"
                ) from e

            except APIStatusError as e:
                last_error = e
                wait = 2 ** attempt
                print(f"  [groq] attempt {attempt}/{max_retries} failed "
                    f"(status {e.status_code}): {e}. Retrying in {wait}s...")
                time.sleep(wait)

            except Exception as e:
                last_error = e
                wait = 2 ** attempt
                print(f"  [groq] attempt {attempt}/{max_retries} failed: {e}. "
                    f"Retrying in {wait}s...")
                time.sleep(wait)

        raise RuntimeError(f"Groq generation failed after {max_retries} attempts: {last_error}")
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

        data = self._generate_json(prompt, OUTLINE_JSON_SCHEMA)
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

For each line, give the speaker key ("A" or "B"), the text, and an emotion
hint (one word, e.g. "curious", "amused", "thoughtful" — use "neutral" if
nothing specific applies)."""

        data = self._generate_json(prompt, SCRIPT_JSON_SCHEMA)
        lines = []
        for raw in data["lines"]:
            lines.append(DialogueLine(
                speaker=raw["speaker"],
                text=raw["text"].strip(),
                emotion=raw.get("emotion"),
                segment_index=outline_segment.segment_number,
            ))
        return lines
