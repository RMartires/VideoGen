"""grid_sieve (highlight multiples) and grid_toggle (door-puzzle passes)."""

from __future__ import annotations

from typing import Any

from manim import Text, UP, VGroup

from app.services.manim.core.grids import numbered_grid
from app.services.manim.core.holds import idle_pulses
from app.services.manim.core.layout import fit
from app.services.manim.segments.base import SegmentDef


def _build_numbered(scene, segment: dict[str, Any], default_n: int) -> VGroup:
    n = max(6, min(36, int(segment.get("count") or default_n)))
    cols = 6
    grid, entries = numbered_grid(
        n, cols, cell=0.62, color=scene.accent, text_color=scene.text_color
    )
    group = VGroup(grid)
    shell = None
    title = segment.get("title")
    if title:
        shell = Text(str(title), color=scene.accent, weight="BOLD", font_size=40)
        shell.next_to(grid, UP, buff=0.5)
        group.add(shell)
    group = fit(group)
    group.anim_shell = shell
    group.grid_entries = entries
    return group


def build_sieve(scene, segment: dict[str, Any]) -> VGroup:
    group = _build_numbered(scene, segment, default_n=30)
    group.sieve_step = max(2, int(segment.get("highlight_multiples_of") or 2))
    return group


def animate_sieve(scene, segment: dict[str, Any], group: VGroup, budget: float) -> float:
    entries = getattr(group, "grid_entries", None) or []
    step = getattr(group, "sieve_step", 2)
    targets = [entries[i] for i in range(step - 1, len(entries), step)]
    if not targets:
        return idle_pulses(scene, group, budget)
    consumed = 0.0
    per = min(0.6, max(0.15, budget / max(1, len(targets) + 1)))
    for entry in targets:
        if consumed + per > budget:
            break
        square = entry[0]
        scene.play(
            square.animate.set_fill(scene.accent, opacity=0.45), run_time=per
        )
        consumed += per
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


def build_toggle(scene, segment: dict[str, Any]) -> VGroup:
    return _build_numbered(scene, segment, default_n=12)


def animate_toggle(scene, segment: dict[str, Any], group: VGroup, budget: float) -> float:
    """Door-puzzle passes: pass k toggles every k-th cell open/closed."""
    entries = getattr(group, "grid_entries", None) or []
    if not entries:
        return idle_pulses(scene, group, budget)
    n = len(entries)
    open_state = [False] * n
    consumed = 0.0
    passes = min(4, n)
    per_pass = max(0.4, budget / (passes + 1))
    for k in range(1, passes + 1):
        if consumed + per_pass > budget:
            break
        anims = []
        for i in range(k - 1, n, k):
            open_state[i] = not open_state[i]
            square = entries[i][0]
            opacity = 0.45 if open_state[i] else 0.0
            anims.append(square.animate.set_fill(scene.accent, opacity=opacity))
        scene.play(*anims, run_time=per_pass)
        consumed += per_pass
    if budget - consumed > 0.05:
        consumed += idle_pulses(scene, group, budget - consumed)
    return consumed


SEGMENTS = [
    SegmentDef(
        type="grid_sieve",
        category="counting",
        build=build_sieve,
        animate=animate_sieve,
        intro="shell_fade",
    ),
    SegmentDef(
        type="grid_toggle",
        category="counting",
        build=build_toggle,
        animate=animate_toggle,
        intro="shell_fade",
    ),
]
