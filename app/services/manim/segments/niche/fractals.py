"""P2 fractal/growth types: fractal_iterate, fractal_zoom, spiral_growth,
newton_basins."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from manim import (
    Dot,
    FadeIn,
    LEFT,
    Line,
    RIGHT,
    Square,
    Text,
    Transform,
    UP,
    VGroup,
    VMobject,
)

from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.segments.base import SegmentDef


def _koch_side(start: np.ndarray, end: np.ndarray, depth: int) -> list[np.ndarray]:
    """Point list of a Koch-curve side at the given depth (endpoints included)."""
    if depth == 0:
        return [start, end]
    delta = (end - start) / 3.0
    a = start + delta
    b = start + 2 * delta
    # Peak of the equilateral bump, rotated +60° from the middle third.
    angle = math.pi / 3
    rot = np.array(
        [
            [math.cos(angle), -math.sin(angle), 0.0],
            [math.sin(angle), math.cos(angle), 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    peak = a + rot @ delta
    points: list[np.ndarray] = []
    for seg_start, seg_end in ((start, a), (a, peak), (peak, b), (b, end)):
        sub = _koch_side(seg_start, seg_end, depth - 1)
        points.extend(sub[:-1])
    points.append(end)
    return points


def _koch_curve(width: float, depth: int, color) -> VMobject:
    start = np.array([-width / 2, 0.0, 0.0])
    end = np.array([width / 2, 0.0, 0.0])
    curve = VMobject(color=color, stroke_width=2.5)
    curve.set_points_as_corners(_koch_side(start, end, depth))
    return curve


# --- fractal_iterate: the Koch curve gains detail one iteration at a time ----
def build_fractal_iterate(scene, segment: dict[str, Any]) -> VGroup:
    curve = _koch_curve(5.0, 0, scene.accent)
    group = VGroup(curve)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(curve, UP, buff=1.2)
        group.add(shell)
    group = fit(group, max_height=5.0)
    group.anim_shell = shell
    group.fractal_parts = {"curve": curve, "width": 5.0, "max_depth": 4}
    return group


def animate_fractal_iterate(scene, segment, group, budget: float) -> float:
    parts = getattr(group, "fractal_parts", None) or {}
    curve = parts.get("curve")
    if curve is None or budget < 1.5:
        return idle_pulses(scene, group, budget)
    width = parts.get("width", 5.0)
    max_depth = int(parts.get("max_depth", 4))
    consumed = 0.0
    per_step = min(1.3, max(0.7, budget / (max_depth + 1)))
    center = curve.get_center()
    for depth in range(1, max_depth + 1):
        if consumed + per_step > budget:
            break
        target = _koch_curve(width, depth, scene.accent)
        target.move_to(center)
        scene.play(Transform(curve, target), run_time=per_step)
        consumed += per_step
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- fractal_zoom: zooming into self-similar squares ------------------------
def build_fractal_zoom(scene, segment: dict[str, Any]) -> VGroup:
    # Nested squares, each a third the size, tucked in the top-right corner:
    # scaling the whole group makes the "same shape again" pop out.
    squares = VGroup()
    side = 4.0
    corner = np.array([0.0, 0.0, 0.0])
    for i in range(5):
        sq = Square(side_length=side, color=scene.accent, stroke_width=2.5)
        sq.move_to(corner + np.array([side / 2, side / 2, 0.0]))
        squares.add(sq)
        corner = corner + np.array([side * 2 / 3, side * 2 / 3, 0.0])
        side /= 3.0
    squares.move_to([0, 0, 0])
    group = VGroup(squares)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(squares, UP, buff=0.45)
        group.add(shell)
    group = fit(group, max_height=5.5)
    group.anim_shell = shell
    group.zoom_parts = {"squares": squares}
    return group


def animate_fractal_zoom(scene, segment, group, budget: float) -> float:
    parts = getattr(group, "zoom_parts", None) or {}
    squares = parts.get("squares")
    if squares is None or budget < 1.5:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    zooms = 2
    per_zoom = min(2.0, max(1.0, (budget - 0.4) / zooms))
    for _ in range(zooms):
        if consumed + per_zoom > budget:
            break
        inner = squares[1]
        scale = squares[0].width / inner.width
        shift = squares[0].get_center() - inner.get_center()
        scene.play(
            squares.animate.scale(scale, about_point=squares[0].get_center())
            .shift(shift * scale),
            run_time=per_zoom,
        )
        consumed += per_zoom
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- spiral_growth: golden-angle dots spiral outward -------------------------
def build_spiral_growth(scene, segment: dict[str, Any]) -> VGroup:
    count = max(20, min(120, int(segment.get("count") or 80)))
    golden = math.pi * (3 - math.sqrt(5))
    dots = VGroup()
    for i in range(count):
        r = 0.22 * math.sqrt(i)
        theta = i * golden
        dot = Dot(
            np.array([r * math.cos(theta), r * math.sin(theta), 0.0]),
            radius=0.05,
            color=scene.accent,
        )
        dot.set_opacity(0)
        dots.add(dot)
    group = VGroup(dots)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(dots, UP, buff=0.45)
        group.add(shell)
    group = fit(group, max_height=5.5)
    group.anim_shell = shell
    group.spiral_dots = list(dots)
    return group


def animate_spiral_growth(scene, segment, group, budget: float) -> float:
    dots = getattr(group, "spiral_dots", None) or []
    if not dots or budget < 1.0:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    grow_t = min(4.0, budget * 0.7)
    batch = max(1, len(dots) // max(1, int(grow_t / 0.25)))
    per_batch = grow_t / math.ceil(len(dots) / batch)
    for i in range(0, len(dots), batch):
        if consumed + per_batch > budget:
            break
        scene.play(
            *(dot.animate.set_opacity(1) for dot in dots[i : i + batch]),
            run_time=per_batch,
        )
        consumed += per_batch
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- newton_basins: roots color the line they attract ------------------------
def build_newton_basins(scene, segment: dict[str, Any]) -> VGroup:
    # 1-D caricature: three roots on a line; seeds slide to whichever root
    # Newton's method sends them to, coloring by destination.
    roots_x = [-2.0, 0.0, 2.0]
    line = Line(LEFT * 3.2, RIGHT * 3.2, color=scene.text_color, stroke_width=2)
    root_dots = VGroup(
        *(
            Dot(np.array([x, 0.0, 0.0]), radius=0.09, color=scene.accent)
            for x in roots_x
        )
    )
    group = VGroup(line, root_dots)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(line, UP, buff=1.0)
        group.add(shell)
    group = fit(group, max_height=5.0)
    group.anim_shell = shell
    group.basin_parts = {"line": line, "roots_x": roots_x}
    return group


def animate_newton_basins(scene, segment, group, budget: float) -> float:
    parts = getattr(group, "basin_parts", None) or {}
    roots_x = parts.get("roots_x") or []
    line = parts.get("line")
    if not roots_x or line is None or budget < 1.5:
        return idle_pulses(scene, group, budget)
    center = line.get_center()
    consumed = 0.0
    seeds = [x / 10.0 for x in range(-30, 31, 6)]
    per_wave = min(1.4, max(0.8, budget / 4.0))
    wave = 0
    while consumed + per_wave <= budget - 0.2 and wave < 3:
        dots = VGroup()
        moves = []
        for seed_x in seeds[wave::3]:
            nearest = min(roots_x, key=lambda r: abs(r - seed_x))
            dot = Dot(
                center + np.array([seed_x, 0.6, 0.0]),
                radius=0.06,
                color=scene.accent,
            )
            dots.add(dot)
            moves.append(
                dot.animate.move_to(center + np.array([nearest, 0.0, 0.0]))
            )
        scene.play(FadeIn(dots, run_time=0.2), *moves, run_time=per_wave)
        group.add(dots)
        consumed += per_wave
        wave += 1
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENTS = [
    SegmentDef(
        type="fractal_iterate",
        category="niche",
        build=build_fractal_iterate,
        animate=animate_fractal_iterate,
        intro="shell_fade",
    ),
    SegmentDef(
        type="fractal_zoom",
        category="niche",
        build=build_fractal_zoom,
        animate=animate_fractal_zoom,
        intro="shell_fade",
    ),
    SegmentDef(
        type="spiral_growth",
        category="niche",
        build=build_spiral_growth,
        animate=animate_spiral_growth,
        intro="shell_fade",
    ),
    SegmentDef(
        type="newton_basins",
        category="niche",
        build=build_newton_basins,
        animate=animate_newton_basins,
        intro="shell_fade",
    ),
]
