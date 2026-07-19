"""Scene-spec models, validation and subtitle-aligned timing.

App-side module: NEVER imports manim. Segment type names and category
compatibility come from ``catalog.yaml`` so validation works without the
optional Manim dependency installed.
"""

from __future__ import annotations

import json
import os
import re
from typing import List, Optional

from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from app.services import subtitle
from app.services.manim import catalog
from app.services.manim.core.math_safe import repair_latex
from app.services.manim.spec_normalize import normalize_segments
from app.utils import utils

_SEGMENT_TYPES = catalog.segment_types()
_GEOMETRY_TYPES = catalog.geometry_types()
# Templates that read as generic filler on a geometry topic. When the LLM has
# committed to a geometry story, these only break the visual narrative.
_ABSTRACT_TYPES = catalog.abstract_types()


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
    values: Optional[List[float]] = None
    labels: Optional[List[str]] = None
    start_value: Optional[float] = None
    end_value: Optional[float] = None
    count: Optional[int] = None
    # Generic extension fields used by newer segment types.
    matrix: Optional[List[List[float]]] = None
    vectors: Optional[List[List[float]]] = None
    coefficients: Optional[List[float]] = None
    numerator: Optional[float] = None
    denominator: Optional[float] = None
    rows: Optional[int] = None
    highlight_multiples_of: Optional[int] = None
    equation_from: Optional[str] = None
    equation_to: Optional[str] = None
    # When true, the scene keeps the previous mobject on screen and crossfades
    # into the new segment instead of fading to black first.
    continues_from_previous: Optional[bool] = None
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


def validate_or_default(raw: object, video_subject: str = "") -> SceneSpec:
    """Coerce arbitrary LLM output into a valid SceneSpec, falling back safely."""
    try:
        if isinstance(raw, str):
            raw = json.loads(raw)
        if isinstance(raw, dict) and raw.get("segments"):
            raw = {**raw, "segments": normalize_segments(raw["segments"])}
        spec = SceneSpec.model_validate(raw)
    except (ValidationError, ValueError, TypeError) as exc:
        logger.warning(f"invalid manim scene spec, using default: {exc}")
        return default_spec(video_subject)

    spec.segments = [s for s in spec.segments if s.type in _SEGMENT_TYPES]

    for segment in spec.segments:
        if segment.equations:
            segment.equations = [repair_latex(eq) for eq in segment.equations]

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


_MIN_SLOT = {
    "counter_doubling": 3.5,
    "quote_card": 2.5,
    "equation_reveal": 2.0,
    "growth_bars": 2.5,
    "value_pop": 2.0,
}


def _extend_short_slots(spec: SceneSpec, total_duration: float) -> None:
    """Borrow time from neighbors when key segments are too short to animate."""
    segments = spec.segments
    if not segments:
        return

    for i, seg in enumerate(segments):
        need = _MIN_SLOT.get(seg.type)
        if need is None or (seg.duration or 0) >= need:
            continue
        deficit = need - float(seg.duration or 0)
        # Prefer donating from the segment immediately before (often a weaker pop).
        for donor_idx in range(i - 1, -1, -1):
            donor = segments[donor_idx]
            if donor.type == "highlight":
                continue
            spare = float(donor.duration or 0) - _MIN_SLOT.get(donor.type, 1.0)
            if spare <= 0.2:
                continue
            take = min(deficit, spare)
            donor.duration = round(float(donor.duration or 0) - take, 3)
            seg.start = round(float(seg.start or 0) + take, 3)
            seg.duration = round(float(seg.duration or 0) + take, 3)
            deficit -= take
            if deficit <= 0.05:
                break

    # Recompute monotonic starts from durations.
    if segments[0].start is not None:
        segments[0].start = 0.0
    for i in range(1, len(segments)):
        prev = segments[i - 1]
        segments[i].start = round(
            float(prev.start or 0) + float(prev.duration or 0), 3
        )
    last = segments[-1]
    last_end = float(last.start or 0) + float(last.duration or 0)
    if last_end > total_duration and len(segments) >= 2:
        overflow = last_end - total_duration
        donor = segments[-2]
        if float(donor.duration or 0) > _MIN_SLOT.get(donor.type, 1.0) + overflow:
            donor.duration = round(float(donor.duration or 0) - overflow, 3)
            last.start = round(float(last.start or 0) - overflow, 3)


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
    # Micro-segment specs (10+) need shorter minimum gaps so visuals can
    # track individual narration beats instead of freezing for 2s+.
    min_slot = 1.0 if n >= 10 else 1.5 if n >= 7 else 2.0
    for i in range(1, n):
        lower = starts[i - 1] + min_slot
        # Leave enough room for every remaining segment to get min_slot.
        upper = max(lower, total_duration - min_slot * (n - i))
        starts[i] = min(max(starts[i], lower), upper)

    for i, segment in enumerate(spec.segments):
        end = starts[i + 1] if i + 1 < n else total_duration
        segment.start = round(starts[i], 3)
        segment.duration = round(max(0.5, end - starts[i]), 3)

    _extend_short_slots(spec, total_duration)

    logger.info(
        "manim segment schedule (s): "
        + ", ".join(
            f"{s.type}@{s.start}+{s.duration}" for s in spec.segments
        )
    )
    return spec
