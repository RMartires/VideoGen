"""Shared test utilities for the manim segment suites.

``HAS_MANIM`` gates every T2 builder/animator test: builders instantiate real
mobjects, so the whole tier skips when the optional Manim dependency is absent.
"""

from __future__ import annotations

import json
import os
from typing import Any

try:
    import manim  # noqa: F401

    HAS_MANIM = True
except Exception:  # pragma: no cover - optional dependency
    HAS_MANIM = False

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "specs")


def load_fixture(type_name: str) -> dict[str, Any]:
    path = os.path.join(FIXTURES_DIR, f"{type_name}.json")
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def fixture_names() -> set[str]:
    if not os.path.isdir(FIXTURES_DIR):
        return set()
    return {
        name[: -len(".json")]
        for name in os.listdir(FIXTURES_DIR)
        if name.endswith(".json")
    }


class MockScene:
    """Records play()/wait() calls; builders/animators need nothing more.

    Mimics the attribute surface segment functions use: accent, text_color,
    play, wait, add, remove.
    """

    accent = "#4da6ff"
    text_color = "#f5f7fa"

    def __init__(self) -> None:
        self.played: list[Any] = []
        self.waited: list[float] = []
        self.added: list[Any] = []
        self.removed: list[Any] = []

    def play(self, *animations: Any, run_time: float = 1.0, **_kw: Any) -> None:
        self.played.append((animations, run_time))

    def wait(self, duration: float = 1.0) -> None:
        self.waited.append(duration)

    def add(self, *mobjects: Any) -> None:
        self.added.extend(mobjects)

    def remove(self, *mobjects: Any) -> None:
        self.removed.extend(mobjects)

    @property
    def total_play_time(self) -> float:
        return sum(rt for _, rt in self.played) + sum(self.waited)
