from __future__ import annotations

import math
import re
from typing import Any

from manim import DOWN, LEFT, Polygon, RIGHT, Text, UP, VGroup

from app.services.manim.core.geometry import side_lengths, triangle_vertices
from app.services.manim.core.layout import fit
from app.services.manim.segments.base import SegmentDef


def build(scene, segment: dict[str, Any]) -> VGroup:
    a, b = side_lengths(segment)
    p0, p1, p2, _, _ = triangle_vertices(a, b)
    triangle = Polygon(
        p0, p1, p2,
        color=scene.accent,
        fill_opacity=0.25,
        stroke_width=3,
    )
    c = math.sqrt(a * a + b * b)
    labels = VGroup(
        Text(
            f"a = {int(a) if a == int(a) else a}",
            color=scene.text_color,
            font_size=32,
        ).next_to((p0 + p1) / 2, DOWN, buff=0.25),
        Text(
            f"b = {int(b) if b == int(b) else b}",
            color=scene.text_color,
            font_size=32,
        ).next_to((p1 + p2) / 2, RIGHT, buff=0.25),
        Text(
            f"c = {int(c) if c == int(c) else round(c, 1)}",
            color=scene.text_color,
            font_size=32,
        ).next_to((p0 + p2) / 2, LEFT, buff=0.35),
    )
    group = VGroup(triangle, labels)
    caption = segment.get("caption") or segment.get("title")
    # Skip captions like "c = 5" that just repeat a side label already drawn
    # on the figure.
    if caption and re.fullmatch(
        r"[abc]\s*=\s*[\d.]+", str(caption).strip(), flags=re.IGNORECASE
    ):
        caption = None
    if caption:
        title = Text(str(caption), color=scene.accent, font_size=40)
        title.next_to(group, UP, buff=0.6)
        group.add(title)
    return fit(group)


SEGMENT = SegmentDef(
    type="right_triangle", category="geometry", build=build, intro="create"
)
