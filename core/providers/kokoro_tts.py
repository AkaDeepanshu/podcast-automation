"""
Kokoro implementation of TTSEngine.

Kokoro-82M is a free, local, open-weight TTS model. First run will download
weights from HuggingFace Hub (a few hundred MB) — needs internet access once,
then runs fully offline.

Install:
    pip install kokoro soundfile --break-system-packages
    # Kokoro also needs espeak-ng as a system dependency for non-English /
    # fallback phonemization:
    apt-get install -y espeak-ng

Voices reference (American/British English voice IDs):
    af_heart, af_bella, af_nicole, af_sarah   (female)
    am_michael, am_adam, am_fenrir            (male)
Full list: https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md
"""

import time

from core.interfaces import TTSEngine, DialogueLine, TTSResult


class KokoroTTSEngine(TTSEngine):
    def __init__(self, lang_code: str = "a", speed: float = 1.0, sample_rate: int = 24000):
        # Imported lazily so the rest of the codebase doesn't require torch
        # to be installed just to run script generation.
        from kokoro import KPipeline

        self.pipeline = KPipeline(lang_code=lang_code)
        self.speed = speed
        self.sample_rate = sample_rate

    def synthesize_line(
        self,
        line: DialogueLine,
        voice_id: str,
        output_path: str,
    ) -> TTSResult:
        import soundfile as sf
        import numpy as np

        text = line.text.strip()
        if not text:
            return TTSResult(
                line_index=line.line_index,
                audio_path="",
                duration_seconds=0.0,
                success=False,
                error="empty text",
            )

        try:
            audio_chunks = []
            for result in self.pipeline(text, voice=voice_id, speed=self.speed):
                if result.audio is not None:
                    audio_chunks.append(result.audio.numpy())

            if not audio_chunks:
                return TTSResult(
                    line_index=line.line_index,
                    audio_path="",
                    duration_seconds=0.0,
                    success=False,
                    error="no audio produced",
                )

            audio = np.concatenate(audio_chunks)
            sf.write(output_path, audio, self.sample_rate)
            duration = len(audio) / self.sample_rate

            return TTSResult(
                line_index=line.line_index,
                audio_path=output_path,
                duration_seconds=duration,
                success=True,
            )

        except Exception as e:
            return TTSResult(
                line_index=line.line_index,
                audio_path="",
                duration_seconds=0.0,
                success=False,
                error=str(e),
            )
