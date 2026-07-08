"""Render math-explainer visuals with Manim Community Edition.

Orchestration only: this module validates the LLM-produced scene spec and drives
the ``manim`` CLI in a locked-down subprocess. It deliberately does NOT
``import manim`` (an optional dependency) at load time, so it is always safe for
the app to import this module. The heavy Manim import happens in the standalone
scene file ``manim_templates.py`` executed by the CLI.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from typing import List, Optional

from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from app.models.schema import VideoAspect
from app.utils import utils

_TEMPLATES_MODULE = os.path.join(os.path.dirname(__file__), "manim_templates.py")
_SCENE_NAME = "MathExplainerScene"
_SEGMENT_TYPES = {
    "title_card",
    "equation_reveal",
    "step_by_step",
    "bullet_points",
    "axes_plot",
    "number_line",
    "right_triangle",
    "squares_on_sides",
    "pythagorean_triple",
    "area_grid",
}
# Hard ceiling for a single render so a bad spec cannot hang the worker.
_RENDER_TIMEOUT_SECONDS = 600


class Segment(BaseModel):
    type: str = "title_card"
    title: Optional[str] = None
    subtitle: Optional[str] = None
    caption: Optional[str] = None
    label: Optional[str] = None
    equations: Optional[List[str]] = None
    steps: Optional[List[str]] = None
    points: Optional[List[str]] = None
    function: Optional[str] = None
    x_range: Optional[List[float]] = None
    y_range: Optional[List[float]] = None
    side_a: Optional[float] = None
    side_b: Optional[float] = None
    side: Optional[int] = None


class SceneSpec(BaseModel):
    title: str = "Math"
    background_color: Optional[str] = None
    accent_color: Optional[str] = None
    text_color: Optional[str] = None
    segments: List[Segment] = Field(default_factory=list)


def default_spec(video_subject: str) -> SceneSpec:
    """A safe, always-renderable spec used when the LLM output is unusable."""
    subject = (video_subject or "Mathematics").strip() or "Mathematics"
    return SceneSpec(
        title=subject,
        segments=[
            Segment(type="title_card", title=subject, subtitle="A quick explainer"),
            Segment(type="right_triangle", side_a=3, side_b=4, caption="Right triangle"),
            Segment(type="squares_on_sides", side_a=3, side_b=4, title="Squares on each side"),
            Segment(type="area_grid", side=3, title="Area of side 3"),
            Segment(type="area_grid", side=4, title="Area of side 4"),
            Segment(
                type="pythagorean_triple",
                side_a=3,
                side_b=4,
            ),
            Segment(
                type="equation_reveal",
                caption="Core idea",
                equations=["a^2 + b^2 = c^2"],
            ),
        ],
    )


def validate_or_default(raw: object, video_subject: str = "") -> SceneSpec:
    """Coerce arbitrary LLM output into a valid SceneSpec, falling back safely."""
    try:
        if isinstance(raw, str):
            raw = json.loads(raw)
        spec = SceneSpec.model_validate(raw)
    except (ValidationError, ValueError, TypeError) as exc:
        logger.warning(f"invalid manim scene spec, using default: {exc}")
        return default_spec(video_subject)

    spec.segments = [s for s in spec.segments if s.type in _SEGMENT_TYPES]
    if not spec.segments:
        logger.warning("manim scene spec has no usable segments, using default")
        return default_spec(video_subject)
    return spec


def _resolution_for_aspect(aspect: VideoAspect) -> tuple[int, int]:
    # VideoAspect.to_resolution() returns (width, height) already oriented for
    # the aspect, so portrait 9:16 renders at 1080x1920 with no cropping.
    width, height = VideoAspect(aspect).to_resolution()
    return width, height


def render_manim_video(
    task_id: str,
    spec: SceneSpec,
    video_aspect: VideoAspect = VideoAspect.portrait,
    duration: float = 40.0,
    timeout: int = _RENDER_TIMEOUT_SECONDS,
) -> str:
    """Render ``spec`` to an mp4 and return its path.

    Raises RuntimeError on any failure so the caller can fail the task cleanly
    instead of proceeding with a missing material.
    """
    task_path = utils.task_dir(task_id)
    spec_path = os.path.join(task_path, "manim_spec.json")
    media_dir = os.path.join(task_path, "manim_media")
    output_name = "manim_scene"

    with open(spec_path, "w", encoding="utf-8") as handle:
        json.dump(spec.model_dump(), handle, ensure_ascii=False, indent=2)

    width, height = _resolution_for_aspect(video_aspect)

    env = os.environ.copy()
    env["MANIM_SPEC_PATH"] = spec_path
    env["MANIM_TARGET_DURATION"] = str(max(4.0, float(duration)))

    cmd = [
        sys.executable,
        "-m",
        "manim",
        "render",
        "-qm",
        "--format",
        "mp4",
        "--resolution",
        f"{width},{height}",
        "--media_dir",
        media_dir,
        "--output_file",
        output_name,
        _TEMPLATES_MODULE,
        _SCENE_NAME,
    ]

    logger.info(f"rendering manim scene: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            env=env,
            cwd=task_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Manim is not installed. Install it with `uv sync --extra manim` "
            "or `pip install manim` to use video_source='manim'."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"manim render timed out after {timeout}s") from exc

    if result.returncode != 0:
        logger.error(f"manim stdout:\n{result.stdout}")
        logger.error(f"manim stderr:\n{result.stderr}")
        raise RuntimeError(
            f"manim render failed with exit code {result.returncode}"
        )

    rendered = _find_rendered_mp4(media_dir, output_name)
    if not rendered:
        logger.error(f"manim stdout:\n{result.stdout}")
        raise RuntimeError("manim render produced no mp4 output")

    final_path = os.path.join(task_path, "manim_scene.mp4")
    shutil.copyfile(rendered, final_path)
    _cleanup_media(media_dir)
    logger.success(f"manim scene rendered: {final_path}")
    return final_path


def _find_rendered_mp4(media_dir: str, output_name: str) -> Optional[str]:
    if not os.path.isdir(media_dir):
        return None
    target = f"{output_name}.mp4"
    matches: list[str] = []
    for root, _dirs, files in os.walk(media_dir):
        for name in files:
            if name == target:
                matches.append(os.path.join(root, name))
    if not matches:
        return None
    # Prefer the highest-resolution copy if Manim wrote several.
    matches.sort(key=lambda p: os.path.getsize(p), reverse=True)
    return matches[0]


def _cleanup_media(media_dir: str) -> None:
    try:
        shutil.rmtree(media_dir, ignore_errors=True)
    except OSError as exc:  # pragma: no cover - best-effort cleanup
        logger.warning(f"failed to clean manim media dir {media_dir}: {exc}")
