"""Render Reddit-style post and comment cards with Pillow."""

from __future__ import annotations

import hashlib
import os
import textwrap

from PIL import Image, ImageDraw, ImageFont

from app.services.reddit.fetch import RedditComment, RedditPost
from app.services.reddit.script import chunk_body_text
from app.utils import utils

# Dark Reddit-inspired palette (not official branding assets).
_CARD = (30, 30, 32, 245)
_TEXT = (215, 218, 220, 255)
_MUTED = (129, 131, 132, 255)
_ORANGE = (255, 69, 0, 255)
_BORDER = (60, 60, 62, 255)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a project font, falling back to Pillow default."""
    candidates: list[str] = []
    fonts_dir = os.path.join(utils.root_dir(), "resource", "fonts")
    preferred = [
        "MicrosoftYaHeiBold.ttc" if bold else "MicrosoftYaHeiNormal.ttc",
        "STHeitiMedium.ttc",
        "Arial.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for name in preferred:
        path = os.path.join(fonts_dir, name)
        if os.path.isfile(path):
            candidates.append(path)
    # Common system fonts
    for path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
    ):
        if os.path.isfile(path):
            candidates.append(path)

    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _avatar_color(name: str) -> tuple[int, int, int, int]:
    digest = hashlib.md5((name or "u").encode("utf-8")).hexdigest()
    r = 80 + int(digest[0:2], 16) % 140
    g = 80 + int(digest[2:4], 16) % 140
    b = 80 + int(digest[4:6], 16) % 140
    return (r, g, b, 255)


def _initials(name: str) -> str:
    cleaned = "".join(ch for ch in (name or "?") if ch.isalnum())
    if not cleaned:
        return "?"
    return cleaned[:2].upper()


def _wrap(text: str, width: int) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    lines: list[str] = []
    for paragraph in text.split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            lines.append("")
            continue
        lines.extend(textwrap.wrap(paragraph, width=width) or [paragraph])
    return lines


def _draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fill,
    radius: int = 24,
    outline=None,
    width: int = 2,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _format_score(score: int) -> str:
    abs_score = abs(int(score))
    if abs_score >= 1000:
        return f"{score / 1000:.1f}k"
    return str(score)


def _draw_post_header(
    draw: ImageDraw.ImageDraw,
    post: RedditPost,
    *,
    padding: int,
    avatar_size: int,
    meta_font,
) -> int:
    """Draw avatar + meta row; return y after the header."""
    ax, ay = padding, padding
    color = _avatar_color(post.author)
    draw.ellipse((ax, ay, ax + avatar_size, ay + avatar_size), fill=color)
    initials = _initials(post.author)
    bbox = draw.textbbox((0, 0), initials, font=meta_font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        (ax + (avatar_size - tw) / 2, ay + (avatar_size - th) / 2 - 2),
        initials,
        font=meta_font,
        fill=(255, 255, 255, 255),
    )
    meta = f"r/{post.subreddit}  ·  u/{post.author}  ·  {_format_score(post.score)} ups"
    draw.text((ax + avatar_size + 16, ay + 8), meta, font=meta_font, fill=_MUTED)
    return ay + avatar_size + 16


def render_post_card(
    post: RedditPost,
    *,
    width: int = 900,
    show_body: bool = True,
    max_body_chars: int = 600,
) -> Image.Image:
    """Render the OP post card (subreddit, title, optional body)."""
    padding = 28
    avatar_size = 56
    title_font = _font(36, bold=True)
    meta_font = _font(24)
    body_font = _font(28)

    title_lines = _wrap(post.title, width=36)
    body_text = (post.selftext or "").strip()
    if not show_body:
        body_text = ""
    elif len(body_text) > max_body_chars:
        body_text = body_text[: max_body_chars - 1].rstrip() + "…"
    body_lines = _wrap(body_text, width=42) if body_text else []

    line_h_title = 44
    line_h_body = 34
    content_h = (
        padding
        + avatar_size
        + 16
        + len(title_lines) * line_h_title
        + (12 if body_lines else 0)
        + len(body_lines) * line_h_body
        + padding
    )
    height = max(220, content_h)
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    _draw_rounded_rect(draw, (0, 0, width - 1, height - 1), fill=_CARD, outline=_BORDER)

    y = _draw_post_header(
        draw, post, padding=padding, avatar_size=avatar_size, meta_font=meta_font
    )
    for line in title_lines:
        draw.text((padding, y), line, font=title_font, fill=_TEXT)
        y += line_h_title

    if body_lines:
        y += 8
        for line in body_lines:
            draw.text((padding, y), line, font=body_font, fill=_TEXT)
            y += line_h_body

    draw.rectangle((0, 0, 8, height), fill=_ORANGE)
    return img


def render_body_chunk_card(
    post: RedditPost,
    chunk: str,
    *,
    width: int = 900,
    max_title_lines: int = 2,
    show_title: bool = True,
) -> Image.Image:
    """
    Compact progressive body card: meta + optional short title + current chunk.

    After the first few beats, callers pass show_title=False so only the
    spoken sentence appears (less chrome, more gameplay).
    """
    padding = 24
    avatar_size = 44
    title_font = _font(28, bold=True)
    meta_font = _font(22)
    body_font = _font(28)

    title_lines = _wrap(post.title, width=40)[:max_title_lines] if show_title else []
    chunk_lines = _wrap((chunk or "").strip(), width=42)

    line_h_title = 34
    line_h_body = 34
    content_h = (
        padding
        + avatar_size
        + 12
        + len(title_lines) * line_h_title
        + (10 if title_lines else 4)
        + len(chunk_lines) * line_h_body
        + padding
    )
    height = max(140, content_h)
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    _draw_rounded_rect(
        draw, (0, 0, width - 1, height - 1), fill=_CARD, outline=_BORDER, radius=20
    )

    y = _draw_post_header(
        draw, post, padding=padding, avatar_size=avatar_size, meta_font=meta_font
    )
    for line in title_lines:
        draw.text((padding, y), line, font=title_font, fill=_MUTED)
        y += line_h_title

    y += 6 if title_lines else 2
    for line in chunk_lines:
        draw.text((padding, y), line, font=body_font, fill=_TEXT)
        y += line_h_body

    draw.rectangle((0, 0, 8, height), fill=_ORANGE)
    return img


def render_comment_card(
    comment: RedditComment,
    *,
    width: int = 900,
    max_body_chars: int = 280,
) -> Image.Image:
    """Render a single comment card (kept for debugging; story mode skips comments)."""
    padding = 24
    avatar_size = 48
    meta_font = _font(22)
    body_font = _font(26)

    body = (comment.body or "").strip()
    if len(body) > max_body_chars:
        body = body[: max_body_chars - 1].rstrip() + "…"
    body_lines = _wrap(body, width=44)

    line_h = 32
    height = max(
        140,
        padding + avatar_size + 12 + len(body_lines) * line_h + padding,
    )
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    _draw_rounded_rect(draw, (0, 0, width - 1, height - 1), fill=_CARD, outline=_BORDER, radius=20)

    ax, ay = padding, padding
    color = _avatar_color(comment.author)
    draw.ellipse((ax, ay, ax + avatar_size, ay + avatar_size), fill=color)
    initials = _initials(comment.author)
    bbox = draw.textbbox((0, 0), initials, font=meta_font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        (ax + (avatar_size - tw) / 2, ay + (avatar_size - th) / 2 - 2),
        initials,
        font=meta_font,
        fill=(255, 255, 255, 255),
    )

    op_tag = "  ·  OP" if comment.is_op else ""
    meta = f"u/{comment.author}{op_tag}  ·  {_format_score(comment.score)}"
    draw.text((ax + avatar_size + 14, ay + 10), meta, font=meta_font, fill=_MUTED)

    y = ay + avatar_size + 12
    for line in body_lines:
        draw.text((padding, y), line, font=body_font, fill=_TEXT)
        y += line_h
    return img


# First N body-chunk cards keep a muted title; later beats show chunk only.
_BODY_TITLE_BEATS = 2


def export_card_pngs(
    post: RedditPost,
    output_dir: str,
    *,
    card_width: int = 900,
    body_chunks: list[str] | None = None,
    title_beats: int = _BODY_TITLE_BEATS,
) -> dict[str, str]:
    """
    Write card PNGs for the post title and each body chunk.

    Comments are not exported in story mode. Body chunks show the muted title
    only for the first ``title_beats`` cards.
    """
    os.makedirs(output_dir, exist_ok=True)
    paths: dict[str, str] = {}

    chunks = body_chunks if body_chunks is not None else chunk_body_text(post.selftext or "")

    post_title = render_post_card(post, width=card_width, show_body=False)
    post_title_path = os.path.join(output_dir, "card_post_title.png")
    post_title.save(post_title_path, "PNG")
    paths["post_title"] = post_title_path

    # Legacy full-body card (useful for debugging / fallbacks).
    post_full = render_post_card(post, width=card_width, show_body=True)
    post_full_path = os.path.join(output_dir, "card_post.png")
    post_full.save(post_full_path, "PNG")
    paths["post"] = post_full_path

    for index, chunk in enumerate(chunks):
        card = render_body_chunk_card(
            post,
            chunk,
            width=card_width,
            show_title=index < max(0, int(title_beats)),
        )
        path = os.path.join(output_dir, f"card_body_chunk_{index}.png")
        card.save(path, "PNG")
        paths[f"body_chunk_{index}"] = path

    return paths


def list_gameplay_files(directory: str) -> list[str]:
    """Return video files in a gameplay directory (sorted)."""
    if not directory or not os.path.isdir(directory):
        return []
    extensions = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
    files: list[str] = []
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        if os.path.isfile(path) and os.path.splitext(name)[1].lower() in extensions:
            files.append(path)
    return files
