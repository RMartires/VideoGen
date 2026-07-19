"""squares_on_sides and pythagorean_triple (triple = squares + sum caption)."""

from __future__ import annotations

from typing import Any

from manim import DOWN, Polygon, Text, UP, VGroup

from app.services.manim.core.geometry import (
    side_lengths,
    square_on_edge,
    triangle_vertices,
)
from app.services.manim.core.layout import fit
from app.services.manim.segments.base import SegmentDef


def build_squares_on_sides(scene, segment: dict[str, Any]) -> VGroup:
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
    sq_c = square_on_edge(p0, p2, p1, scene.accent)
    area_a = int(a * a)
    area_b = int(b * b)
    area_c = int(a * a + b * b)
    labels = VGroup(
        Text(f"a²={area_a}", color=scene.text_color, font_size=32).move_to(
            sq_a.get_center()
        ),
        Text(f"b²={area_b}", color=scene.text_color, font_size=32).move_to(
            sq_b.get_center()
        ),
        Text(f"c²={area_c}", color=scene.text_color, font_size=32).move_to(
            sq_c.get_center()
        ),
    )
    group = VGroup(triangle, sq_a, sq_b, sq_c, labels)
    title = segment.get("title")
    if title:
        header = Text(str(title), color=scene.accent, font_size=42)
        # Position relative to the diagram, not the frame edge: fit()
        # recenters the whole group, so edge-anchored headers end up on top of
        # the figure.
        header.next_to(group, UP, buff=0.55)
        group.add(header)
    return fit(group, max_width=10.5, max_height=9.0)


def build_pythagorean_triple(scene, segment: dict[str, Any]) -> VGroup:
    """3-4-5 style demo: triangle, squares, and area labels."""
    segment = dict(segment)
    if segment.get("side_a") is None and segment.get("a") is None:
        segment["side_a"] = 3
    if segment.get("side_b") is None and segment.get("b") is None:
        segment["side_b"] = 4
    group = build_squares_on_sides(scene, segment)
    a, b = side_lengths(segment)
    area_a, area_b = int(a * a), int(b * b)
    area_c = area_a + area_b
    summary = Text(
        f"{area_a} + {area_b} = {area_c}",
        color=scene.accent,
        font_size=48,
        weight="BOLD",
    )
    summary.next_to(group, DOWN, buff=0.5)
    group.add(summary)
    return fit(group, max_width=10.5, max_height=9.2)


SEGMENTS = [
    SegmentDef(
        type="squares_on_sides",
        category="geometry",
        build=build_squares_on_sides,
        intro="create",
    ),
    SegmentDef(
        type="pythagorean_triple",
        category="geometry",
        build=build_pythagorean_triple,
        intro="create",
    ),
]
