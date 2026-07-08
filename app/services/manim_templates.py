"""Manim Community Edition scene templates for math-explainer videos.

This module is executed *standalone* by the ``manim`` CLI (see
``app/services/manim_video.py``); it is never imported by the running app, so it
is safe for it to ``import manim`` at module load time even though Manim is an
optional dependency.

The scene reads a validated JSON "scene spec" (path in ``MANIM_SPEC_PATH``) and a
target duration (``MANIM_TARGET_DURATION`` seconds), then renders each segment
with a fixed, parameterized template. The LLM only ever produces the JSON data;
no arbitrary code from the spec is executed. The single exception is plot
``function`` strings, which are evaluated in a locked-down namespace (no builtins,
math functions only) in :func:`_safe_math_fn`.
"""

from __future__ import annotations

import json
import math
import os
from typing import Any, Callable

import numpy as np
from manim import (
    DOWN,
    LEFT,
    ORIGIN,
    RIGHT,
    UP,
    Axes,
    Create,
    FadeOut,
    NumberLine,
    Polygon,
    Scene,
    Square,
    Text,
    VGroup,
    Write,
)

try:  # MathTex needs a LaTeX toolchain; degrade gracefully when it is absent.
    from manim import MathTex

    _HAS_MATHTEX = True
except Exception:  # pragma: no cover - import guard
    MathTex = None  # type: ignore[assignment]
    _HAS_MATHTEX = False


DEFAULT_BACKGROUND = "#0b0f1a"
DEFAULT_ACCENT = "#4da6ff"
DEFAULT_TEXT = "#f5f7fa"

# Whitelisted names available to plot ``function`` expressions. No builtins are
# exposed, so expressions like ``__import__('os')`` cannot resolve.
_SAFE_MATH_NAMES: dict[str, Any] = {
    "sin": np.sin,
    "cos": np.cos,
    "tan": np.tan,
    "arcsin": np.arcsin,
    "arccos": np.arccos,
    "arctan": np.arctan,
    "sinh": np.sinh,
    "cosh": np.cosh,
    "tanh": np.tanh,
    "exp": np.exp,
    "log": np.log,
    "log10": np.log10,
    "sqrt": np.sqrt,
    "abs": np.abs,
    "floor": np.floor,
    "ceil": np.ceil,
    "sign": np.sign,
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}


def _spec() -> dict[str, Any]:
    spec_path = os.environ.get("MANIM_SPEC_PATH", "")
    with open(spec_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _target_duration() -> float:
    try:
        value = float(os.environ.get("MANIM_TARGET_DURATION", "40"))
    except (TypeError, ValueError):
        value = 40.0
    return max(4.0, value)


def _safe_math_fn(expr: str) -> Callable[[float], float]:
    """Compile a plot expression into a callable over ``x`` in a safe namespace."""
    code = compile(expr, "<manim-plot>", "eval")
    for name in code.co_names:
        if name not in _SAFE_MATH_NAMES and name != "x":
            raise ValueError(f"disallowed name in plot function: {name}")

    def fn(x: float) -> float:
        return eval(code, {"__builtins__": {}}, {**_SAFE_MATH_NAMES, "x": x})

    return fn


def _triangle_vertices(side_a: float, side_b: float, scale: float = 0.55):
    """Right triangle: right angle at origin, leg a along +x, leg b along +y."""
    a = max(0.5, float(side_a))
    b = max(0.5, float(side_b))
    p0 = ORIGIN
    p1 = a * scale * RIGHT
    p2 = p1 + b * scale * UP
    return p0, p1, p2, a, b


def _square_on_edge(p0, p1, p_outside, color, fill_opacity: float = 0.22):
    """Square built outward from edge p0→p1, away from p_outside."""
    edge = p1 - p0
    length = float(np.linalg.norm(edge))
    if length < 1e-6:
        return Square(side_length=0.1, color=color)
    angle = math.atan2(edge[1], edge[0])
    sq = Square(
        side_length=length,
        color=color,
        fill_opacity=fill_opacity,
        stroke_width=2,
    )
    sq.rotate(angle)
    mid = (p0 + p1) / 2
    perp = np.array([-edge[1], edge[0], 0.0])
    perp_norm = np.linalg.norm(perp)
    if perp_norm > 1e-6:
        perp = perp / perp_norm
    if np.dot(perp, p_outside - mid) > 0:
        perp = -perp
    sq.move_to(mid + perp * (length / 2))
    return sq


class MathExplainerScene(Scene):
    def construct(self) -> None:
        spec = _spec()
        self.accent = spec.get("accent_color") or DEFAULT_ACCENT
        self.text_color = spec.get("text_color") or DEFAULT_TEXT
        self.camera.background_color = spec.get("background_color") or DEFAULT_BACKGROUND

        segments = spec.get("segments") or []
        if not segments:
            segments = [{"type": "title_card", "title": spec.get("title", "Math")}]

        slot = _target_duration() / max(1, len(segments))
        # In/out animation budget per segment; the remainder is a static hold.
        anim = min(1.2, max(0.4, slot * 0.35))
        hold = max(0.6, slot - 2 * anim)

        builders: dict[str, Callable[[dict[str, Any]], VGroup]] = {
            "title_card": self._title_card,
            "equation_reveal": self._equation_reveal,
            "step_by_step": self._step_by_step,
            "bullet_points": self._bullet_points,
            "axes_plot": self._axes_plot,
            "number_line": self._number_line,
            "right_triangle": self._right_triangle,
            "squares_on_sides": self._squares_on_sides,
            "pythagorean_triple": self._pythagorean_triple,
            "area_grid": self._area_grid,
        }
        create_types = {
            "axes_plot",
            "number_line",
            "right_triangle",
            "squares_on_sides",
            "pythagorean_triple",
            "area_grid",
        }

        for segment in segments:
            seg_type = str(segment.get("type", "title_card"))
            builder = builders.get(seg_type, self._title_card)
            try:
                mobject = builder(segment)
            except Exception:
                mobject = self._title_card({"title": str(segment.get("title", "Math"))})

            intro = Create(mobject) if seg_type in create_types else Write(mobject)
            self.play(intro, run_time=anim)
            self.wait(hold)
            self.play(FadeOut(mobject), run_time=anim)

    # --- helpers -----------------------------------------------------------
    def _math(self, expr: str, **kwargs: Any):
        if _HAS_MATHTEX:
            try:
                return MathTex(expr, **kwargs)
            except Exception:
                pass
        return Text(expr, **kwargs)

    def _fit(self, mobject, max_width: float = 12.0, max_height: float = 7.0):
        if mobject.width > max_width:
            mobject.scale_to_fit_width(max_width)
        if mobject.height > max_height:
            mobject.scale_to_fit_height(max_height)
        return mobject

    # --- templates ---------------------------------------------------------
    def _title_card(self, segment: dict[str, Any]) -> VGroup:
        title = Text(
            str(segment.get("title", "Math")),
            color=self.text_color,
            weight="BOLD",
            font_size=64,
        )
        group = VGroup(title)
        subtitle = segment.get("subtitle")
        if subtitle:
            sub = Text(str(subtitle), color=self.accent, font_size=40)
            sub.next_to(title, DOWN, buff=0.5)
            group.add(sub)
        group.arrange(DOWN, buff=0.5)
        return self._fit(group)

    def _equation_reveal(self, segment: dict[str, Any]) -> VGroup:
        equations = segment.get("equations") or []
        if isinstance(equations, str):
            equations = [equations]
        group = VGroup()
        caption = segment.get("caption")
        if caption:
            group.add(Text(str(caption), color=self.text_color, font_size=40))
        for eq in equations:
            group.add(self._math(str(eq), color=self.text_color, font_size=56))
        if not group:
            group.add(Text("=", color=self.text_color, font_size=56))
        group.arrange(DOWN, buff=0.6)
        return self._fit(group)

    def _step_by_step(self, segment: dict[str, Any]) -> VGroup:
        group = VGroup()
        title = segment.get("title")
        if title:
            group.add(Text(str(title), color=self.accent, weight="BOLD", font_size=48))
        for i, step in enumerate(segment.get("steps") or [], start=1):
            group.add(Text(f"{i}. {step}", color=self.text_color, font_size=36))
        if len(group) == 0:
            group.add(Text(str(segment.get("title", "Steps")), color=self.text_color, font_size=48))
        group.arrange(DOWN, buff=0.4, aligned_edge=UP)
        return self._fit(group)

    def _bullet_points(self, segment: dict[str, Any]) -> VGroup:
        group = VGroup()
        title = segment.get("title")
        if title:
            group.add(Text(str(title), color=self.accent, weight="BOLD", font_size=48))
        for point in segment.get("points") or []:
            group.add(Text(f"- {point}", color=self.text_color, font_size=36))
        if len(group) == 0:
            group.add(Text(str(segment.get("title", "Notes")), color=self.text_color, font_size=48))
        group.arrange(DOWN, buff=0.4, aligned_edge=UP)
        return self._fit(group)

    def _axes_plot(self, segment: dict[str, Any]) -> VGroup:
        x_range = segment.get("x_range") or [-5, 5]
        y_range = segment.get("y_range") or [-3, 3]
        axes = Axes(
            x_range=[float(x_range[0]), float(x_range[1])],
            y_range=[float(y_range[0]), float(y_range[1])],
            axis_config={"color": self.text_color, "include_tip": True},
        )
        group = VGroup(axes)
        expr = segment.get("function")
        if expr:
            fn = _safe_math_fn(str(expr))
            graph = axes.plot(fn, color=self.accent)
            group.add(graph)
        label = segment.get("label")
        if label:
            text = Text(str(label), color=self.accent, font_size=36)
            text.next_to(axes, UP)
            group.add(text)
        return self._fit(group)

    def _side_lengths(self, segment: dict[str, Any]) -> tuple[float, float]:
        a = float(segment.get("side_a") or segment.get("a") or 3)
        b = float(segment.get("side_b") or segment.get("b") or 4)
        return max(0.5, a), max(0.5, b)

    def _right_triangle(self, segment: dict[str, Any]) -> VGroup:
        a, b = self._side_lengths(segment)
        p0, p1, p2, _, _ = _triangle_vertices(a, b)
        triangle = Polygon(
            p0, p1, p2,
            color=self.accent,
            fill_opacity=0.25,
            stroke_width=3,
        )
        c = math.sqrt(a * a + b * b)
        labels = VGroup(
            Text(f"a = {int(a) if a == int(a) else a}", color=self.text_color, font_size=32).next_to(
                (p0 + p1) / 2, DOWN, buff=0.25
            ),
            Text(f"b = {int(b) if b == int(b) else b}", color=self.text_color, font_size=32).next_to(
                (p1 + p2) / 2, RIGHT, buff=0.25
            ),
            Text(
                f"c = {int(c) if c == int(c) else round(c, 1)}",
                color=self.text_color,
                font_size=32,
            ).next_to((p0 + p2) / 2, LEFT, buff=0.35),
        )
        group = VGroup(triangle, labels)
        caption = segment.get("caption") or segment.get("title")
        if caption:
            title = Text(str(caption), color=self.accent, font_size=40)
            title.to_edge(UP, buff=0.5)
            group.add(title)
        return self._fit(group)

    def _squares_on_sides(self, segment: dict[str, Any]) -> VGroup:
        a, b = self._side_lengths(segment)
        p0, p1, p2, _, _ = _triangle_vertices(a, b, scale=0.45)
        triangle = Polygon(
            p0, p1, p2,
            color=self.accent,
            fill_opacity=0.2,
            stroke_width=3,
        )
        sq_a = _square_on_edge(p0, p1, p2, self.accent)
        sq_b = _square_on_edge(p1, p2, p0, self.accent)
        sq_c = _square_on_edge(p0, p2, p1, self.accent)
        area_a = int(a * a)
        area_b = int(b * b)
        area_c = int(a * a + b * b)
        labels = VGroup(
            Text(f"a^2={area_a}", color=self.text_color, font_size=28).move_to(sq_a.get_center()),
            Text(f"b^2={area_b}", color=self.text_color, font_size=28).move_to(sq_b.get_center()),
            Text(f"c^2={area_c}", color=self.text_color, font_size=28).move_to(sq_c.get_center()),
        )
        group = VGroup(triangle, sq_a, sq_b, sq_c, labels)
        title = segment.get("title")
        if title:
            header = Text(str(title), color=self.accent, font_size=38)
            header.to_edge(UP, buff=0.4)
            group.add(header)
        return self._fit(group, max_width=11.0, max_height=6.5)

    def _pythagorean_triple(self, segment: dict[str, Any]) -> VGroup:
        """3-4-5 style demo: triangle, squares, and area labels."""
        segment = dict(segment)
        if segment.get("side_a") is None and segment.get("a") is None:
            segment["side_a"] = 3
        if segment.get("side_b") is None and segment.get("b") is None:
            segment["side_b"] = 4
        group = self._squares_on_sides(segment)
        a, b = self._side_lengths(segment)
        area_a, area_b = int(a * a), int(b * b)
        area_c = area_a + area_b
        summary = Text(
            f"{area_a} + {area_b} = {area_c}",
            color=self.accent,
            font_size=44,
            weight="BOLD",
        )
        summary.to_edge(DOWN, buff=0.5)
        group.add(summary)
        return self._fit(group, max_width=11.0, max_height=6.8)

    def _area_grid(self, segment: dict[str, Any]) -> VGroup:
        """n×n unit-square grid illustrating side length squared = area."""
        n = int(segment.get("side") or segment.get("side_a") or 3)
        n = max(2, min(n, 6))
        cell = 0.38
        grid = VGroup()
        for row in range(n):
            for col in range(n):
                sq = Square(
                    side_length=cell,
                    color=self.accent,
                    fill_opacity=0.35,
                    stroke_width=1.5,
                )
                sq.move_to(
                    ORIGIN
                    + (col - (n - 1) / 2) * cell * RIGHT
                    + (row - (n - 1) / 2) * cell * UP
                )
                grid.add(sq)
        area = n * n
        label = Text(
            f"{n} x {n}  area = {area}",
            color=self.text_color,
            font_size=40,
            weight="BOLD",
        )
        label.next_to(grid, DOWN, buff=0.45)
        group = VGroup(grid, label)
        title = segment.get("title") or segment.get("caption")
        if title:
            header = Text(str(title), color=self.accent, font_size=38)
            header.to_edge(UP, buff=0.4)
            group.add(header)
        return self._fit(group)

    def _number_line(self, segment: dict[str, Any]) -> VGroup:
        x_range = segment.get("x_range") or [0, 10]
        line = NumberLine(
            x_range=[float(x_range[0]), float(x_range[1]), 1],
            include_numbers=True,
            color=self.text_color,
        )
        group = VGroup(line)
        label = segment.get("label")
        if label:
            text = Text(str(label), color=self.accent, font_size=36)
            text.next_to(line, UP, buff=0.6)
            group.add(text)
        return self._fit(group)
