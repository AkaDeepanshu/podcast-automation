"""
Core interfaces for the podcast automation pipeline.

Every provider (Gemini, Claude, Kokoro, ElevenLabs, ...) implements one of
these two interfaces. The pipeline code only ever talks to these abstract
classes — never to a specific provider directly. This is what lets you swap
free -> paid later by changing one line in config.yaml instead of rewriting
pipeline code.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


# -----------------------------------------------------------------------------
# Shared data structures
# -----------------------------------------------------------------------------

@dataclass
class DialogueLine:
    """A single line of dialogue spoken by one speaker."""
    speaker: str                  # speaker key, e.g. "A" or "B" (maps to speakers.yaml)
    text: str                     # the actual spoken text
    emotion: Optional[str] = None  # optional style hint, e.g. "curious", "amused"
    segment_index: int = 0        # which script segment this line belongs to
    line_index: int = 0           # global line index across the whole script

    def to_dict(self) -> dict:
        return {
            "speaker": self.speaker,
            "text": self.text,
            "emotion": self.emotion,
            "segment_index": self.segment_index,
            "line_index": self.line_index,
        }

    @staticmethod
    def from_dict(d: dict) -> "DialogueLine":
        return DialogueLine(
            speaker=d["speaker"],
            text=d["text"],
            emotion=d.get("emotion"),
            segment_index=d.get("segment_index", 0),
            line_index=d.get("line_index", 0),
        )


@dataclass
class OutlineSegment:
    """One segment of the episode outline (used to drive chunked generation)."""
    segment_number: int
    theme: str
    beats: list = field(default_factory=list)   # list[str] of talking points
    target_minutes: float = 5.0

    def to_dict(self) -> dict:
        return {
            "segment_number": self.segment_number,
            "theme": self.theme,
            "beats": self.beats,
            "target_minutes": self.target_minutes,
        }

    @staticmethod
    def from_dict(d: dict) -> "OutlineSegment":
        return OutlineSegment(
            segment_number=d["segment_number"],
            theme=d["theme"],
            beats=d.get("beats", []),
            target_minutes=d.get("target_minutes", 5.0),
        )


@dataclass
class TTSResult:
    """Result of synthesizing a single line of dialogue."""
    line_index: int
    audio_path: str
    duration_seconds: float
    success: bool
    error: Optional[str] = None


# -----------------------------------------------------------------------------
# Script generator interface
# -----------------------------------------------------------------------------

class ScriptGenerator(ABC):
    """
    Abstract interface for any LLM-backed script generation provider.

    Implementations: GeminiScriptGenerator (Phase 1), ClaudeScriptGenerator
    / OpenAIScriptGenerator (Phase 2, paid).
    """

    @abstractmethod
    def generate_outline(
        self,
        topic: str,
        num_segments: int,
        target_duration_minutes: float,
        speakers: dict,
    ) -> list[OutlineSegment]:
        """Produce a structured outline of `num_segments` segments for the topic."""
        raise NotImplementedError

    @abstractmethod
    def generate_segment_script(
        self,
        topic: str,
        outline_segment: OutlineSegment,
        speakers: dict,
        previous_context: str,
        target_word_count: int,
    ) -> list[DialogueLine]:
        """
        Generate dialogue lines for a single outline segment.

        `previous_context` is a short summary / last few lines of the prior
        segment — used to keep continuity without feeding the entire
        growing script back into the prompt every time.
        """
        raise NotImplementedError


# -----------------------------------------------------------------------------
# TTS engine interface
# -----------------------------------------------------------------------------

class TTSEngine(ABC):
    """
    Abstract interface for any TTS provider.

    Implementations: KokoroTTSEngine (Phase 1, free/local),
    ElevenLabsTTSEngine (Phase 2, paid).
    """

    @abstractmethod
    def synthesize_line(
        self,
        line: DialogueLine,
        voice_id: str,
        output_path: str,
    ) -> TTSResult:
        """Synthesize a single dialogue line to a .wav file at output_path."""
        raise NotImplementedError
