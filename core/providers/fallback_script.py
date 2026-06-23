"""
Fallback script generator: wraps an ordered list of ScriptGenerator
providers and tries them in sequence.

Why this exists: free-tier LLM quotas (Gemini's especially) are tight
enough at 4-5 episodes/week that a single exhausted daily quota can block
an entire episode. Rather than just failing, this tries the next provider
in the chain.

Behavior:
- Tries providers in priority order for the FIRST call of a run.
- Once a provider succeeds, it's used for all subsequent calls in that run
  (keeps voice/style consistent across one episode's outline + segments;
  switching models mid-episode would make dialogue style shift partway
  through).
- If a provider fails with what looks like a quota/rate-limit error, moves
  to the next provider and STAYS on it for the rest of the run (no point
  retrying an exhausted daily quota mid-run).
- If a provider fails for a non-quota reason (e.g. malformed response), that
  provider's own internal retry logic handles it; only after it gives up
  entirely does the fallback chain advance.
- If every provider in the chain fails, raises the last error.
"""

from core.interfaces import ScriptGenerator, OutlineSegment, DialogueLine


class FallbackScriptGenerator(ScriptGenerator):
    def __init__(self, providers: list[tuple[str, ScriptGenerator]], log=None):
        """
        providers: ordered list of (name, ScriptGenerator instance) tuples,
                   tried in order. `name` is just for logging.
        """
        if not providers:
            raise ValueError("FallbackScriptGenerator requires at least one provider")
        self.providers = providers
        self.log = log
        self._active_index = 0  # sticks once a provider succeeds/is selected

    def _log(self, msg: str, level: str = "info"):
        if self.log:
            getattr(self.log, level)(msg)
        else:
            print(msg)

    def _call_with_fallback(self, method_name: str, *args, **kwargs):
        last_error = None
        start_index = self._active_index

        for i in range(start_index, len(self.providers)):
            name, provider = self.providers[i]
            try:
                if i != self._active_index:
                    self._log(f"  Falling back to provider: {name}", "warning")
                result = getattr(provider, method_name)(*args, **kwargs)
                if i != self._active_index:
                    self._log(f"  Fallback to {name} succeeded — staying on it "
                               f"for the rest of this run.", "info")
                self._active_index = i  # stick with this provider going forward
                return result
            except Exception as e:
                last_error = e
                self._log(f"  Provider '{name}' failed: {e}", "warning")
                if i + 1 < len(self.providers):
                    self._log(f"  Trying next provider in fallback chain...", "warning")

        raise RuntimeError(
            f"All {len(self.providers)} script generation provider(s) failed. "
            f"Last error: {last_error}"
        )

    def generate_outline(
        self,
        topic: str,
        num_segments: int,
        target_duration_minutes: float,
        speakers: dict,
    ) -> list[OutlineSegment]:
        return self._call_with_fallback(
            "generate_outline",
            topic=topic,
            num_segments=num_segments,
            target_duration_minutes=target_duration_minutes,
            speakers=speakers,
        )

    def generate_segment_script(
        self,
        topic: str,
        outline_segment: OutlineSegment,
        speakers: dict,
        previous_context: str,
        target_word_count: int,
    ) -> list[DialogueLine]:
        return self._call_with_fallback(
            "generate_segment_script",
            topic=topic,
            outline_segment=outline_segment,
            speakers=speakers,
            previous_context=previous_context,
            target_word_count=target_word_count,
        )
