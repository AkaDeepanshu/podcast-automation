"""Apply per-job EpisodeConfig overrides onto a loaded config.yaml dict."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from backend.database import SessionLocal
from backend.models import EpisodeConfig


@dataclass(frozen=True)
class EpisodeOverrides:
    target_duration_minutes: int | None
    num_segments: int | None
    model: str | None
    skip_video: bool


def get_episode_config(job_id: str) -> EpisodeOverrides | None:
    db = SessionLocal()
    try:
        row = db.get(EpisodeConfig, job_id)
        if row is None:
            return None
        return EpisodeOverrides(
            target_duration_minutes=row.target_duration_minutes,
            num_segments=row.num_segments,
            model=row.model,
            skip_video=bool(row.skip_video),
        )
    finally:
        db.close()


def apply_episode_overrides(
    config: dict[str, Any],
    episode: EpisodeOverrides | None,
    skip_video: bool,
) -> tuple[dict[str, Any], bool]:
    """
    Deep-copy config and merge EpisodeConfig fields.

    When an episode_configs row exists, its skip_video is authoritative.
    model override writes to script_generation.gemini.model only when the
    active script generator is gemini or fallback_chain (v1 rule).
    """
    cfg = copy.deepcopy(config)
    effective_skip = skip_video

    if episode is None:
        return cfg, effective_skip

    sg = cfg.setdefault("script_generation", {})
    if not isinstance(sg, dict):
        sg = {}
        cfg["script_generation"] = sg

    if episode.target_duration_minutes is not None:
        sg["target_duration_minutes"] = episode.target_duration_minutes
    if episode.num_segments is not None:
        sg["num_segments"] = episode.num_segments

    if episode.model:
        provider = (cfg.get("providers") or {}).get("script_generator")
        if provider in ("gemini", "fallback_chain"):
            gemini = sg.setdefault("gemini", {})
            if isinstance(gemini, dict):
                gemini["model"] = episode.model

    effective_skip = bool(episode.skip_video)
    return cfg, effective_skip
