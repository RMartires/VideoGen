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
import re
import traceback
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
    Indicate,
    NumberLine,
    Polygon,
    Scene,
    Square,
    Text,
    Transform,
    VGroup,
    Write,
)
from manim import config as manim_config

# Manim CE does NOT recompute the camera frame when --resolution changes: it
# keeps the default 14.22x8-unit landscape frame, so a 1080x1920 portrait
# render maps 14.22 units across 1080px and shows ~25 units vertically —
# content built for an 8-unit-tall frame ends up tiny in the middle third.
# Match the frame to the actual pixel aspect so 1 unit renders the same size
# in every orientation (portrait: 4.5x8 units for 1080x1920).
_frame_aspect = float(os.environ.get("MANIM_FRAME_ASPECT", "0") or 0)
if _frame_aspect > 0:
    manim_config.frame_width = manim_config.frame_height * _frame_aspect

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


def _is_portrait() -> bool:
    return os.environ.get("MANIM_IS_PORTRAIT", "0") == "1"


def _portrait_scale() -> float:
    return 1.75 if _is_portrait() else 1.0


_SUPERSCRIPT_MAP = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
    "+": "⁺", "-": "⁻", "(": "⁽", ")": "⁾", "=": "⁼",
    "a": "ᵃ", "b": "ᵇ", "c": "ᶜ", "d": "ᵈ", "e": "ᵉ", "f": "ᶠ",
    "g": "ᵍ", "h": "ʰ", "i": "ⁱ", "j": "ʲ", "k": "ᵏ", "l": "ˡ",
    "m": "ᵐ", "n": "ⁿ", "o": "ᵒ", "p": "ᵖ", "r": "ʳ", "s": "ˢ",
    "t": "ᵗ", "u": "ᵘ", "v": "ᵛ", "w": "ʷ", "x": "ˣ", "y": "ʸ", "z": "ᶻ",
}
_SUBSCRIPT_MAP = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
    "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
    "+": "₊", "-": "₋", "=": "₌",
    "a": "ₐ", "e": "ₑ", "h": "ₕ", "i": "ᵢ", "j": "ⱼ", "k": "ₖ",
    "l": "ₗ", "m": "ₘ", "n": "ₙ", "o": "ₒ", "p": "ₚ", "r": "ᵣ",
    "s": "ₛ", "t": "ₜ", "u": "ᵤ", "v": "ᵥ", "x": "ₓ",
}
_LATEX_SYMBOLS = {
    r"\cdot": "·", r"\times": "×", r"\div": "÷", r"\pm": "±",
    r"\pi": "π", r"\theta": "θ", r"\alpha": "α", r"\beta": "β",
    r"\infty": "∞", r"\sqrt": "√", r"\approx": "≈",
    r"\leq": "≤", r"\geq": "≥", r"\le": "≤", r"\ge": "≥",
    r"\neq": "≠", r"\ne": "≠",
    r"\sum": "Σ", r"\prod": "Π", r"\int": "∫",
    r"\rightarrow": "→", r"\to": "→",
    r"\left": "", r"\right": "",
}


def _unicode_math(expr: str) -> str:
    """Best-effort LaTeX -> plain Unicode for when no TeX toolchain exists.

    Handles the constructs the LLM actually emits (\\cdot, \\frac, ^{...},
    _{...}, single-char scripts) so formulas like ``N = N_0 \\cdot 2^t`` read
    as ``N = N₀ · 2ᵗ`` instead of showing raw LaTeX source on screen.
    """
    result = expr
    result = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"\1/\2", result)
    for command, symbol in _LATEX_SYMBOLS.items():
        result = result.replace(command, symbol)

    def _script(match: re.Match[str], table: dict[str, str]) -> str:
        content = match.group(1) if match.group(1) is not None else match.group(2)
        return "".join(table.get(ch, ch) for ch in content)

    result = re.sub(
        r"\^\{([^{}]*)\}|\^(\w)", lambda m: _script(m, _SUPERSCRIPT_MAP), result
    )
    result = re.sub(
        r"_\{([^{}]*)\}|_(\w)", lambda m: _script(m, _SUBSCRIPT_MAP), result
    )
    # Anything LaTeX-ish that survived would render as literal source; drop it.
    result = re.sub(r"\\[A-Za-z]+", "", result)
    result = result.replace("{", "").replace("}", "")
    return " ".join(result.split())


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
    scale *= _portrait_scale()
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
            segments = [{"type": "title_card", "title": spec.get("title") or "Math"}]

        total = _target_duration()
        default_slot = total / max(1, len(segments))
        fade_time = 0.3
        intro_time = 0.9
        write_time = 1.2
        outro_time = 0.35

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
            "squares_transform": self._squares_transform,
            "area_grid": self._area_grid,
        }
        create_types = {
            "axes_plot",
            "number_line",
            "right_triangle",
            "squares_on_sides",
            "pythagorean_triple",
            "squares_transform",
            "area_grid",
        }
        # Post-intro animations that play out INSIDE a segment's time slot.
        animators: dict[str, Callable[[dict[str, Any], VGroup, float], float]] = {
            "squares_transform": self._animate_squares_transform,
        }

        # Each segment appears at its absolute start time (matched to the
        # narration by apply_subtitle_timing); the current visual simply holds
        # until the next start. Without spec starts, fall back to even slots.
        current = None
        elapsed = 0.0
        prev_start = 0.0
        for index, segment in enumerate(segments):
            seg_type = str(segment.get("type", "title_card"))

            raw_start = segment.get("start")
            start = (
                float(raw_start)
                if raw_start is not None
                else index * default_slot
            )
            start = max(start, prev_start)
            prev_start = start

            if seg_type == "highlight":
                # The narration is referring back to what is already on
                # screen: pulse it instead of replacing it.
                if current is None:
                    continue
                if start > elapsed:
                    self.wait(start - elapsed)
                    elapsed = start
                self.play(
                    Indicate(current, scale_factor=1.06, color=self.accent),
                    run_time=1.2,
                )
                elapsed += 1.2
                continue

            builder = builders.get(seg_type, self._title_card)
            try:
                mobject = builder(segment)
            except Exception:
                # Surface the failure in the manim CLI output (captured by
                # render_manim_video) and keep the previous visual on screen
                # rather than flashing a broken placeholder.
                print(
                    f"[manim_templates] segment {index} ({seg_type}) failed to build:",
                    flush=True,
                )
                traceback.print_exc()
                continue

            if start > elapsed:
                self.wait(start - elapsed)
                elapsed = start

            if current is not None:
                self.play(FadeOut(current), run_time=fade_time)
                elapsed += fade_time
            if seg_type in create_types:
                self.play(Create(mobject), run_time=intro_time)
                elapsed += intro_time
            else:
                # Text and equations appear as if written by hand while the
                # narration introduces them.
                self.play(Write(mobject), run_time=write_time)
                elapsed += write_time
            current = mobject

            animator = animators.get(seg_type)
            if animator is not None:
                raw_duration = segment.get("duration")
                slot = (
                    float(raw_duration)
                    if raw_duration is not None
                    else default_slot
                )
                budget = start + slot - elapsed
                try:
                    elapsed += animator(segment, mobject, max(0.0, budget))
                except Exception:
                    print(
                        f"[manim_templates] segment {index} ({seg_type}) "
                        "animation failed:",
                        flush=True,
                    )
                    traceback.print_exc()

        if current is None:
            # Every builder failed; render a safe title card instead of a
            # black video so the task still produces something usable.
            fallback = self._title_card({"title": spec.get("title") or "Math"})
            self.play(Write(fallback), run_time=intro_time)
            elapsed += intro_time
            current = fallback

        # Hold the final visual so the render covers the full narration.
        tail = total - elapsed - outro_time
        if tail > 0:
            self.wait(tail)
        self.play(FadeOut(current), run_time=outro_time)

    # --- helpers -----------------------------------------------------------
    def _math(self, expr: str, **kwargs: Any):
        if _HAS_MATHTEX:
            try:
                return MathTex(expr, **kwargs)
            except Exception:
                pass
        kwargs.setdefault("font_size", kwargs.get("font_size", 56))
        return Text(_unicode_math(expr), **kwargs)

    def _fit(
        self,
        mobject,
        max_width: float | None = None,
        max_height: float | None = None,
    ):
        # At a portrait resolution Manim keeps frame_height = 8.0 and derives
        # frame_width from the aspect: 8 * (1080/1920) = 4.5 units. Anything
        # wider than that is cropped off-screen, so the caps must respect the
        # visible frame, not the landscape defaults.
        if _is_portrait():
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
        if _is_portrait():
            mobject.shift(UP * 0.85)
            # Burned-in subtitles are anchored at 78% of the frame height and
            # a three-line box reaches up to about y = -1.7; keep a margin so
            # bottom labels never sit behind the subtitle background.
            subtitle_top = -1.4
            bottom = float(mobject.get_bottom()[1])
            if bottom < subtitle_top:
                mobject.shift(UP * (subtitle_top - bottom))
            top_limit = 3.8
            top = float(mobject.get_top()[1])
            if top > top_limit:
                mobject.shift(DOWN * (top - top_limit))
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

        def _with_step(bounds: list) -> list[float]:
            lo, hi = float(bounds[0]), float(bounds[1])
            if hi <= lo:
                hi = lo + 1.0
            # Manim's default tick step is 1: an LLM range like [0, 1e13]
            # would allocate trillions of tick marks and OOM the render.
            # Aim for ~8 ticks whatever the span.
            return [lo, hi, max((hi - lo) / 8.0, 1e-6)]

        axes = Axes(
            x_range=_with_step(x_range),
            y_range=_with_step(y_range),
            axis_config={"color": self.text_color, "include_tip": True},
        )
        group = VGroup(axes)
        expr = segment.get("function")
        if expr:
            fn = _safe_math_fn(str(expr))
            # Manim does not clip graphs to the axes box: a fast-growing
            # function (2**x over [0, 30] with y capped at 32) draws a path
            # thousands of units tall, and _fit then shrinks the axes to a
            # sliver. Restrict the plot domain to where the curve stays
            # within the visible y-range.
            x_min, x_max = float(x_range[0]), float(x_range[1])
            y_min, y_max = float(y_range[0]), float(y_range[1])
            margin = 0.05 * (y_max - y_min)
            samples = 256
            xs = [
                x_min + (x_max - x_min) * i / (samples - 1)
                for i in range(samples)
            ]
            visible = []
            for x in xs:
                try:
                    y = float(fn(x))
                except Exception:
                    continue
                if math.isfinite(y) and y_min - margin <= y <= y_max + margin:
                    visible.append(x)
            plot_range = (
                [min(visible), max(visible)] if len(visible) >= 2 else [x_min, x_max]
            )
            graph = axes.plot(fn, x_range=plot_range, color=self.accent)
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
        # Skip captions like "c = 5" that just repeat a side label already
        # drawn on the figure.
        if caption and re.fullmatch(
            r"[abc]\s*=\s*[\d.]+", str(caption).strip(), flags=re.IGNORECASE
        ):
            caption = None
        if caption:
            title = Text(str(caption), color=self.accent, font_size=40)
            title.next_to(group, UP, buff=0.6)
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
            Text(f"a²={area_a}", color=self.text_color, font_size=32).move_to(sq_a.get_center()),
            Text(f"b²={area_b}", color=self.text_color, font_size=32).move_to(sq_b.get_center()),
            Text(f"c²={area_c}", color=self.text_color, font_size=32).move_to(sq_c.get_center()),
        )
        group = VGroup(triangle, sq_a, sq_b, sq_c, labels)
        title = segment.get("title")
        if title:
            header = Text(str(title), color=self.accent, font_size=42)
            # Position relative to the diagram, not the frame edge: _fit
            # recenters the whole group, so edge-anchored headers end up on
            # top of the figure.
            header.next_to(group, UP, buff=0.55)
            group.add(header)
        return self._fit(group, max_width=10.5, max_height=9.0)

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
            font_size=48,
            weight="BOLD",
        )
        summary.next_to(group, DOWN, buff=0.5)
        group.add(summary)
        return self._fit(group, max_width=10.5, max_height=9.2)

    def _squares_transform(self, segment: dict[str, Any]) -> VGroup:
        """Triangle with squares where the leg squares visibly fill c²."""
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
        sq_c = _square_on_edge(p0, p2, p1, self.accent, fill_opacity=0.08)
        area_a, area_b = int(a * a), int(b * b)
        area_c = area_a + area_b
        labels = VGroup(
            Text(f"a²={area_a}", color=self.text_color, font_size=32).move_to(
                sq_a.get_center()
            ),
            Text(f"b²={area_b}", color=self.text_color, font_size=32).move_to(
                sq_b.get_center()
            ),
        )

        # Split c² into two strips whose areas are exactly a² and b² (the
        # classic similar-triangle decomposition). They are built invisible so
        # _fit positions them with the rest of the group; the animator morphs
        # ghost copies of the leg squares onto them.
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
            color=self.accent,
            font_size=48,
            weight="BOLD",
        )
        summary.set_opacity(0.0)

        group = VGroup(triangle, sq_a, sq_b, sq_c, strip_a, strip_b, labels)
        summary.next_to(group, DOWN, buff=0.5)
        group.add(summary)
        title = segment.get("title")
        if title:
            header = Text(str(title), color=self.accent, font_size=42)
            header.next_to(group, UP, buff=0.55)
            group.add(header)
        self._fit(group, max_width=10.5, max_height=9.2)
        group.transform_parts = {
            "sq_a": sq_a,
            "sq_b": sq_b,
            "strip_a": strip_a,
            "strip_b": strip_b,
            "summary": summary,
        }
        return group

    def _animate_squares_transform(
        self, segment: dict[str, Any], group: VGroup, budget: float
    ) -> float:
        """Slide copies of the leg squares onto c², then reveal the sum.

        Plays within ``budget`` seconds and returns the time consumed so the
        scene scheduler keeps segment starts aligned with the narration.
        """
        parts = getattr(group, "transform_parts", None)
        if not parts or budget < 2.5:
            return 0.0
        consumed = 0.0

        pause = min(0.8, budget * 0.15)
        if pause > 0:
            self.wait(pause)
            consumed += pause

        move_time = min(1.3, (budget - consumed) * 0.3)
        for src_key, dst_key in (("sq_a", "strip_a"), ("sq_b", "strip_b")):
            ghost = parts[src_key].copy()
            target = (
                parts[dst_key]
                .copy()
                .set_stroke(self.accent, width=2, opacity=1.0)
                .set_fill(self.accent, opacity=0.45)
            )
            self.play(Transform(ghost, target), run_time=move_time)
            consumed += move_time
            # play() left the ghost as a top-level scene mobject; re-parent it
            # into the group so the segment crossfade fades it out too.
            self.remove(ghost)
            group.add(ghost)

        summary = parts["summary"]
        if budget - consumed >= 0.8:
            self.play(summary.animate.set_opacity(1.0), run_time=0.8)
            consumed += 0.8
        return consumed

    def _area_grid(self, segment: dict[str, Any]) -> VGroup:
        """n×n unit-square grid illustrating side length squared = area."""
        n = int(segment.get("side") or segment.get("side_a") or 3)
        n = max(2, min(n, 6))
        cell = 0.48 * (_portrait_scale() / 1.75)
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
            f"{n} × {n}  area = {area}",
            color=self.text_color,
            font_size=44,
            weight="BOLD",
        )
        label.next_to(grid, DOWN, buff=0.45)
        group = VGroup(grid, label)
        title = segment.get("title") or segment.get("caption")
        if title:
            header = Text(str(title), color=self.accent, font_size=38)
            header.next_to(group, UP, buff=0.5)
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
