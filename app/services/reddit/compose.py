"""Compose Reddit cards over looping local gameplay footage."""

from __future__ import annotations

import json
import os
import random
from typing import Optional

import numpy as np
from loguru import logger
from moviepy import CompositeVideoClip, ImageClip, VideoFileClip, vfx
from PIL import Image

from app.config import config
from app.models.schema import VideoAspect, VideoParams
from app.services.reddit.cards import export_card_pngs, list_gameplay_files
from app.services.reddit.fetch import RedditPost
from app.services.reddit.script import (
    allocate_segment_times,
    chunk_body_text,
    narration_segments,
)
from app.utils import utils

_CARD_MAX_HEIGHT_RATIO = 0.40
_CARD_FADE = 0.25


def resolve_gameplay_dir(params: VideoParams | None = None) -> str:
    override = ""
    if params is not None:
        override = (getattr(params, "reddit_gameplay_dir", None) or "").strip()
    reddit_cfg = getattr(config, "reddit", None) or {}
    configured = override or str(reddit_cfg.get("gameplay_dir", "resource/gameplay"))
    if os.path.isabs(configured):
        return configured
    return os.path.join(utils.root_dir(), configured)


def _fit_gameplay_clip(
    clip: VideoFileClip,
    video_width: int,
    video_height: int,
) -> VideoFileClip:
    """Cover-fit gameplay into the target aspect (center crop after resize)."""
    clip_w, clip_h = clip.size
    scale = max(video_width / clip_w, video_height / clip_h)
    new_w = int(round(clip_w * scale))
    new_h = int(round(clip_h * scale))
    resized = clip.resized(new_size=(new_w, new_h))
    x1 = max(0, (new_w - video_width) // 2)
    y1 = max(0, (new_h - video_height) // 2)
    return resized.cropped(
        x1=x1,
        y1=y1,
        x2=x1 + video_width,
        y2=y1 + video_height,
    )


def _build_looped_background(
    gameplay_files: list[str],
    duration: float,
    video_width: int,
    video_height: int,
) -> VideoFileClip:
    if not gameplay_files:
        raise ValueError(
            "no gameplay clips found; add at least one .mp4/.mov to the gameplay folder"
        )

    files = list(gameplay_files)
    random.shuffle(files)

    pieces = []
    covered = 0.0
    index = 0
    opened: list[VideoFileClip] = []
    try:
        while covered < duration + 0.25:
            path = files[index % len(files)]
            index += 1
            raw = VideoFileClip(path, audio=False)
            opened.append(raw)
            fitted = _fit_gameplay_clip(raw, video_width, video_height)
            remaining = duration - covered + 0.25
            if fitted.duration > remaining:
                fitted = fitted.subclipped(0, remaining)
            pieces.append(fitted.with_start(covered))
            covered += fitted.duration

        background = CompositeVideoClip(
            pieces,
            size=(video_width, video_height),
        ).with_duration(duration)
        # Keep references so GC doesn't close underlying readers early.
        background._reddit_opened = opened  # type: ignore[attr-defined]
        background._reddit_pieces = pieces  # type: ignore[attr-defined]
        return background
    except Exception:
        for clip in opened:
            try:
                clip.close()
            except Exception:
                pass
        raise


def _apply_card_motion(clip: ImageClip, duration: float) -> ImageClip:
    """Fade in/out plus a short scale pop on enter."""
    fade_in = min(_CARD_FADE, max(0.05, duration / 3.0))
    fade_out = min(0.20, max(0.05, duration / 4.0))
    if duration < 0.35:
        # Too short for motion; keep a light fade only.
        return clip.with_effects([vfx.FadeIn(min(0.08, duration / 2))])

    def scale_at(t: float) -> float:
        if t >= fade_in:
            return 1.0
        return 0.92 + 0.08 * (t / fade_in)

    effects = [
        vfx.FadeIn(fade_in),
        vfx.FadeOut(fade_out),
        vfx.Resize(scale_at),
    ]
    return clip.with_effects(effects)


def _card_clip_for_segment(
    segment: dict,
    card_paths: dict[str, str],
    video_width: int,
    video_height: int,
) -> Optional[ImageClip]:
    kind = segment.get("kind")
    start = float(segment["start"])
    end = float(segment["end"])
    duration = max(0.05, end - start)

    if kind == "title":
        path = card_paths.get("post_title") or card_paths.get("post")
    elif kind == "body_chunk":
        idx = segment.get("chunk_index")
        path = card_paths.get(f"body_chunk_{idx}") or card_paths.get("post")
    elif kind == "body":
        path = card_paths.get("post")
    elif kind == "comment":
        idx = segment.get("comment_index")
        path = card_paths.get(f"comment_{idx}")
    else:
        path = card_paths.get("post")

    if not path or not os.path.isfile(path):
        return None

    # Target ~82% of frame width, placed in upper third; cap height so gameplay shows.
    target_w = int(video_width * 0.82)
    img = Image.open(path).convert("RGBA")
    scale = target_w / img.width
    new_size = (target_w, max(1, int(img.height * scale)))
    max_h = int(video_height * _CARD_MAX_HEIGHT_RATIO)
    if new_size[1] > max_h:
        scale = max_h / img.height
        new_size = (max(1, int(img.width * scale)), max_h)
    img = img.resize(new_size, Image.Resampling.LANCZOS)

    base = ImageClip(np.array(img), transparent=True).with_duration(duration)
    final_w, final_h = base.w, base.h
    top = int(video_height * 0.08)
    left = (video_width - final_w) // 2

    # Keep the pop centered as Resize changes size during fade-in.
    fade_in = min(_CARD_FADE, max(0.05, duration / 3.0))

    def position_at(t: float):
        if t >= fade_in or duration < 0.35:
            return (left, top)
        s = 0.92 + 0.08 * (t / fade_in)
        w = int(final_w * s)
        h = int(final_h * s)
        return (left + (final_w - w) // 2, top + (final_h - h) // 2)

    clip = _apply_card_motion(base, duration)
    return clip.with_position(position_at).with_start(start)


def compose_reddit_video(
    *,
    task_id: str,
    post: RedditPost,
    audio_duration: float,
    video_aspect: VideoAspect | str = VideoAspect.portrait,
    gameplay_dir: str,
    output_path: str | None = None,
) -> str:
    """
    Render a full-length Reddit story video (gameplay + cards) and return its path.
    """
    aspect = VideoAspect(video_aspect) if not isinstance(video_aspect, VideoAspect) else video_aspect
    video_width, video_height = aspect.to_resolution()
    duration = max(float(audio_duration), 0.5)

    task_directory = utils.task_dir(task_id)
    cards_dir = os.path.join(task_directory, "reddit_cards")
    card_width = min(900, int(video_width * 0.82))
    body_chunks = chunk_body_text(post.selftext or "")
    card_paths = export_card_pngs(
        post, cards_dir, card_width=card_width, body_chunks=body_chunks
    )

    # Persist post metadata for debugging / later edits.
    meta_path = os.path.join(task_directory, "reddit_post.json")
    with open(meta_path, "w", encoding="utf-8") as fp:
        json.dump(post.to_dict(), fp, ensure_ascii=False, indent=2)

    segments = allocate_segment_times(narration_segments(post), duration)
    segments_path = os.path.join(task_directory, "reddit_segments.json")
    with open(segments_path, "w", encoding="utf-8") as fp:
        json.dump(segments, fp, ensure_ascii=False, indent=2)

    gameplay_files = list_gameplay_files(gameplay_dir)
    if not gameplay_files:
        raise ValueError(
            f"no gameplay clips in {gameplay_dir}; "
            "add at least one .mp4/.mov/.mkv file"
        )

    logger.info(
        f"composing Reddit story: {len(segments)} segments, "
        f"{len(gameplay_files)} gameplay files, duration={duration:.2f}s"
    )

    background = None
    card_clips = []
    final = None
    try:
        background = _build_looped_background(
            gameplay_files, duration, video_width, video_height
        )
        for segment in segments:
            clip = _card_clip_for_segment(
                segment, card_paths, video_width, video_height
            )
            if clip is not None:
                card_clips.append(clip)

        layers = [background, *card_clips]
        final = CompositeVideoClip(layers, size=(video_width, video_height)).with_duration(
            duration
        )

        out = output_path or os.path.join(task_directory, "reddit-story.mp4")
        final.write_videofile(
            out,
            fps=30,
            codec="libx264",
            audio=False,
            logger=None,
            threads=2,
        )
        logger.info(f"Reddit story video written: {out}")
        return out
    finally:
        for clip in card_clips:
            try:
                clip.close()
            except Exception:
                pass
        if final is not None:
            try:
                final.close()
            except Exception:
                pass
        if background is not None:
            opened = getattr(background, "_reddit_opened", [])
            try:
                background.close()
            except Exception:
                pass
            for clip in opened:
                try:
                    clip.close()
                except Exception:
                    pass


def build_reddit_video(
    task_id: str,
    params: VideoParams,
    audio_duration: float,
    post: RedditPost | None = None,
) -> list[str]:
    """
    Public entry used by the task pipeline.

    Returns a single-item list with the composed Reddit story MP4 path.
    """
    if post is None:
        meta_path = os.path.join(utils.task_dir(task_id), "reddit_post.json")
        if not os.path.isfile(meta_path):
            raise ValueError(
                "reddit post metadata missing; script step must fetch the Reddit URL first"
            )
        with open(meta_path, encoding="utf-8") as fp:
            post = RedditPost.from_dict(json.load(fp))

    gameplay_dir = resolve_gameplay_dir(params)
    path = compose_reddit_video(
        task_id=task_id,
        post=post,
        audio_duration=audio_duration,
        video_aspect=params.video_aspect or VideoAspect.portrait,
        gameplay_dir=gameplay_dir,
    )
    return [path]
