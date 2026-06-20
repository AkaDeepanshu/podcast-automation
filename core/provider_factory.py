"""
Provider factory — reads config.yaml and instantiates the active
ScriptGenerator / TTSEngine implementation.

This is the ONLY place in the codebase that knows about concrete provider
classes. Pipeline code calls get_script_generator() / get_tts_engine() and
never imports GeminiScriptGenerator or KokoroTTSEngine directly.
"""

from core.interfaces import ScriptGenerator, TTSEngine


def get_script_generator(config: dict) -> ScriptGenerator:
    provider_name = config["providers"]["script_generator"]
    sg_config = config["script_generation"]

    if provider_name == "gemini":
        from core.providers.gemini_script import GeminiScriptGenerator
        gemini_cfg = sg_config["gemini"]
        return GeminiScriptGenerator(
            model=gemini_cfg["model"],
            temperature=gemini_cfg["temperature"],
            max_output_tokens=gemini_cfg["max_output_tokens"],
        )

    # Phase 2 stub:
    # elif provider_name == "claude":
    #     from core.providers.claude_script import ClaudeScriptGenerator
    #     return ClaudeScriptGenerator(...)

    raise ValueError(f"Unknown script_generator provider: {provider_name}")


def get_tts_engine(config: dict) -> TTSEngine:
    provider_name = config["providers"]["tts_engine"]
    tts_config = config["tts"]

    if provider_name == "kokoro":
        from core.providers.kokoro_tts import KokoroTTSEngine
        kokoro_cfg = tts_config["kokoro"]
        return KokoroTTSEngine(
            lang_code=kokoro_cfg["lang_code"],
            speed=kokoro_cfg["speed"],
            sample_rate=kokoro_cfg["sample_rate"],
        )

    # Phase 2 stub:
    # elif provider_name == "elevenlabs":
    #     from core.providers.elevenlabs_tts import ElevenLabsTTSEngine
    #     return ElevenLabsTTSEngine(...)

    raise ValueError(f"Unknown tts_engine provider: {provider_name}")
