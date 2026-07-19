from __future__ import annotations

from typing import Any

import numpy as np
from manim import DOWN, Polygon, Text, Transform, UP, VGroup

from app.services.manim.core.geometry import (
    side_lengths,
    square_on_edge,
    triangle_vertices,
)
from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.segments.base import SegmentDef


def build(scene, segment: dict[str, Any]) -> VGroup:
    """Triangle with squares where the leg squares visibly fill c²."""
    a, b = side_lengths(segment)
    p0, p1, p2, _, _ = triangle_vertices(a, b, scale=0.45)
    triangle = Polygon(
        p0, p1, p2,
        color=scene.accent,
        fill_opacity=0.2,
        stroke_width=3,
    )
    sq_a = square_on_edge(p0, p1, p2, scene.accent)
    sq_b = square_on_edge(p1, p2, p0, scene.accent)
    sq_c = square_on_edge(p0, p2, p1, scene.accent, fill_opacity=0.08)
    area_a, area_b = int(a * a), int(b * b)
    area_c = area_a + area_b
    labels = VGroup(
        Text(f"a²={area_a}", color=scene.text_color, font_size=32).move_to(
            sq_a.get_center()
        ),
        Text(f"b²={area_b}", color=scene.text_color, font_size=32).move_to(
            sq_b.get_center()
        ),
    )

    # Split c² into two strips whose areas are exactly a² and b² (the classic
    # similar-triangle decomposition). They are built invisible so fit()
    # positions them with the rest of the group; the animator morphs ghost
    # copies of the leg squares onto them.
    edge = p2 - p0
    c_units = float(np.linalg.norm(edge))
    perp = np.array([-edge[1], edge[0], 0.0])
    perp = perp / max(1e-6, float(np.linalg.norm(perp)))
    mid = (p0 + p2) / 2
    if np.dot(perp, p1 - mid) > 0:
        perp = -perp
    h_a = c_units * (a * a) / (a * a + b * b)
    strip_a = Polygon(
        p0, p2, p2 + perp * h_a, p0 + perp * h_a,
        stroke_opacity=0.0,
        fill_opacity=0.0,
    )
    strip_b = Polygon(
        p0 + perp * h_a,
        p2 + perp * h_a,
        p2 + perp * c_units,
        p0 + perp * c_units,
        stroke_opacity=0.0,
        fill_opacity=0.0,
    )

    summary = Text(
        f"{area_a} + {area_b} = {area_c}",
        color=scene.accent,
        font_size=48,
        weight="BOLD",
    )
    summary.set_opacity(0.0)

    group = VGroup(triangle, sq_a, sq_b, sq_c, strip_a, strip_b, labels)
    summary.next_to(group, DOWN, buff=0.5)
    group.add(summary)
    title = segment.get("title")
    if title:
        header = Text(str(title), color=scene.accent, font_size=42)
        header.next_to(group, UP, buff=0.55)
        group.add(header)
    fit(group, max_width=10.5, max_height=9.2)
    group.transform_parts = {
        "sq_a": sq_a,
        "sq_b": sq_b,
        "strip_a": strip_a,
        "strip_b": strip_b,
        "summary": summary,
    }
    return group


def animate(scene, segment: dict[str, Any], group: VGroup, budget: float) -> float:
    """Slide copies of the leg squares onto c², then reveal the sum.

    Plays within ``budget`` seconds and returns the time consumed so the scene
    scheduler keeps segment starts aligned with the narration.
    """
    parts = getattr(group, "transform_parts", None)
    if not parts:
        return idle_pulses(scene, group, budget)
    if budget < 2.5:
        return idle_pulses(scene, group, budget)
    consumed = 0.0

    pause = min(0.5, budget * 0.12)
    if pause > 0:
        consumed += pause
        if pause > 0.05:
            scene.wait(pause)

    move_time = min(1.3, (budget - consumed) * 0.3)
    for src_key, dst_key in (("sq_a", "strip_a"), ("sq_b", "strip_b")):
        ghost = parts[src_key].copy()
        target = (
            parts[dst_key]
            .copy()
            .set_stroke(scene.accent, width=2, opacity=1.0)
            .set_fill(scene.accent, opacity=0.45)
        )
        scene.play(Transform(ghost, target), run_time=move_time)
        consumed += move_time
        # play() left the ghost as a top-level scene mobject; re-parent it
        # into the group so the segment crossfade fades it out too.
        scene.remove(ghost)
        group.add(ghost)

    summary = parts["summary"]
    if budget - consumed >= 0.8:
        scene.play(summary.animate.set_opacity(1.0), run_time=0.8)
        consumed += 0.8
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENT = SegmentDef(
    type="squares_transform",
    category="geometry",
    build=build,
    animate=animate,
    intro="create",
)
