"""A 2x2 matrix warping the plane, with ghost axes left behind (eola style)."""

from __future__ import annotations

from typing import Any

from manim import Text, UP, VGroup

from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.core.transforms import (
    apply_matrix_to_group,
    basis_arrows,
    make_plane,
    matrix_of,
)
from app.services.manim.segments.base import SegmentDef


def build(scene, segment: dict[str, Any]) -> VGroup:
    plane = make_plane()
    ghost = make_plane(faded=True)
    ghost.set_opacity(0.25)
    arrows = basis_arrows(scene, plane)
    group = VGroup(ghost, plane, arrows)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(group, UP, buff=0.4)
        group.add(shell)
    group = fit(group, max_height=5.5)
    group.anim_shell = shell
    group.warp_parts = {
        "moving": VGroup(plane, arrows),
        "matrix": matrix_of(segment),
    }
    return group


def animate(scene, segment: dict[str, Any], group: VGroup, budget: float) -> float:
    parts = getattr(group, "warp_parts", None) or {}
    moving = parts.get("moving")
    if moving is None or budget < 1.5:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    pause = min(0.5, budget * 0.15)
    if pause > 0.05:
        scene.wait(pause)
        consumed += pause
    warp_t = min(2.5, (budget - consumed) * 0.6)
    apply_matrix_to_group(scene, moving, parts["matrix"], warp_t)
    consumed += warp_t
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENT = SegmentDef(
    type="matrix_transform_plane",
    category="linear_algebra",
    build=build,
    animate=animate,
    intro="shell_fade",
)
