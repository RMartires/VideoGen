"""Render math-explainer visuals with Manim Community Edition.

Orchestration only: this module drives the ``manim`` CLI in a locked-down
subprocess. It deliberately does NOT ``import manim`` (an optional dependency)
at load time, so it is always safe for the app to import this module. The heavy
Manim import happens in the standalone scene shim ``manim_templates.py``
executed by the CLI, which in turn imports ``app.services.manim.scene``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from typing import Optional

from loguru import logger

from app.models.schema import VideoAspect, VideoParams
from app.services.manim.spec import SceneSpec
from app.utils import utils

_SERVICES_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TEMPLATES_MODULE = os.path.join(_SERVICES_DIR, "manim_templates.py")
# Repo root: the scene shim imports ``app.services.manim.*``, and the manim CLI
# loads it as a bare file with cwd=task_path — without the repo root on
# PYTHONPATH every render dies with ModuleNotFoundError: app.
_REPO_ROOT = os.path.dirname(os.path.dirname(_SERVICES_DIR))
_SCENE_NAME = "MathExplainerScene"
# Hard ceiling for a single render so a bad spec cannot hang the worker.
_RENDER_TIMEOUT_SECONDS = 600


def apply_manim_video_defaults(params: VideoParams) -> None:
    """Apply subtitle/layout defaults tuned for Manim math explainers."""
    if params.video_source != "manim":
        return
    params.font_name = "BeVietnamPro-Bold.ttf"
    if not params.font_size or params.font_size > 48:
        params.font_size = 48
    params.subtitle_position = "custom"
    params.custom_position = 78.0
    params.text_background_color = True
    params.rounded_subtitle_background = True


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
    env["MANIM_IS_PORTRAIT"] = "1" if height > width else "0"
    # Lets the scene match the camera frame to the pixel aspect; without this
    # Manim keeps its 14.22x8 landscape frame and portrait content renders tiny.
    env["MANIM_FRAME_ASPECT"] = f"{width / height:.6f}"
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        _REPO_ROOT + os.pathsep + existing_pythonpath
        if existing_pythonpath
        else _REPO_ROOT
    )

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
    target_duration = max(4.0, float(duration))
    actual_duration = _probe_duration(rendered)
    shortfall = (
        target_duration - actual_duration if actual_duration is not None else 0.0
    )
    if shortfall > 0.5:
        logger.warning(
            f"manim render is {shortfall:.1f}s shorter than the narration "
            f"({actual_duration:.1f}s vs {target_duration:.1f}s); "
            "freeze-extending the last frame"
        )
        if not _extend_with_freeze_frame(rendered, final_path, shortfall):
            shutil.copyfile(rendered, final_path)
    else:
        shutil.copyfile(rendered, final_path)
    _cleanup_media(media_dir)
    logger.success(f"manim scene rendered: {final_path}")
    return final_path


def _probe_duration(video_path: str) -> Optional[float]:
    """Duration of ``video_path`` in seconds via ffprobe, or None on failure."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return float(result.stdout.strip())
    except Exception as exc:
        logger.warning(f"could not probe manim render duration: {exc}")
        return None


def _extend_with_freeze_frame(src: str, dst: str, extra_seconds: float) -> bool:
    """Extend ``src`` by holding its last frame, writing to ``dst``."""
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                src,
                "-vf",
                f"tpad=stop_mode=clone:stop_duration={extra_seconds:.3f}",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                dst,
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0 and os.path.isfile(dst):
            return True
        logger.warning(f"ffmpeg freeze-extend failed: {result.stderr[-500:]}")
    except Exception as exc:
        logger.warning(f"ffmpeg freeze-extend failed: {exc}")
    return False


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
