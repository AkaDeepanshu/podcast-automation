"""LLM-backed topic title suggestions (JSON-mode, shared usage tracker)."""

from __future__ import annotations

import logging
import re

from backend.discovery.base import TopicDiscovery
from core.config_loader import PROJECT_ROOT, load_config
from core.provider_factory import _build_single_script_provider
from core.provider_usage_tracker import ProviderUsageTracker

log = logging.getLogger(__name__)

TITLES_SCHEMA = {
    "type": "object",
    "properties": {
        "titles": {
            "type": "array",
            "items": {"type": "string"},
        }
    },
    "required": ["titles"],
}


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").strip().lower())


def _provider_chain(config: dict):
    """Build script providers with a shared usage tracker (always on for discovery)."""
    usage_path = PROJECT_ROOT / config["paths"].get(
        "usage_db", "data/state/provider_usage.db"
    )
    tracker = ProviderUsageTracker(str(usage_path))
    name = config["providers"]["script_generator"]
    if name == "fallback_chain":
        chain = config["script_generation"].get("fallback_chain") or []
        if not chain:
            raise RuntimeError("fallback_chain is empty in config.yaml")
        return [
            (n, _build_single_script_provider(n, config, usage_tracker=tracker))
            for n in chain
        ]
    return [(name, _build_single_script_provider(name, config, usage_tracker=tracker))]


def _generate_json_with_fallback(prompt: str, schema: dict) -> dict:
    config = load_config()
    last_error: Exception | None = None
    for name, provider in _provider_chain(config):
        generate = getattr(provider, "_generate_json", None)
        if generate is None:
            continue
        try:
            return generate(prompt, schema)
        except Exception as exc:
            last_error = exc
            log.warning("Discovery provider '%s' failed: %s", name, exc)
    if last_error:
        raise last_error
    raise RuntimeError("No JSON-capable script provider available for discovery")


class LLMTopicDiscovery(TopicDiscovery):
    def suggest_titles(
        self,
        focus_area: str,
        *,
        count: int = 3,
        exclude: set[str] | None = None,
    ) -> list[str]:
        exclude = exclude or set()
        avoid = sorted(exclude)[:40]
        avoid_block = "\n".join(f"- {t}" for t in avoid) if avoid else "(none)"
        prompt = (
            f"Suggest {count} distinct podcast episode topic titles for an "
            f"English-learning conversational podcast.\n"
            f"Focus area: {focus_area}\n"
            f"Titles should be concrete, catchy, and suitable as episode topics "
            f"(not vague themes). Avoid duplicates of these existing titles:\n"
            f"{avoid_block}\n"
            f"Return JSON with a 'titles' array of strings only."
        )
        data = _generate_json_with_fallback(prompt, TITLES_SCHEMA)
        raw = data.get("titles") or []
        out: list[str] = []
        seen: set[str] = set(exclude)
        for item in raw:
            title = (item or "").strip()
            if not title:
                continue
            key = normalize_title(title)
            if key in seen:
                continue
            seen.add(key)
            out.append(title)
            if len(out) >= count:
                break
        return out
