"""Post-process LLM scene specs before validation timing.

Repairs common exponential-story mistakes (fragmented counters, bad labels,
rushed closing segments) without executing arbitrary code.
"""

from __future__ import annotations

import math
import re
from copy import deepcopy
from typing import Any, Optional

# Segment types that tell one continuous doubling story.
_RICE_TYPES = frozenset(
    {"counter_doubling", "value_pop", "growth_bars", "dot_grid_doubling"}
)

# When several segments share a narration_hint, keep the richest visual.
_HINT_PRIORITY = {
    "growth_bars": 50,
    "counter_doubling": 40,
    "dot_grid_doubling": 35,
    "axes_plot": 30,
    "equation_morph": 28,
    "equation_reveal": 25,
    "quote_card": 45,
    "value_pop": 10,
    "highlight": 5,
}

_CONTINUITY_PAIRS = frozenset(
    {
        ("counter_doubling", "counter_doubling"),
        ("counter_doubling", "dot_grid_doubling"),
        ("growth_bars", "dot_grid_doubling"),
        ("dot_grid_doubling", "quote_card"),
        ("growth_bars", "quote_card"),
        ("equation_morph", "highlight"),
        ("axes_plot", "highlight"),
    }
)

_BAD_COUNTER_LABELS = frozenset(
    {"cycles", "cycle", "steps", "times", "rounds", "periods"}
)

_POWER_LABEL = re.compile(r"^2?\^?\s*(\d+)\s*$", re.I)
_GRAIN_CAPTION = re.compile(r"(\d[\d,]*)\s*grains?", re.I)
_JUNK_MORPH = re.compile(r"^\\?(downarrow|uparrow|rightarrow|leftarrow|Rightarrow|Rightarrow)?$", re.I)


def _seg_dict(segment: Any) -> dict[str, Any]:
    if hasattr(segment, "model_dump"):
        return segment.model_dump()
    if isinstance(segment, dict):
        return deepcopy(segment)
    return dict(segment)


def _grain_count(text: str) -> Optional[int]:
    if not text:
        return None
    match = _GRAIN_CAPTION.search(str(text))
    if not match:
        return None
    try:
        return int(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _doubling_steps(start: float, target: float) -> int:
    start = max(start, 1.0)
    target = max(target, start)
    if target <= start:
        return 0
    return max(0, int(round(math.log2(target / start))))


def _fix_counter_label(segment: dict[str, Any]) -> None:
    """Power notation in ``label`` (e.g. ``2^4``) is almost always a day index."""
    label = str(segment.get("label") or "").strip()
    if label.lower() in _BAD_COUNTER_LABELS:
        segment["label"] = "doublings"
        return
    if not label or not ("^" in label or _POWER_LABEL.match(label)):
        return
    match = _POWER_LABEL.match(label.replace(" ", ""))
    if match:
        exp = int(match.group(1))
        if not segment.get("title"):
            segment["title"] = f"Day {exp + 1}"
    segment["label"] = "grains"


def _clean_morph_equations(segment: dict[str, Any]) -> None:
    eqs = segment.get("equations")
    if not eqs:
        return
    cleaned = [
        eq
        for eq in eqs
        if eq
        and not _JUNK_MORPH.match(str(eq).strip())
        and len(str(eq).strip()) > 2
    ]
    segment["equations"] = cleaned or None


def _merge_counter_chain(block: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge consecutive counter_doubling segments; drop redundant grain value_pops."""
    counters = [s for s in block if s.get("type") == "counter_doubling"]
    if not counters:
        return block
    if len(counters) <= 1 and not any(s.get("type") == "value_pop" for s in block):
        for c in counters:
            _fix_counter_label(c)
        return block

    merged = deepcopy(counters[0])
    start = float(merged.get("start_value") or 1)
    merged["start_value"] = start
    total_steps = 0
    milestones: list[int] = []

    for seg in block:
        if seg.get("type") == "counter_doubling":
            _fix_counter_label(seg)
            count = int(seg.get("count") or 1)
            end_val = seg.get("end_value")
            if end_val is not None:
                total_steps = max(total_steps, _doubling_steps(start, float(end_val)))
            else:
                total_steps += count
        elif seg.get("type") == "value_pop":
            grains = _grain_count(str(seg.get("caption") or ""))
            if grains is not None:
                milestones.append(grains)

    if milestones:
        total_steps = max(total_steps, _doubling_steps(start, max(milestones)))

    merged["count"] = max(1, min(8, total_steps or int(merged.get("count") or 1)))
    merged.pop("end_value", None)
    if not merged.get("label") or "^" in str(merged.get("label")):
        merged["label"] = "grains"

    out: list[dict[str, Any]] = []
    for seg in block:
        stype = seg.get("type")
        if stype == "counter_doubling":
            if seg is counters[0]:
                out.append(merged)
            continue
        if stype == "value_pop" and _grain_count(str(seg.get("caption") or "")):
            continue
        if stype == "highlight":
            out.append(seg)
            continue
        out.append(seg)
    return out


def _expand_growth_bars(segment: dict[str, Any], milestones: list[int]) -> None:
    values = list(segment.get("values") or [])
    labels = list(segment.get("labels") or [])
    if len(values) >= 3 and not milestones:
        return
    top = max([1.0] + [float(v) for v in values] + [float(m) for m in milestones])
    if top <= 1:
        return
    top_exp = int(round(math.log2(top)))
    exponents = sorted(
        set([0, max(0, top_exp - 7), max(0, top_exp - 4), top_exp])
    )
    combined = [float(2**e) for e in exponents]
    segment["values"] = combined
    if len(labels) < len(combined):
        default_days = [1, 4, 7, 12, 20, 30]
        segment["labels"] = [
            labels[i] if i < len(labels) else f"Day {default_days[i]}"
            for i in range(len(combined))
        ]


def _merge_adjacent_value_pops(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Combine back-to-back value_pop segments to avoid blank fade gaps."""
    if not segments:
        return segments
    out: list[dict[str, Any]] = []
    i = 0
    while i < len(segments):
        seg = segments[i]
        if (
            seg.get("type") == "value_pop"
            and i + 1 < len(segments)
            and segments[i + 1].get("type") == "value_pop"
        ):
            nxt = segments[i + 1]
            merged = deepcopy(seg)
            first = str(merged.get("caption") or "").strip()
            second = str(nxt.get("caption") or "").strip()
            if first and second:
                if not merged.get("title"):
                    merged["title"] = first
                merged["caption"] = second
            hints = [
                h
                for h in (seg.get("narration_hint"), nxt.get("narration_hint"))
                if h
            ]
            if hints:
                merged["narration_hint"] = ". ".join(hints)
            out.append(merged)
            i += 2
            continue
        out.append(seg)
        i += 1
    return out


def _normalize_rice_story(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Coalesce fragmented counter / value_pop chains into one continuous demo."""
    out: list[dict[str, Any]] = []
    i = 0
    milestones: list[int] = []
    while i < len(segments):
        seg = segments[i]
        if seg.get("type") not in _RICE_TYPES:
            out.append(seg)
            i += 1
            continue

        block: list[dict[str, Any]] = []
        while i < len(segments) and segments[i].get("type") in _RICE_TYPES | {"highlight"}:
            if segments[i].get("type") == "highlight":
                if block:
                    block.append(segments[i])
                else:
                    out.append(segments[i])
            else:
                block.append(segments[i])
                grains = _grain_count(str(segments[i].get("caption") or ""))
                if grains:
                    milestones.append(grains)
            i += 1

        if block:
            block = _merge_counter_chain(block)
            for seg in block:
                if seg.get("type") == "growth_bars":
                    _expand_growth_bars(seg, milestones)
            out.extend(block)
    return out


def _collapse_duplicate_axes(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop extra axes_plot segments with the same function; keep one labeled re-show."""
    seen: dict[str, int] = {}
    out: list[dict[str, Any]] = []
    for seg in segments:
        if seg.get("type") != "axes_plot":
            out.append(seg)
            continue
        fn = str(seg.get("function") or "")
        count = seen.get(fn, 0) + 1
        seen[fn] = count
        if count == 1:
            out.append(seg)
        elif count == 2 and seg.get("label"):
            out.append(seg)
        else:
            out.append(
                {
                    "type": "highlight",
                    "narration_hint": seg.get("narration_hint"),
                }
            )
    return out


def _drop_echo_highlight(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove a closing highlight that repeats the opening narration line."""
    if len(segments) < 2 or segments[-1].get("type") != "highlight":
        return segments
    first_hint = (segments[0].get("narration_hint") or "").strip().lower()
    last_hint = (segments[-1].get("narration_hint") or "").strip().lower()
    if first_hint and first_hint == last_hint:
        return segments[:-1]
    return segments


def _dedupe_same_hint(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop weaker segments that reuse the same narration_hint back-to-back."""
    if not segments:
        return segments
    out: list[dict[str, Any]] = []
    for seg in segments:
        hint = (seg.get("narration_hint") or "").strip().lower()
        if (
            out
            and hint
            and hint == (out[-1].get("narration_hint") or "").strip().lower()
        ):
            prev = out[-1]
            prev_rank = _HINT_PRIORITY.get(prev.get("type", ""), 0)
            rank = _HINT_PRIORITY.get(seg.get("type", ""), 0)
            if rank > prev_rank:
                out[-1] = seg
            continue
        out.append(seg)
    return out


def _mark_continuity(segments: list[dict[str, Any]]) -> None:
    """Set continues_from_previous when the next segment extends the same story."""
    pair_set = _CONTINUITY_PAIRS

    def _prev_visual(idx: int) -> Optional[str]:
        for j in range(idx - 1, -1, -1):
            t = segments[j].get("type")
            if t != "highlight":
                return t
        return None

    for i in range(1, len(segments)):
        prev_type = _prev_visual(i)
        cur = segments[i]
        cur_type = cur.get("type")
        if cur_type == "highlight" or not prev_type:
            cur.pop("continues_from_previous", None)
            continue
        if (prev_type, cur_type) in pair_set:
            cur["continues_from_previous"] = True
        else:
            cur.pop("continues_from_previous", None)


def _propagate_counter_end(segments: list[dict[str, Any]]) -> None:
    for i, seg in enumerate(segments):
        if seg.get("type") != "counter_doubling":
            continue
        start = float(seg.get("start_value") or 1)
        steps = int(seg.get("count") or 1)
        end_val = start * (2**steps)
        for j in range(i + 1, min(i + 3, len(segments))):
            nxt = segments[j]
            if nxt.get("type") == "dot_grid_doubling" and not nxt.get("start_value"):
                nxt["start_value"] = end_val
            if nxt.get("type") == "growth_bars" and len(nxt.get("values") or []) <= 1:
                _expand_growth_bars(nxt, [int(end_val)])


def normalize_segments(segments: list[Any]) -> list[dict[str, Any]]:
    """Return a cleaned segment list ready for ``SceneSpec`` validation."""
    raw = [_seg_dict(s) for s in segments]
    for seg in raw:
        _fix_counter_label(seg)
        if seg.get("type") == "equation_morph":
            _clean_morph_equations(seg)
        if seg.get("type") == "counter_doubling":
            if seg.get("start_value") is None:
                seg["start_value"] = 1.0

    raw = _merge_adjacent_value_pops(raw)
    raw = _normalize_rice_story(raw)
    raw = _collapse_duplicate_axes(raw)
    raw = _dedupe_same_hint(raw)
    raw = _drop_echo_highlight(raw)
    _propagate_counter_end(raw)
    _mark_continuity(raw)
    return raw
