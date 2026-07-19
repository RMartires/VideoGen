"""P2 dynamics types: state_vector, collision_pi, parallax_demo."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from manim import (
    DOWN,
    Dot,
    LEFT,
    Line,
    RIGHT,
    Square,
    Text,
    UP,
    UpdateFromAlphaFunc,
    VGroup,
)

from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.core.transforms import make_plane
from app.services.manim.segments.base import SegmentDef


# --- state_vector: a point orbits phase space while bars track (x, v) --------
def build_state_vector(scene, segment: dict[str, Any]) -> VGroup:
    plane = make_plane([-2, 2], [-2, 2])
    dot = Dot(plane.c2p(1.5, 0.0), radius=0.09, color=scene.accent)
    group = VGroup(plane, dot)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(plane, UP, buff=0.4)
        group.add(shell)
    group = fit(group, max_height=5.5)
    group.anim_shell = shell
    group.state_parts = {"plane": plane, "dot": dot, "radius": 1.5}
    return group


def animate_state_vector(scene, segment, group, budget: float) -> float:
    parts = getattr(group, "state_parts", None) or {}
    plane, dot = parts.get("plane"), parts.get("dot")
    if plane is None or dot is None or budget < 1.5:
        return idle_pulses(scene, group, budget)
    r = parts.get("radius", 1.5)

    def _update(mob, alpha: float) -> None:
        theta = alpha * 2 * math.pi
        # Harmonic oscillator: position on x, velocity on y; circle orbit.
        mob.move_to(plane.c2p(r * math.cos(theta), -r * math.sin(theta)))

    orbit_t = min(4.0, budget * 0.75)
    scene.play(UpdateFromAlphaFunc(dot, _update), run_time=orbit_t)
    consumed = orbit_t
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- collision_pi: blocks bounce off a wall (counting collisions gives pi) ---
def build_collision_pi(scene, segment: dict[str, Any]) -> VGroup:
    floor = Line(LEFT * 3.2, RIGHT * 3.2, color=scene.text_color, stroke_width=2)
    wall = Line(
        floor.get_start(),
        floor.get_start() + UP * 1.8,
        color=scene.text_color,
        stroke_width=3,
    )
    big = Square(side_length=0.9, color=scene.accent, fill_opacity=0.4)
    big.next_to(floor, UP, buff=0).shift(RIGHT * 2.0)
    small = Square(side_length=0.5, color=scene.text_color, fill_opacity=0.4)
    small.next_to(floor, UP, buff=0).shift(RIGHT * 0.4)
    counter = Text("0", color=scene.accent, font_size=42, weight="BOLD")
    counter.next_to(wall, UP + RIGHT, buff=0.25)
    group = VGroup(floor, wall, big, small, counter)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(group, UP, buff=0.5)
        group.add(shell)
    group = fit(group, max_height=5.0)
    group.anim_shell = shell
    group.collision_parts = {
        "big": big,
        "small": small,
        "counter": counter,
        "wall": wall,
    }
    return group


def animate_collision_pi(scene, segment, group, budget: float) -> float:
    from manim import Transform

    parts = getattr(group, "collision_parts", None) or {}
    big, small = parts.get("big"), parts.get("small")
    counter, wall = parts.get("counter"), parts.get("wall")
    if big is None or small is None or budget < 1.5:
        return idle_pulses(scene, group, budget)
    wall_x = float(wall.get_center()[0]) + float(small.width) / 2 + 0.05
    consumed = 0.0
    count = 0
    per_hit = min(0.9, max(0.45, budget / 8.0))
    # Cartoon schedule: big block drifts left; small block shuttles
    # wall <-> big, incrementing the counter each bounce.
    while consumed + 2 * per_hit <= budget - 0.3 and count < 6:
        big_x = float(big.get_center()[0])
        scene.play(
            small.animate.set_x(wall_x),
            big.animate.set_x(big_x - 0.25),
            run_time=per_hit,
        )
        count += 1
        new_counter = Text(
            str(count), color=scene.accent, font_size=42, weight="BOLD"
        )
        new_counter.move_to(counter.get_center())
        scene.play(
            small.animate.set_x(float(big.get_center()[0]) - 0.7),
            Transform(counter, new_counter),
            run_time=per_hit,
        )
        count += 1
        consumed += 2 * per_hit
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


# --- parallax_demo: near and far dots slide at different speeds --------------
def build_parallax_demo(scene, segment: dict[str, Any]) -> VGroup:
    far = VGroup(
        *(
            Dot(np.array([x, 1.1, 0.0]), radius=0.05, color=scene.text_color)
            for x in (-2.4, -0.8, 0.8, 2.4)
        )
    )
    near = VGroup(
        *(
            Dot(np.array([x, -0.9, 0.0]), radius=0.10, color=scene.accent)
            for x in (-1.8, 0.0, 1.8)
        )
    )
    horizon = Line(LEFT * 3.2, RIGHT * 3.2, color=scene.text_color, stroke_width=1)
    horizon.shift(UP * 0.15)
    group = VGroup(horizon, far, near)
    shell = None
    title = segment.get("title") or segment.get("caption")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(group, UP, buff=0.5)
        group.add(shell)
    group = fit(group, max_height=5.0)
    group.anim_shell = shell
    group.parallax_parts = {"far": far, "near": near}
    return group


def animate_parallax_demo(scene, segment, group, budget: float) -> float:
    parts = getattr(group, "parallax_parts", None) or {}
    far, near = parts.get("far"), parts.get("near")
    if far is None or near is None or budget < 1.5:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    sweep_t = min(2.2, max(1.0, budget * 0.4))
    for direction in (LEFT, RIGHT):
        if consumed + sweep_t > budget:
            break
        scene.play(
            far.animate.shift(direction * 0.5),
            near.animate.shift(direction * 1.6),
            run_time=sweep_t,
        )
        consumed += sweep_t
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENTS = [
    SegmentDef(
        type="state_vector",
        category="niche",
        build=build_state_vector,
        animate=animate_state_vector,
        intro="shell_fade",
    ),
    SegmentDef(
        type="collision_pi",
        category="niche",
        build=build_collision_pi,
        animate=animate_collision_pi,
        intro="shell_fade",
    ),
    SegmentDef(
        type="parallax_demo",
        category="niche",
        build=build_parallax_demo,
        animate=animate_parallax_demo,
        intro="shell_fade",
    ),
]
