"""MathExplainerScene: the thin construct loop over registered segments.

Executed *standalone* by the ``manim`` CLI via the ``manim_templates.py`` shim;
never imported by the running app, so importing manim at module load is safe
even though Manim is an optional dependency.

The scene reads a validated JSON "scene spec" (path in ``MANIM_SPEC_PATH``) and
a target duration (``MANIM_TARGET_DURATION`` seconds), then renders each
segment with a fixed, parameterized template from the registry. The LLM only
ever produces the JSON data; no arbitrary code from the spec is executed. The
single exception is plot ``function`` strings, which are evaluated in a
locked-down namespace in ``core.math_safe.safe_math_fn``.
"""

from __future__ import annotations

import os
import traceback
from typing import Any

from manim import (
    Circumscribe,
    Create,
    FadeIn,
    FadeOut,
    Indicate,
    ReplacementTransform,
    Scene,
    UP,
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
# This MUST run at import time, before the CLI instantiates the Scene class.
_frame_aspect = float(os.environ.get("MANIM_FRAME_ASPECT", "0") or 0)
if _frame_aspect > 0:
    manim_config.frame_width = manim_config.frame_height * _frame_aspect

from app.services.manim import registry  # noqa: E402
from app.services.manim.core.env import spec_from_env, target_duration  # noqa: E402
from app.services.manim.core.holds import animate_hold  # noqa: E402
from app.services.manim.core.style import (  # noqa: E402
    DEFAULT_ACCENT,
    DEFAULT_BACKGROUND,
    DEFAULT_TEXT,
)


class MathExplainerScene(Scene):
    def construct(self) -> None:
        spec = spec_from_env()
        self.accent = spec.get("accent_color") or DEFAULT_ACCENT
        self.text_color = spec.get("text_color") or DEFAULT_TEXT
        self.camera.background_color = (
            spec.get("background_color") or DEFAULT_BACKGROUND
        )

        segments = spec.get("segments") or []
        if not segments:
            segments = [{"type": "title_card", "title": spec.get("title") or "Math"}]

        total = target_duration()
        default_slot = total / max(1, len(segments))
        fade_time = 0.3
        intro_time = 0.9
        write_time = 1.2

        current = None
        elapsed = 0.0
        prev_start = 0.0
        highlight_count = 0
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

            raw_duration = segment.get("duration")
            slot = float(raw_duration) if raw_duration is not None else default_slot
            if index + 1 < len(segments):
                next_raw = segments[index + 1].get("start")
                if next_raw is not None:
                    slot_end = float(next_raw)
                else:
                    slot_end = start + slot
            else:
                slot_end = total
            slot_end = min(max(slot_end, start + 0.5), total)

            if seg_type == "highlight":
                # Pseudo-segment: pulses whatever is already on screen; it has
                # no builder and is handled inline by the loop.
                if current is None:
                    continue
                if start > elapsed:
                    elapsed += animate_hold(
                        self, current, segment, seg_type, start - elapsed
                    )
                pulse_time = 1.0
                # Alternate Indicate / Circumscribe so repeated references to
                # the same visual don't all look identical.
                if highlight_count % 2 == 0:
                    self.play(
                        Indicate(current, scale_factor=1.06, color=self.accent),
                        run_time=pulse_time,
                    )
                else:
                    self.play(
                        Circumscribe(current, color=self.accent, buff=0.15),
                        run_time=pulse_time,
                    )
                highlight_count += 1
                elapsed += pulse_time
                hold = slot_end - elapsed
                if hold > 0:
                    elapsed += animate_hold(self, current, segment, seg_type, hold)
                continue

            defn = registry.get(seg_type) or registry.get("title_card")
            try:
                mobject = defn.build(self, segment)
            except Exception:
                print(
                    f"[manim scene] segment {index} ({seg_type}) failed to build:",
                    flush=True,
                )
                traceback.print_exc()
                continue

            if start > elapsed:
                elapsed += animate_hold(
                    self, current, segment, seg_type, start - elapsed
                )

            continues = bool(segment.get("continues_from_previous"))
            prev_type = (
                str(segments[index - 1].get("type", ""))
                if index > 0
                else ""
            )
            if continues and prev_type == "highlight" and index > 1:
                prev_type = str(segments[index - 2].get("type", ""))
            compatible = continues and (
                prev_type,
                seg_type,
            ) in {
                ("counter_doubling", "counter_doubling"),
                ("counter_doubling", "dot_grid_doubling"),
                ("growth_bars", "dot_grid_doubling"),
                ("growth_bars", "quote_card"),
                ("dot_grid_doubling", "quote_card"),
            }
            if current is not None and not compatible:
                self.play(FadeOut(current), run_time=fade_time)
                elapsed += fade_time
                elapsed += self._play_intro(defn.intro, mobject, intro_time, write_time)
            elif current is not None and compatible:
                cross_t = 0.35
                self.play(ReplacementTransform(current, mobject), run_time=cross_t)
                elapsed += cross_t
            else:
                elapsed += self._play_intro(defn.intro, mobject, intro_time, write_time)
            current = mobject

            hold_budget = max(0.0, slot_end - elapsed)
            animator = defn.animate
            if hold_budget > 0 and animator is not None:
                try:
                    elapsed += animator(self, segment, mobject, hold_budget)
                except Exception:
                    print(
                        f"[manim scene] segment {index} ({seg_type}) "
                        "animation failed:",
                        flush=True,
                    )
                    traceback.print_exc()
                    elapsed += animate_hold(
                        self, current, segment, seg_type, hold_budget
                    )
            elif hold_budget > 0:
                elapsed += animate_hold(
                    self, current, segment, seg_type, hold_budget
                )

        outro_time = 0.35
        if current is None:
            title_def = registry.get("title_card")
            fallback = title_def.build(
                self, {"title": spec.get("title") or "Math"}
            )
            self.play(Write(fallback), run_time=intro_time)
            elapsed += intro_time
            current = fallback

        tail = total - elapsed - outro_time
        if tail > 0:
            elapsed += animate_hold(self, current, {}, "title_card", tail)
        self.play(FadeOut(current), run_time=outro_time)

    def _play_intro(
        self, intro: str, mobject: VGroup, intro_time: float, write_time: float
    ) -> float:
        """Play the segment's entry animation; returns seconds consumed."""
        if intro == "stagger":
            shell = getattr(mobject, "stagger_shell", None)
            if shell is not None:
                self.play(Write(shell), run_time=0.7)
                return 0.7
            if getattr(mobject, "stagger_items", None):
                # Staggered items start hidden; the segment animator writes them.
                return 0.0
            self.play(Write(mobject), run_time=write_time)
            return write_time
        if intro == "plot":
            parts = getattr(mobject, "plot_parts", None) or {}
            intro_group = VGroup(parts.get("axes"))
            label = parts.get("label")
            if label is not None:
                intro_group.add(label)
            self.play(Create(intro_group), run_time=intro_time)
            return intro_time
        if intro == "create":
            self.play(Create(mobject), run_time=intro_time)
            return intro_time
        if intro == "shell_fade":
            # Fade the whole group: children built with opacity 0 (pop texts,
            # unrevealed rows) stay hidden, while static parts like bar labels
            # appear immediately instead of never being added to the scene.
            self.play(FadeIn(mobject, shift=UP * 0.1), run_time=0.6)
            return 0.6
        if intro == "grid_fade":
            shell = getattr(mobject, "grid_shell", None)
            if shell is not None:
                self.play(FadeIn(shell, shift=UP * 0.1), run_time=0.6)
                return 0.6
            self.play(Create(mobject), run_time=intro_time)
            return intro_time
        if intro == "quote_fade":
            lines = getattr(mobject, "quote_lines", None) or []
            if lines:
                for line in lines:
                    self.play(FadeIn(line, shift=UP * 0.08), run_time=0.35)
                return 0.35 * len(lines)
            self.play(FadeIn(mobject, shift=UP * 0.1), run_time=0.6)
            return 0.6
        self.play(Write(mobject), run_time=write_time)
        return write_time
