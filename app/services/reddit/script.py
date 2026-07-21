"""Build TTS narration scripts from Reddit posts."""

from __future__ import annotations

import re

from app.services.reddit.fetch import RedditPost, fetch_post
from app.utils import utils

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'])|(?<=[.!?])\s*\n+|\n{2,}")
_MAX_CHUNK_CHARS = 140
# Readable floor so short punch lines don't blink (~1.8–2.2s range).
_MIN_SEGMENT_SECONDS = 2.0


def chunk_body_text(text: str, max_chars: int = _MAX_CHUNK_CHARS) -> list[str]:
    """
    Split post body into short narration/card chunks.

    Prefers sentence boundaries, then packs leftover long sentences to max_chars.
    """
    raw = (text or "").strip()
    if not raw:
        return []

    sentences: list[str] = []
    for piece in _SENTENCE_SPLIT_RE.split(raw):
        piece = piece.strip()
        if piece:
            sentences.append(piece)
    if not sentences:
        sentences = [raw]

    chunks: list[str] = []
    for sentence in sentences:
        if len(sentence) <= max_chars:
            chunks.append(sentence)
            continue
        # Pack long sentences by word without exceeding max_chars.
        words = sentence.split()
        buf: list[str] = []
        for word in words:
            candidate = (" ".join(buf + [word])).strip()
            if buf and len(candidate) > max_chars:
                chunks.append(" ".join(buf))
                buf = [word]
            else:
                buf.append(word)
        if buf:
            chunks.append(" ".join(buf))
    return chunks


def build_script_from_post(post: RedditPost) -> str:
    """
    Build a plain-text narration script from a normalized Reddit post.

    Structure for TTS pacing (comments are intentionally omitted):
      1) Title
      2) Body chunks (sentence-sized)
    """
    parts: list[str] = []
    title = (post.title or "").strip()
    if title:
        parts.append(title)

    for chunk in chunk_body_text(post.selftext or ""):
        parts.append(chunk)

    script = "\n\n".join(parts).strip()
    if not script:
        raise ValueError("Reddit post produced an empty narration script")
    return script


def build_script_from_url(url: str, comment_limit: int | None = None) -> tuple[str, RedditPost]:
    """Fetch a Reddit URL and return (script, post). Comments are not narrated."""
    # comment_limit kept for API compatibility; story mode does not use comments.
    _ = comment_limit
    post = fetch_post(url, comment_limit=0)
    return build_script_from_post(post), post


def narration_segments(post: RedditPost) -> list[dict]:
    """
    Split the post into timed narration segments for card reveals.

    Each segment has: kind ("title"|"body_chunk"), text, optional chunk_index.
    Comments are excluded from the story cut.
    """
    segments: list[dict] = []
    title = (post.title or "").strip()
    if title:
        segments.append(
            {
                "kind": "title",
                "text": title,
                "comment_index": None,
                "chunk_index": None,
            }
        )

    for index, chunk in enumerate(chunk_body_text(post.selftext or "")):
        segments.append(
            {
                "kind": "body_chunk",
                "text": chunk,
                "comment_index": None,
                "chunk_index": index,
            }
        )
    return segments


def allocate_segment_times(
    segments: list[dict],
    total_duration: float,
    *,
    min_duration: float = _MIN_SEGMENT_SECONDS,
) -> list[dict]:
    """
    Assign start/end times with a per-segment floor, then weight the remainder.

    Every segment gets at least ``min_duration`` (clamped to equal-split when the
    video is too short). Leftover time is distributed by character weight.
    Title also keeps a mild hook boost via weight inflation.
    """
    if not segments:
        return []
    n = len(segments)
    duration = max(float(total_duration), 0.1)
    floor = min(float(min_duration), duration / n)

    weights = [float(max(len((s.get("text") or "").strip()), 1)) for s in segments]

    # Mild title boost so the hook stays readable on long posts.
    title_target = min(3.0, max(floor, duration * 0.08))
    title_indices = [i for i, s in enumerate(segments) if s.get("kind") == "title"]
    if title_indices and duration > title_target + floor * (n - 1):
        title_i = title_indices[0]
        # After floors, leftover pool is duration - floor*n.
        # Aim for title length ≈ title_target => extra_title ≈ title_target - floor.
        leftover = max(duration - floor * n, 0.0)
        want_extra = max(title_target - floor, 0.0)
        if leftover > 0 and want_extra > 0:
            other = sum(weights) - weights[title_i]
            # Share of leftover for title = want_extra / leftover
            # w_t / (w_t + other) = want_extra / leftover
            if other > 0 and want_extra < leftover:
                weights[title_i] = other * want_extra / max(leftover - want_extra, 0.1)

    total_weight = sum(weights) or 1.0
    leftover = max(duration - floor * n, 0.0)
    cursor = 0.0
    timed: list[dict] = []
    for i, segment in enumerate(segments):
        length = floor + leftover * (weights[i] / total_weight)
        if i == n - 1:
            end = duration
        else:
            end = min(duration, cursor + length)
        item = dict(segment)
        item["start"] = cursor
        item["end"] = max(cursor + 0.05, end)
        timed.append(item)
        cursor = item["end"]
    return timed


def write_segment_subtitles(
    segments: list[dict],
    subtitle_file: str,
) -> str:
    """
    Write an SRT where each cue is one narration segment.

    Kept for tests/debugging; Reddit story mode no longer burns captions.
    """
    blocks: list[str] = []
    idx = 1
    for segment in segments:
        text = (segment.get("text") or "").strip()
        if not text:
            continue
        start = float(segment.get("start", 0.0))
        end = float(segment.get("end", start + 0.05))
        if end <= start:
            end = start + 0.05
        start_ts = utils.time_convert_seconds_to_hmsm(start)
        end_ts = utils.time_convert_seconds_to_hmsm(end)
        caption = " ".join(text.split())
        blocks.append(f"{idx}\n{start_ts} --> {end_ts}\n{caption}")
        idx += 1

    payload = "\n\n".join(blocks)
    if payload:
        payload += "\n\n"
    with open(subtitle_file, "w", encoding="utf-8") as fp:
        fp.write(payload)
    return subtitle_file
