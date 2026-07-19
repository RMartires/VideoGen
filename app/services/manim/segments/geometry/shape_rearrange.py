"""Pieces of one shape sliding along arcs into another of equal area."""

from __future__ import annotations

from typing import Any

from manim import DOWN, LEFT, RIGHT, Polygon, Square, Text, Transform, UP, VGroup

from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.segments.base import SegmentDef

_SIDE = 1.9


def build(scene, segment: dict[str, Any]) -> VGroup:
    """A square cut into two triangles that reassemble into a big triangle.

    A minimal, always-valid dissection demo: the classic 'same pieces, same
    area, different shape' beat used across 3b1b proofs.
    """
    s = _SIDE
    square = Square(side_length=s, color=scene.text_color, stroke_width=2)
    square.shift(LEFT * 1.6)
    corner = square.get_corner(DOWN + LEFT)
    tri_a = Polygon(
        corner, corner + [s, 0, 0], corner + [0, s, 0],
        color=scene.accent, fill_opacity=0.45, stroke_width=1.5,
    )
    tri_b = Polygon(
        corner + [s, 0, 0], corner + [s, s, 0], corner + [0, s, 0],
        color=scene.accent, fill_opacity=0.3, stroke_width=1.5,
    )

    # Targets: the same two triangles laid out as one big right triangle.
    base = square.get_corner(DOWN + RIGHT) + RIGHT * 1.4
    target_a = Polygon(
        base, base + [s, 0, 0], base + [0, s, 0],
        color=scene.accent, fill_opacity=0.45, stroke_width=1.5,
    )
    target_b = Polygon(
        base + [s, 0, 0], base + [2 * s, 0, 0], base + [s, s, 0],
        color=scene.accent, fill_opacity=0.3, stroke_width=1.5,
    )
    ghost_targets = VGroup(target_a.copy(), target_b.copy())
    ghost_targets.set_opacity(0)

    caption = Text(
        segment.get("caption") or "Same pieces, same area",
        color=scene.text_color,
        font_size=34,
    )
    group = VGroup(square, tri_a, tri_b, ghost_targets)
    caption.next_to(group, DOWN, buff=0.5)
    group.add(caption)
    shell = None
    title = segment.get("title")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(group, UP, buff=0.5)
        group.add(shell)
    group = fit(group, max_width=10.5)
    group.rearrange_parts = {
        "pieces": [tri_a, tri_b],
        "targets": list(ghost_targets),
    }
    group.anim_shell = shell
    return group


def animate(scene, segment: dict[str, Any], group: VGroup, budget: float) -> float:
    parts = getattr(group, "rearrange_parts", None) or {}
    pieces = parts.get("pieces") or []
    targets = parts.get("targets") or []
    if not pieces or len(pieces) != len(targets) or budget < 2.0:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    per = min(1.4, max(0.7, budget / (len(pieces) + 2)))
    for piece, target in zip(pieces, targets):
        if consumed + per > budget:
            break
        ghost = piece.copy()
        goal = target.copy().set_opacity(1)
        scene.play(Transform(ghost, goal, path_arc=0.7), run_time=per)
        consumed += per
        scene.remove(ghost)
        group.add(ghost)
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENT = SegmentDef(
    type="shape_rearrange",
    category="geometry",
    build=build,
    animate=animate,
    intro="create",
)
