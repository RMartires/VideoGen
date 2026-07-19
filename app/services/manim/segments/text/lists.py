"""step_by_step and bullet_points: staggered list reveals."""

from __future__ import annotations

from typing import Any

from manim import DOWN, Text, UP, VGroup

from app.services.manim.core.animation import stagger_reveal
from app.services.manim.core.layout import fit
from app.services.manim.segments.base import SegmentDef


def _build_list(
    scene,
    segment: dict[str, Any],
    items_key: str,
    prefix_fn,
    fallback_title: str,
) -> VGroup:
    group = VGroup()
    shell = None
    title = segment.get("title")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=48)
        group.add(shell)
    reveal_items = []
    for i, entry in enumerate(segment.get(items_key) or [], start=1):
        item = Text(prefix_fn(i, entry), color=scene.text_color, font_size=36)
        item.set_opacity(0)
        reveal_items.append(item)
        group.add(item)
    if len(group) == 0:
        item = Text(
            str(segment.get("title", fallback_title)),
            color=scene.text_color,
            font_size=48,
        )
        item.set_opacity(0)
        reveal_items.append(item)
        group.add(item)
    group.arrange(DOWN, buff=0.4, aligned_edge=UP)
    group = fit(group)
    group.stagger_shell = shell
    group.stagger_items = reveal_items
    return group


def build_steps(scene, segment: dict[str, Any]) -> VGroup:
    return _build_list(
        scene, segment, "steps", lambda i, s: f"{i}. {s}", "Steps"
    )


def build_bullets(scene, segment: dict[str, Any]) -> VGroup:
    return _build_list(
        scene, segment, "points", lambda _i, p: f"- {p}", "Notes"
    )


def animate(scene, segment: dict[str, Any], group: VGroup, budget: float) -> float:
    items = getattr(group, "stagger_items", None) or []
    return stagger_reveal(scene, group, items, budget)


SEGMENTS = [
    SegmentDef(
        type="step_by_step",
        category="text",
        build=build_steps,
        animate=animate,
        intro="stagger",
    ),
    SegmentDef(
        type="bullet_points",
        category="text",
        build=build_bullets,
        animate=animate,
        intro="stagger",
    ),
]
