"""
Provider factory — reads config.yaml and instantiates the active
ScriptGenerator / TTSEngine implementation.

This is the ONLY place in the codebase that knows about concrete provider
classes. Pipeline code calls get_script_generator() / get_tts_engine() and
never imports GeminiScriptGenerator or KokoroTTSEngine directly.
"""

from core.interfaces import ScriptGenerator, TTSEngine
from core.config_loader import PROJECT_ROOT


def _build_single_script_provider(provider_name: str, config: dict, usage_tracker=None) -> ScriptGenerator:
    """Builds one concrete ScriptGenerator by name. Shared by both the
    single-provider path and the fallback-chain path so there's only one
    place that knows how to construct each provider."""
    sg_config = config["script_generation"]

    if provider_name == "gemini":
        from core.providers.gemini_script import GeminiScriptGenerator
        gemini_cfg = sg_config["gemini"]
        return GeminiScriptGenerator(
            model=gemini_cfg["model"],
            temperature=gemini_cfg["temperature"],
            max_output_tokens=gemini_cfg["max_output_tokens"],
            usage_tracker=usage_tracker,
            daily_limit=gemini_cfg.get("daily_limit", 0),
        )

    if provider_name == "gemini_lite":
        from core.providers.gemini_script import GeminiScriptGenerator
        lite_cfg = sg_config["gemini_lite"]
        return GeminiScriptGenerator(
            model=lite_cfg["model"],
            temperature=lite_cfg["temperature"],
            max_output_tokens=lite_cfg["max_output_tokens"],
            usage_tracker=usage_tracker,
            daily_limit=lite_cfg.get("daily_limit", 0),
        )

    if provider_name == "groq":
        from core.providers.groq_script import GroqScriptGenerator
        groq_cfg = sg_config["groq"]
        return GroqScriptGenerator(
            model=groq_cfg["model"],
            temperature=groq_cfg["temperature"],
            max_output_tokens=groq_cfg["max_output_tokens"],
            usage_tracker=usage_tracker,
            daily_limit=groq_cfg.get("daily_limit", 0),
            structured_output_mode=groq_cfg.get("structured_output_mode", "json_schema"),
        )

    # Phase 2 stub:
    # if provider_name == "claude":
    #     from core.providers.claude_script import ClaudeScriptGenerator
    #     return ClaudeScriptGenerator(...)

    raise ValueError(f"Unknown script_generator provider: {provider_name}")


def get_script_generator(config: dict) -> ScriptGenerator:
    provider_name = config["providers"]["script_generator"]

    if provider_name == "fallback_chain":
        from core.providers.fallback_script import FallbackScriptGenerator
        from core.provider_usage_tracker import ProviderUsageTracker

        usage_db_path = PROJECT_ROOT / config["paths"].get("usage_db", "state/provider_usage.db")
        usage_tracker = ProviderUsageTracker(str(usage_db_path))

        chain_names = config["script_generation"]["fallback_chain"]
        if not chain_names:
            raise ValueError(
                "providers.script_generator is 'fallback_chain' but "
                "script_generation.fallback_chain is empty in config.yaml"
            )

        providers = [
            (name, _build_single_script_provider(name, config, usage_tracker=usage_tracker))
            for name in chain_names
        ]
        return FallbackScriptGenerator(providers)

    return _build_single_script_provider(provider_name, config)


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
