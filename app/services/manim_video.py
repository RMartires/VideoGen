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
import re
import shutil
import subprocess
import sys
from typing import List, Optional

from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from app.models.schema import VideoAspect, VideoParams
from app.services import subtitle
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
    "squares_transform",
    "area_grid",
    "highlight",
}
# Hard ceiling for a single render so a bad spec cannot hang the worker.
_RENDER_TIMEOUT_SECONDS = 600

_GEOMETRY_TYPES = {
    "right_triangle",
    "squares_on_sides",
    "pythagorean_triple",
    "squares_transform",
    "area_grid",
}
# Templates that read as generic filler on a geometry topic. When the LLM has
# committed to a geometry story, these only break the visual narrative.
_ABSTRACT_TYPES = {"number_line", "axes_plot", "bullet_points"}


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
    # Absolute second (from video start) when this visual should appear and how
    # long it stays on screen. Both are filled by apply_subtitle_timing.
    start: Optional[float] = None
    duration: Optional[float] = None
    # Short phrase from the narration when this visual should appear.
    narration_hint: Optional[str] = None


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
            Segment(
                type="right_triangle",
                side_a=3,
                side_b=4,
                caption="Legs a & b, hypotenuse c",
                narration_hint="triangle with legs a and b",
            ),
            Segment(
                type="squares_on_sides",
                side_a=3,
                side_b=4,
                title="Squares on each side",
                narration_hint="building a square on each side",
            ),
            Segment(
                type="squares_transform",
                side_a=3,
                side_b=4,
                narration_hint="nine plus sixteen",
            ),
            Segment(
                type="area_grid",
                side=5,
                title="c² = 25",
                narration_hint="square on the five side",
            ),
            Segment(
                type="equation_reveal",
                caption="The geometric balance",
                equations=["a^2 + b^2 = c^2"],
                narration_hint="a squared plus b squared equals c squared",
            ),
        ],
    )


# JSON unescaping mangles LaTeX: "\times" arrives as "<tab>imes", "\neq" as
# "<newline>eq", etc. Rebuild the intended backslash commands.
_CONTROL_CHAR_REPAIRS = {
    "\t": "\\t",
    "\n": "\\n",
    "\r": "\\r",
    "\f": "\\f",
    "\b": "\\b",
}


def _repair_latex(expr: str) -> str:
    for control, replacement in _CONTROL_CHAR_REPAIRS.items():
        expr = expr.replace(control, replacement)
    return expr.strip()


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

    for segment in spec.segments:
        if segment.equations:
            segment.equations = [_repair_latex(eq) for eq in segment.equations]

    # A highlight pulses whatever is already on screen, so it is meaningless
    # (and renders nothing) before the first real visual.
    while spec.segments and spec.segments[0].type == "highlight":
        spec.segments.pop(0)

    geometry_count = sum(1 for s in spec.segments if s.type in _GEOMETRY_TYPES)
    if geometry_count >= 2:
        dropped = [s.type for s in spec.segments if s.type in _ABSTRACT_TYPES]
        if dropped:
            logger.info(
                f"dropping abstract segments from geometry spec: {dropped}"
            )
            spec.segments = [
                s for s in spec.segments if s.type not in _ABSTRACT_TYPES
            ]

    if not spec.segments:
        logger.warning("manim scene spec has no usable segments, using default")
        return default_spec(video_subject)
    return spec


def _srt_timestamp_to_seconds(timestamp: str) -> float:
    hours, minutes, rest = timestamp.strip().split(":")
    seconds, millis = rest.split(",")
    return (
        int(hours) * 3600
        + int(minutes) * 60
        + int(seconds)
        + int(millis) / 1000.0
    )


def _parse_subtitle_ranges(
    subtitle_path: str,
) -> list[tuple[float, float, str]]:
    items = subtitle.file_to_subtitles(subtitle_path)
    ranges: list[tuple[float, float, str]] = []
    for _idx, times, text in items:
        start_s, end_s = times.split(" --> ")
        ranges.append(
            (
                _srt_timestamp_to_seconds(start_s),
                _srt_timestamp_to_seconds(end_s),
                text.strip(),
            )
        )
    return ranges


def _group_sentences_into_buckets(sentences: list[str], bucket_count: int) -> list[str]:
    if bucket_count <= 0:
        return []
    if not sentences:
        return [""] * bucket_count
    if len(sentences) <= bucket_count:
        buckets = sentences + [""] * (bucket_count - len(sentences))
        return buckets[:bucket_count]

    total_words = sum(len(s.split()) for s in sentences)
    target = max(1, total_words / bucket_count)
    buckets: list[str] = []
    current: list[str] = []
    current_words = 0

    for sentence in sentences:
        current.append(sentence)
        current_words += len(sentence.split())
        if len(buckets) < bucket_count - 1 and current_words >= target:
            buckets.append(" ".join(current).strip())
            current = []
            current_words = 0

    if current:
        if buckets:
            buckets[-1] = f"{buckets[-1]} {' '.join(current)}".strip()
        else:
            buckets.append(" ".join(current).strip())

    while len(buckets) < bucket_count:
        buckets.append("")

    return buckets[:bucket_count]


def _segment_search_text(segment: Segment) -> str:
    parts = [
        segment.narration_hint or "",
        segment.title or "",
        segment.subtitle or "",
        segment.caption or "",
        segment.label or "",
    ]
    type_hints = {
        "right_triangle": "triangle legs hypotenuse right",
        "squares_on_sides": "square side build each",
        "pythagorean_triple": "nine sixteen twenty-five area",
        "squares_transform": "add up fill combine areas squares",
        "area_grid": "area square grid",
        "equation_reveal": "squared equals formula",
        "title_card": "theorem",
    }
    parts.append(type_hints.get(segment.type, ""))
    return " ".join(p for p in parts if p).strip().lower()


def _normalize_for_match(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


def _find_verbatim_hint(
    hint: str,
    ranges: list[tuple[float, float, str]],
    start_idx: int = 0,
) -> Optional[int]:
    """Index of the first subtitle line (from ``start_idx``) that contains
    ``hint`` verbatim, checking single lines then two-line windows.

    This runs before any fuzzy matching: an exact narration_hint pins the
    segment to the precise line it is spoken on, where word-overlap scoring
    tends to fire one line early (an early window can contain the same words).
    """
    hint_norm = _normalize_for_match(hint)
    if not hint_norm:
        return None
    lines = [_normalize_for_match(text) for _, _, text in ranges]
    # Single lines take priority everywhere: a two-line window would report
    # the earlier index even when the hint lives entirely in the later line.
    for idx in range(start_idx, len(lines)):
        if hint_norm in lines[idx]:
            return idx
    for idx in range(start_idx, len(lines) - 1):
        if hint_norm in f"{lines[idx]} {lines[idx + 1]}":
            return idx
    return None


def _find_range_for_text(
    query: str,
    ranges: list[tuple[float, float, str]],
    start_idx: int = 0,
) -> tuple[int, int, float, float]:
    """Find the subtitle range best matching ``query``, scanning forward only.

    Returns ``(start_idx, end_idx, start_seconds, end_seconds)`` of the match.
    """
    if not ranges:
        return start_idx, start_idx, 0.0, 4.0

    query = query.lower().strip()
    if not query:
        idx = min(start_idx, len(ranges) - 1)
        return idx, idx, ranges[idx][0], ranges[idx][1]

    query_words = [w for w in re.split(r"\W+", query) if len(w) > 2]
    best_idx = min(start_idx, len(ranges) - 1)
    best_score = -1.0

    for idx in range(start_idx, len(ranges)):
        # Two-line windows: wide enough for hints that straddle a line break,
        # narrow enough that an early window can't swallow a later line's
        # words and win the tie (which shifted every visual one line early).
        window = " ".join(text.lower() for _, _, text in ranges[idx : idx + 2])
        if query in window:
            end_idx = idx
            while end_idx + 1 < len(ranges) and len(
                " ".join(t for _, _, t in ranges[idx : end_idx + 2])
            ) < len(query) * 1.5:
                end_idx += 1
            return idx, end_idx, ranges[idx][0], ranges[end_idx][1]

        score = sum(1 for word in query_words if word in window) / max(1, len(query_words))
        if score > best_score:
            best_score = score
            best_idx = idx

    end_idx = best_idx
    while end_idx + 1 < len(ranges):
        accumulated = " ".join(t for _, _, t in ranges[best_idx : end_idx + 2])
        if subtitle.similarity(query, accumulated) >= subtitle.similarity(
            query, " ".join(t for _, _, t in ranges[best_idx : end_idx + 1])
        ):
            end_idx += 1
        else:
            break

    return best_idx, end_idx, ranges[best_idx][0], ranges[end_idx][1]


def apply_subtitle_timing(
    spec: SceneSpec,
    subtitle_path: str,
    video_script: str,
    total_duration: float,
) -> SceneSpec:
    """Assign absolute per-segment start times from subtitle timestamps.

    Each segment is anchored to the moment its ``narration_hint`` (or its slice
    of the script) is actually spoken, so visuals switch on narration beats.
    The cursor only moves forward through the subtitles, which keeps starts
    monotonic even if the LLM emitted segments slightly out of order.
    """
    if not subtitle_path or not os.path.isfile(subtitle_path):
        return spec
    if not spec.segments:
        return spec

    ranges = _parse_subtitle_ranges(subtitle_path)
    if not ranges:
        return spec

    total_duration = max(4.0, float(total_duration))
    sentences = utils.split_string_by_punctuations(video_script or "")
    buckets = _group_sentences_into_buckets(sentences, len(spec.segments))

    starts: list[float] = []
    cursor = 0
    for segment, bucket in zip(spec.segments, buckets):
        verbatim_idx = (
            _find_verbatim_hint(segment.narration_hint, ranges, cursor)
            if segment.narration_hint
            else None
        )
        if verbatim_idx is not None:
            start_idx, start_t = verbatim_idx, ranges[verbatim_idx][0]
        else:
            query = _segment_search_text(segment) or bucket
            start_idx, _end_idx, start_t, _end_t = _find_range_for_text(
                query, ranges, cursor
            )
        starts.append(start_t)
        # Advance only past the matched START line: the next segment may be
        # narrated in the very next line, and durations are derived from the
        # following segment's start anyway.
        cursor = min(start_idx + 1, len(ranges) - 1)

    # The screen must never be empty while the hook plays: the first visual
    # starts at 0 regardless of when its narration line lands.
    n = len(starts)
    starts[0] = 0.0
    min_slot = 2.0
    for i in range(1, n):
        lower = starts[i - 1] + min_slot
        # Leave enough room for every remaining segment to get min_slot.
        upper = max(lower, total_duration - min_slot * (n - i))
        starts[i] = min(max(starts[i], lower), upper)

    for i, segment in enumerate(spec.segments):
        end = starts[i + 1] if i + 1 < n else total_duration
        segment.start = round(starts[i], 3)
        segment.duration = round(max(0.5, end - starts[i]), 3)

    logger.info(
        "manim segment schedule (s): "
        + ", ".join(
            f"{s.type}@{s.start}+{s.duration}" for s in spec.segments
        )
    )
    return spec


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
