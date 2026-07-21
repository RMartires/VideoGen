"""Build TTS narration scripts from Reddit posts."""

from __future__ import annotations

import re

from app.services.reddit.fetch import RedditPost, fetch_post
from app.utils import utils

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'])|(?<=[.!?])\s*\n+|\n{2,}")
_MAX_CHUNK_CHARS = 140


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

    Structure for TTS pacing:
      1) Title
      2) Body chunks (sentence-sized)
      3) Each selected comment body (author stays on the card, not spoken)
    """
    parts: list[str] = []
    title = (post.title or "").strip()
    if title:
        parts.append(title)

    for chunk in chunk_body_text(post.selftext or ""):
        parts.append(chunk)

    for comment in post.comments:
        text = (comment.body or "").strip()
        if text:
            parts.append(text)

    script = "\n\n".join(parts).strip()
    if not script:
        raise ValueError("Reddit post produced an empty narration script")
    return script


def build_script_from_url(url: str, comment_limit: int | None = None) -> tuple[str, RedditPost]:
    """Fetch a Reddit URL and return (script, post)."""
    post = fetch_post(url, comment_limit=comment_limit)
    return build_script_from_post(post), post


def narration_segments(post: RedditPost) -> list[dict]:
    """
    Split the post into timed narration segments for card reveals.

    Each segment has: kind ("title"|"body_chunk"|"comment"), text,
    optional comment_index / chunk_index.
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

    for index, comment in enumerate(post.comments):
        text = (comment.body or "").strip()
        if not text:
            continue
        segments.append(
            {
                "kind": "comment",
                "text": text,
                "comment_index": index,
                "chunk_index": None,
            }
        )
    return segments


def allocate_segment_times(
    segments: list[dict],
    total_duration: float,
) -> list[dict]:
    """
    Assign start/end times proportional to character weight.

    Title segments get a floor of min(3s, 8% of duration) so the hook is readable.
    Returns segments with start/end floats attached.
    """
    if not segments:
        return []
    duration = max(float(total_duration), 0.1)
    weights = [float(max(len((s.get("text") or "").strip()), 1)) for s in segments]

    # Boost title so the hook isn't a blink on long posts.
    title_floor = min(3.0, duration * 0.08)
    title_indices = [i for i, s in enumerate(segments) if s.get("kind") == "title"]
    if title_indices and duration > title_floor + 0.5:
        title_i = title_indices[0]
        total_weight = sum(weights) or 1.0
        natural_title = duration * (weights[title_i] / total_weight)
        if natural_title < title_floor:
            # Inflate title weight so its share ≈ title_floor.
            other = total_weight - weights[title_i]
            if other > 0:
                # title_share = w_t / (w_t + other) = title_floor / duration
                # w_t = other * title_floor / (duration - title_floor)
                weights[title_i] = other * title_floor / max(duration - title_floor, 0.1)

    total_weight = sum(weights) or 1.0
    cursor = 0.0
    timed: list[dict] = []
    for i, segment in enumerate(segments):
        share = weights[i] / total_weight
        length = duration * share
        if i == len(segments) - 1:
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
    Write an SRT where each cue is one narration segment (current spoken chunk).

    Avoids full-script Whisper captions that duplicate the Reddit cards.
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
        # Build a clean SRT block (no trailing whitespace-only lines).
        # utils.text_to_srt pads a spaces line that MoviePy treats as an
        # extra blank cue and then crashes on (None, "").
        # Also collapse internal blank lines — MoviePy ends a cue on any
        # empty line, so multiline comment bodies would split cues.
        start_ts = utils.time_convert_seconds_to_hmsm(start)
        end_ts = utils.time_convert_seconds_to_hmsm(end)
        caption = " ".join(text.split())
        blocks.append(f"{idx}\n{start_ts} --> {end_ts}\n{caption}")
        idx += 1

    payload = "\n\n".join(blocks)
    if payload:
        # Trailing blank line required so MoviePy flushes the last cue.
        payload += "\n\n"
    with open(subtitle_file, "w", encoding="utf-8") as fp:
        fp.write(payload)
    return subtitle_file
