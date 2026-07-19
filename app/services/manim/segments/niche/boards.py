"""P2 board/graph types: galton_board, network_flow, attention_arrows."""

from __future__ import annotations

import random
from typing import Any

import numpy as np
from manim import (
    Circle,
    Create,
    Dot,
    Indicate,
    Line,
    MoveAlongPath,
    RIGHT,
    Rectangle,
    Text,
    UP,
    VGroup,
    VMobject,
)

from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.segments.base import SegmentDef


# --- galton_board: balls bounce through pegs into a bell curve ---------------
def build_galton_board(scene, segment: dict[str, Any]) -> VGroup:
    rows = max(3, min(7, int(segment.get("rows") or 5)))
    spacing = 0.55
    pegs = VGroup()
    peg_rows: list[list[np.ndarray]] = []
    top = np.array([0.0, 1.8, 0.0])
    for r in range(rows):
        row_points = []
        for c in range(r + 1):
            point = top + np.array(
                [(c - r / 2) * spacing, -r * spacing * 0.8, 0.0]
            )
            pegs.add(Dot(point, radius=0.05, color=scene.text_color))
            row_points.append(point)
        peg_rows.append(row_points)

    bin_count = rows + 1
    bin_width = spacing * 0.9
    bins = VGroup()
    bin_floor = top[1] - rows * spacing * 0.8 - 0.5
    for c in range(bin_count):
        x = (c - rows / 2) * spacing
        wall = Rectangle(
            width=bin_width, height=0.08,
            color=scene.text_color, fill_opacity=0.5, stroke_width=1,
        )
        wall.move_to(np.array([x, bin_floor, 0.0]))
        bins.add(wall)

    group = VGroup(pegs, bins)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(group, UP, buff=0.45)
        group.add(shell)
    group = fit(group, max_height=5.5)
    group.anim_shell = shell
    group.galton_parts = {
        "peg_rows": peg_rows,
        "rows": rows,
        "spacing": spacing,
        "bin_floor": bin_floor,
        "top": top,
    }
    return group


def animate_galton_board(scene, segment, group, budget: float) -> float:
    parts = getattr(group, "galton_parts", None) or {}
    peg_rows = parts.get("peg_rows")
    if not peg_rows or budget < 1.5:
        return idle_pulses(scene, group, budget)
    rows = parts["rows"]
    spacing = parts["spacing"]
    bin_floor = parts["bin_floor"]
    top = parts["top"]
    rng = random.Random(11)

    stack_heights = [0] * (rows + 1)
    consumed = 0.0
    per_ball = min(1.1, max(0.6, budget / 6.0))
    while consumed + per_ball <= budget - 0.2:
        # Coin flip at each peg row; the bin index is the number of rights.
        steps = [rng.randint(0, 1) for _ in range(rows)]
        k = sum(steps)
        path = VMobject()
        points = [top + np.array([0.0, 0.4, 0.0])]
        rights = 0
        for r, step in enumerate(steps):
            rights += step
            x = (rights - (r + 1) / 2) * spacing
            points.append(top + np.array([x, -(r + 1) * spacing * 0.8, 0.0]))
        landing_x = (k - rows / 2) * spacing
        landing_y = bin_floor + 0.12 + stack_heights[k] * 0.14
        points.append(np.array([landing_x, landing_y, 0.0]))
        path.set_points_smoothly(points)
        stack_heights[k] += 1

        ball = Dot(points[0], radius=0.07, color=scene.accent)
        scene.add(ball)
        scene.play(MoveAlongPath(ball, path), run_time=per_ball)
        group.add(ball)
        consumed += per_ball
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- network_flow: pulses travel along the edges of a layered graph ----------
def build_network_flow(scene, segment: dict[str, Any]) -> VGroup:
    layers = max(2, min(4, int(segment.get("rows") or 3)))
    per_layer = max(2, min(4, int(segment.get("count") or 3)))
    node_positions: list[list[np.ndarray]] = []
    nodes = VGroup()
    for layer in range(layers):
        column = []
        x = (layer - (layers - 1) / 2) * 2.2
        for i in range(per_layer):
            y = (i - (per_layer - 1) / 2) * 1.3
            point = np.array([x, y, 0.0])
            nodes.add(
                Circle(radius=0.18, color=scene.text_color, stroke_width=2)
                .move_to(point)
            )
            column.append(point)
        node_positions.append(column)

    edges = VGroup()
    edge_lines: list[Line] = []
    for layer in range(layers - 1):
        for a in node_positions[layer]:
            for b in node_positions[layer + 1]:
                line = Line(
                    a, b, color=scene.text_color,
                    stroke_width=1.5, stroke_opacity=0.4,
                )
                edges.add(line)
                edge_lines.append(line)

    group = VGroup(edges, nodes)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(group, UP, buff=0.45)
        group.add(shell)
    group = fit(group, max_height=5.5)
    group.anim_shell = shell
    group.flow_parts = {"edges": edge_lines}
    return group


def animate_network_flow(scene, segment, group, budget: float) -> float:
    parts = getattr(group, "flow_parts", None) or {}
    edges = parts.get("edges") or []
    if not edges or budget < 1.0:
        return idle_pulses(scene, group, budget)
    rng = random.Random(7)
    consumed = 0.0
    per_wave = min(1.2, max(0.6, budget / 4.0))
    while consumed + per_wave <= budget - 0.2:
        picked = rng.sample(edges, k=min(4, len(edges)))
        dots = VGroup(
            *(
                Dot(line.get_start(), radius=0.06, color=scene.accent)
                for line in picked
            )
        )
        scene.add(dots)
        scene.play(
            *(
                MoveAlongPath(dot, line)
                for dot, line in zip(dots, picked)
            ),
            run_time=per_wave,
        )
        scene.remove(dots)
        consumed += per_wave
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- attention_arrows: a token attends to the rest of the sentence -----------
def build_attention_arrows(scene, segment: dict[str, Any]) -> VGroup:
    tokens = [str(t) for t in (segment.get("labels") or ["the", "cat", "sat", "here"])][:6]
    if len(tokens) < 2:
        tokens = ["the", "cat"]
    words = VGroup(
        *(Text(t, color=scene.text_color, font_size=34) for t in tokens)
    )
    words.arrange(RIGHT, buff=0.55)
    group = VGroup(words)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(words, UP, buff=1.4)
        group.add(shell)
    group = fit(group, max_height=5.0)
    group.anim_shell = shell
    group.attention_parts = {"words": list(words)}
    return group


def animate_attention_arrows(scene, segment, group, budget: float) -> float:
    parts = getattr(group, "attention_parts", None) or {}
    words = parts.get("words") or []
    if len(words) < 2 or budget < 1.5:
        return idle_pulses(scene, group, budget)
    rng = random.Random(3)
    consumed = 0.0
    per_query = min(1.6, max(0.9, budget / max(2, len(words))))
    arcs_on_screen: VGroup | None = None
    for q_idx in range(len(words)):
        if consumed + per_query > budget - 0.2:
            break
        query = words[q_idx]
        arcs = VGroup()
        for k_idx, key in enumerate(words):
            if k_idx == q_idx:
                continue
            weight = 0.25 + rng.random() * 0.75
            arc = Line(
                query.get_top() + UP * 0.05,
                key.get_top() + UP * 0.05,
                color=scene.accent,
                stroke_width=1.0 + 4.0 * weight,
                stroke_opacity=0.25 + 0.7 * weight,
                path_arc=-1.4,
            )
            arcs.add(arc)
        anims = [Create(arcs), Indicate(query, scale_factor=1.15, color=scene.accent)]
        if arcs_on_screen is not None:
            scene.remove(arcs_on_screen)
            group.remove(arcs_on_screen)
        scene.play(*anims, run_time=per_query)
        group.add(arcs)
        arcs_on_screen = arcs
        consumed += per_query
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENTS = [
    SegmentDef(
        type="galton_board",
        category="niche",
        build=build_galton_board,
        animate=animate_galton_board,
        intro="shell_fade",
    ),
    SegmentDef(
        type="network_flow",
        category="niche",
        build=build_network_flow,
        animate=animate_network_flow,
        intro="shell_fade",
    ),
    SegmentDef(
        type="attention_arrows",
        category="niche",
        build=build_attention_arrows,
        animate=animate_attention_arrows,
        intro="shell_fade",
    ),
]
