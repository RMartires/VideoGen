"""Frame-aware sizing and subtitle-safe placement. Imports manim."""

from __future__ import annotations

from manim import DOWN, ORIGIN, UP

from app.services.manim.core.env import is_portrait


def fit(mobject, max_width: float | None = None, max_height: float | None = None):
    """Scale ``mobject`` into the visible frame and keep it subtitle-safe.

    At a portrait resolution Manim keeps frame_height = 8.0 and derives
    frame_width from the aspect: 8 * (1080/1920) = 4.5 units. Anything wider
    is cropped off-screen, so the caps must respect the visible frame, not the
    landscape defaults.
    """
    if is_portrait():
        cap_width, cap_height = 4.2, 5.0
    else:
        cap_width, cap_height = 12.0, 7.0
    max_width = min(max_width, cap_width) if max_width else cap_width
    max_height = min(max_height, cap_height) if max_height else cap_height
    if mobject.width > max_width:
        mobject.scale_to_fit_width(max_width)
    if mobject.height > max_height:
        mobject.scale_to_fit_height(max_height)
    # Geometry templates build outward from ORIGIN, which leaves them
    # off-center; recenter every group before placing it.
    mobject.move_to(ORIGIN)
    if is_portrait():
        mobject.shift(UP * 0.85)
        # Burned-in subtitles are anchored at 78% of the frame height and a
        # three-line box reaches up to about y = -1.7; keep a margin so bottom
        # labels never sit behind the subtitle background.
        subtitle_top = -1.4
        bottom = float(mobject.get_bottom()[1])
        if bottom < subtitle_top:
            mobject.shift(UP * (subtitle_top - bottom))
        top_limit = 3.8
        top = float(mobject.get_top()[1])
        if top > top_limit:
            mobject.shift(DOWN * (top - top_limit))
    return mobject
