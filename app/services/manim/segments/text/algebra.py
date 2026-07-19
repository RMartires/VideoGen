"""P1 text types: algebra_steps, function_mapping, labeled_braces, quote_card."""

from __future__ import annotations

from typing import Any

from manim import (
    Arrow,
    Brace,
    Create,
    DOWN,
    RIGHT,
    Text,
    UP,
    VGroup,
)

from app.services.manim.core.animation import stagger_reveal
from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.core.text import math_mobject
from app.services.manim.segments.base import SegmentDef


# --- algebra_steps: derivation lines revealed one at a time -----------------
def build_algebra_steps(scene, segment: dict[str, Any]) -> VGroup:
    lines = segment.get("equations") or segment.get("steps") or ["a = b"]
    group = VGroup()
    shell = None
    title = segment.get("title")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=44)
        group.add(shell)
    items = []
    for line in lines[:6]:
        mob = math_mobject(str(line), color=scene.text_color, font_size=48)
        mob.set_opacity(0)
        items.append(mob)
        group.add(mob)
    group.arrange(DOWN, buff=0.45)
    group = fit(group)
    group.stagger_shell = shell
    group.stagger_items = items
    return group


def animate_stagger(scene, segment: dict[str, Any], group: VGroup, budget: float) -> float:
    return stagger_reveal(scene, group, getattr(group, "stagger_items", []) or [], budget)


# --- function_mapping: inputs flying to outputs ------------------------------
def build_function_mapping(scene, segment: dict[str, Any]) -> VGroup:
    values = segment.get("values") or [1, 2, 3]
    values = [float(v) for v in values[:4]]
    labels = segment.get("labels") or [str(segment.get("label") or "x → 2x")]
    rule = str(labels[0])
    inputs = VGroup()
    outputs = VGroup()
    arrows: list[Arrow] = []
    rows = VGroup()
    for v in values:
        vin = Text(
            f"{v:g}", color=scene.text_color, font_size=40
        )
        try:
            # The rule text is only cosmetic; the numeric mapping doubles by
            # default, matching the sample rule shown.
            vout_val = v * 2
        except Exception:
            vout_val = v
        vout = Text(f"{vout_val:g}", color=scene.accent, font_size=40)
        vout.next_to(vin, RIGHT, buff=1.8)
        arrow = Arrow(
            vin.get_right(), vout.get_left(), buff=0.15,
            color=scene.accent, stroke_width=3,
        )
        arrow.set_opacity(0)
        vout.set_opacity(0)
        row = VGroup(vin, arrow, vout)
        rows.add(row)
        inputs.add(vin)
        outputs.add(vout)
        arrows.append(arrow)
    rows.arrange(DOWN, buff=0.5)
    header = Text(rule, color=scene.accent, weight="BOLD", font_size=44)
    header.next_to(rows, UP, buff=0.55)
    group = VGroup(header, rows)
    group = fit(group)
    group.anim_shell = header
    group.mapping_pairs = [
        (arrow, out) for arrow, out in zip(arrows, outputs)
    ]
    return group


def animate_function_mapping(
    scene, segment: dict[str, Any], group: VGroup, budget: float
) -> float:
    pairs = getattr(group, "mapping_pairs", None) or []
    if not pairs:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    per = min(1.0, max(0.4, budget / (len(pairs) + 1)))
    for arrow, out in pairs:
        if consumed + per > budget:
            break
        arrow.set_opacity(1)
        scene.play(Create(arrow), run_time=per * 0.5)
        scene.play(out.animate.set_opacity(1), run_time=per * 0.5)
        consumed += per
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- labeled_braces: equation with braces naming each part -------------------
def build_labeled_braces(scene, segment: dict[str, Any]) -> VGroup:
    expr = (segment.get("equations") or ["a^2 + b^2 = c^2"])[0]
    equation = math_mobject(str(expr), color=scene.text_color, font_size=56)
    labels = segment.get("labels") or ["left side", "right side"]
    brace_groups = []
    group = VGroup(equation)
    n = min(2, len(labels))
    for i in range(n):
        # First label braces below, second above the equation.
        direction = DOWN if i == 0 else UP
        brace = Brace(equation, direction, color=scene.accent)
        text = Text(str(labels[i]), color=scene.accent, font_size=30)
        text.next_to(brace, direction, buff=0.15)
        brace_pair = VGroup(brace, text)
        brace_pair.set_opacity(0)
        brace_groups.append(brace_pair)
        group.add(brace_pair)
    shell = None
    title = segment.get("title")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=42)
        shell.next_to(group, UP, buff=0.8)
        group.add(shell)
    group = fit(group)
    group.anim_shell = shell
    group.brace_items = brace_groups
    return group


def animate_labeled_braces(
    scene, segment: dict[str, Any], group: VGroup, budget: float
) -> float:
    braces = getattr(group, "brace_items", None) or []
    if not braces:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    per = min(1.2, max(0.5, budget / (len(braces) + 1)))
    for pair in braces:
        if consumed + per > budget:
            break
        scene.play(pair.animate.set_opacity(1), run_time=per)
        consumed += per
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- quote_card: a styled aphorism ------------------------------------------
def build_quote_card(scene, segment: dict[str, Any]) -> VGroup:
    quote = str(segment.get("caption") or segment.get("title") or "Mathematics")
    words = quote.split()
    lines: list[str] = []
    line: list[str] = []
    for word in words:
        line.append(word)
        if len(" ".join(line)) > 24:
            lines.append(" ".join(line))
            line = []
    if line:
        lines.append(" ".join(line))
    body = VGroup(
        *(
            Text(text, color=scene.text_color, font_size=44, weight="BOLD")
            for text in lines[:4]
        )
    )
    body.arrange(DOWN, buff=0.3)
    group = VGroup(body)
    group.quote_lines = list(body)
    attribution = segment.get("subtitle") or segment.get("label")
    if attribution:
        who = Text(f"— {attribution}", color=scene.accent, font_size=32)
        who.next_to(body, DOWN, buff=0.5)
        group.add(who)
    return fit(group)


SEGMENTS = [
    SegmentDef(
        type="algebra_steps",
        category="text",
        build=build_algebra_steps,
        animate=animate_stagger,
        intro="stagger",
    ),
    SegmentDef(
        type="function_mapping",
        category="text",
        build=build_function_mapping,
        animate=animate_function_mapping,
        intro="shell_fade",
    ),
    SegmentDef(
        type="labeled_braces",
        category="text",
        build=build_labeled_braces,
        animate=animate_labeled_braces,
        intro="write",
    ),
    SegmentDef(
        type="quote_card",
        category="text",
        build=build_quote_card,
        intro="quote_fade",
    ),
]
