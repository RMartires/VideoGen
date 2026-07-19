"""Backward-compat shim: the implementation moved to ``app/services/manim/``.

Existing callers (task.py, tests) import from this module; keep every public
name re-exported. New code should import from ``app.services.manim.spec`` and
``app.services.manim.video`` directly.
"""

from app.services.manim.spec import (  # noqa: F401
    SceneSpec,
    Segment,
    _ABSTRACT_TYPES,
    _GEOMETRY_TYPES,
    _SEGMENT_TYPES,
    _find_range_for_text,
    _find_verbatim_hint,
    _group_sentences_into_buckets,
    _normalize_for_match,
    _parse_subtitle_ranges,
    _segment_search_text,
    _srt_timestamp_to_seconds,
    apply_subtitle_timing,
    default_spec,
    validate_or_default,
)
from app.services.manim.spec import repair_latex as _repair_latex  # noqa: F401
from app.services.manim.video import (  # noqa: F401
    _RENDER_TIMEOUT_SECONDS,
    _SCENE_NAME,
    _TEMPLATES_MODULE,
    _cleanup_media,
    _extend_with_freeze_frame,
    _find_rendered_mp4,
    _probe_duration,
    _resolution_for_aspect,
    apply_manim_video_defaults,
    render_manim_video,
)
