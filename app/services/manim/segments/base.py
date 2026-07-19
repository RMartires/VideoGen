"""Protocols shared by every segment module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

# build(scene, segment) -> VGroup
Builder = Callable[[Any, dict], Any]
# animate(scene, segment, mobject, budget_seconds) -> seconds consumed
Animator = Callable[[Any, dict, Any, float], float]


@dataclass(frozen=True)
class SegmentDef:
    """One renderable segment type.

    ``intro`` picks the entry animation played by the scene loop:
      - "write":      Write(mobject)                       (default)
      - "create":     Create(mobject)                      (geometry diagrams)
      - "stagger":    shell first, items revealed by the animator
      - "plot":       Create(axes + label), graph drawn by the animator
      - "shell_fade": FadeIn anim_shell / whole group      (counters, bars)
      - "grid_fade":  FadeIn grid_shell, else Create       (cell grids)
    """

    type: str
    category: str
    build: Builder
    animate: Optional[Animator] = None
    intro: str = "write"
