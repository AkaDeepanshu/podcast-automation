"""Topic discovery interface."""

from __future__ import annotations

from typing import Protocol


class TopicDiscovery(Protocol):
    def suggest_titles(
        self,
        focus_area: str,
        *,
        count: int,
        exclude: set[str],
    ) -> list[str]:
        """Return up to `count` new podcast topic titles for a focus area."""
        ...
