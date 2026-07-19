from __future__ import annotations

from typing import Any

from manim import DOWN, Text, VGroup

from app.services.manim.core.layout import fit
from app.services.manim.segments.base import SegmentDef


def build(scene, segment: dict[str, Any]) -> VGroup:
    title = Text(
        str(segment.get("title", "Math")),
        color=scene.text_color,
        weight="BOLD",
        font_size=64,
    )
    group = VGroup(title)
    subtitle = segment.get("subtitle")
    if subtitle:
        sub = Text(str(subtitle), color=scene.accent, font_size=40)
        sub.next_to(title, DOWN, buff=0.5)
        group.add(sub)
    group.arrange(DOWN, buff=0.5)
    return fit(group)


SEGMENT = SegmentDef(type="title_card", category="text", build=build, intro="write")
