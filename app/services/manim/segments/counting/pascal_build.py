"""Pascal's triangle revealed row by row."""

from __future__ import annotations

from typing import Any

from manim import DOWN, FadeIn, Text, UP, VGroup

from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.segments.base import SegmentDef


def _pascal_rows(n: int) -> list[list[int]]:
    rows = [[1]]
    for _ in range(n - 1):
        prev = rows[-1]
        rows.append([1] + [prev[i] + prev[i + 1] for i in range(len(prev) - 1)] + [1])
    return rows


def build(scene, segment: dict[str, Any]) -> VGroup:
    n = max(3, min(8, int(segment.get("rows") or segment.get("count") or 5)))
    rows = _pascal_rows(n)
    row_groups = []
    triangle = VGroup()
    for values in rows:
        row = VGroup(
            *(
                Text(str(v), color=scene.text_color, font_size=32)
                for v in values
            )
        )
        row.arrange(buff=0.45)
        row.set_opacity(0)
        row_groups.append(row)
        triangle.add(row)
    triangle.arrange(DOWN, buff=0.35)
    group = VGroup(triangle)
    shell = None
    title = segment.get("title")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=42)
        shell.next_to(triangle, UP, buff=0.5)
        group.add(shell)
    group = fit(group)
    group.anim_shell = shell
    group.pascal_rows = row_groups
    return group


def animate(scene, segment: dict[str, Any], group: VGroup, budget: float) -> float:
    rows = getattr(group, "pascal_rows", None) or []
    if not rows:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    per_row = min(1.1, max(0.4, budget / max(1, len(rows) + 1)))
    for row in rows:
        if consumed + per_row > budget:
            break
        row.set_opacity(1)
        scene.play(FadeIn(row, shift=DOWN * 0.15), run_time=per_row)
        consumed += per_row
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENT = SegmentDef(
    type="pascal_build",
    category="counting",
    build=build,
    animate=animate,
    intro="shell_fade",
)
