from __future__ import annotations

from typing import Any

from manim import DOWN, Text, UP, VGroup

from app.services.manim.core.env import portrait_scale
from app.services.manim.core.grids import cell_grid
from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.segments.base import SegmentDef


def build(scene, segment: dict[str, Any]) -> VGroup:
    """n×n unit-square grid illustrating side length squared = area."""
    n = int(segment.get("side") or segment.get("side_a") or 3)
    n = max(2, min(n, 6))
    cell = 0.48 * (portrait_scale() / 1.75)
    cells = cell_grid(n, n, cell, scene.accent)
    area = n * n
    label = Text(
        f"{n} × {n}  area = {area}",
        color=scene.text_color,
        font_size=44,
        weight="BOLD",
    )
    label.next_to(cells, DOWN, buff=0.45)
    group = VGroup(cells, label)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, font_size=38)
        shell.next_to(group, UP, buff=0.5)
        group.add(shell)
    group = fit(group)
    group.grid_shell = shell
    group.grid_cells = list(cells)
    return group


def animate(scene, segment: dict[str, Any], group: VGroup, budget: float) -> float:
    cells = getattr(group, "grid_cells", None) or []
    if not cells:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    per_cell = min(0.35, max(0.12, budget / max(1, len(cells) + 1)))
    for cell in cells:
        if consumed + per_cell > budget:
            break
        scene.play(
            cell.animate.set_fill(scene.accent, opacity=0.45),
            run_time=per_cell,
        )
        consumed += per_cell
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENT = SegmentDef(
    type="area_grid",
    category="geometry",
    build=build,
    animate=animate,
    intro="grid_fade",
)
