"""Unit tests for Reddit Story mode helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.reddit.cards import (
    export_card_pngs,
    list_gameplay_files,
    render_body_chunk_card,
    render_post_card,
)
from app.services.reddit.fetch import (
    RedditComment,
    RedditPost,
    comment_entertainment_score,
    normalize_listing,
    oauth_configured,
    parse_reddit_url,
    reddit_json_url,
    select_comments,
)
from app.services.reddit.script import (
    allocate_segment_times,
    build_script_from_post,
    chunk_body_text,
    narration_segments,
    write_segment_subtitles,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_listing() -> list:
    with open(FIXTURES / "sample_post.json", encoding="utf-8") as fp:
        return json.load(fp)


@pytest.fixture
def sample_post(sample_listing) -> RedditPost:
    return normalize_listing(
        sample_listing,
        comment_limit=5,
        source_url="https://www.reddit.com/r/AskReddit/comments/abc123/example/",
    )


def test_parse_reddit_url_standard():
    sub, post_id = parse_reddit_url(
        "https://www.reddit.com/r/AskReddit/comments/abc123/some_title/"
    )
    assert sub == "AskReddit"
    assert post_id == "abc123"


def test_parse_reddit_url_old_reddit_and_query():
    sub, post_id = parse_reddit_url(
        "https://old.reddit.com/r/tifu/comments/xyz789/title/?utm=1"
    )
    assert sub == "tifu"
    assert post_id == "xyz789"


def test_parse_reddit_url_rejects_non_reddit():
    with pytest.raises(ValueError, match="not a Reddit URL"):
        parse_reddit_url("https://example.com/r/x/comments/abc/")


def test_reddit_json_url():
    assert (
        reddit_json_url(
            "https://www.reddit.com/r/AskReddit/comments/abc123/title/"
        )
        == "https://www.reddit.com/r/AskReddit/comments/abc123.json"
    )


def test_normalize_listing_skips_automod_and_stickied(sample_listing):
    post = normalize_listing(sample_listing, comment_limit=5)
    assert post.title.startswith("What is")
    assert post.author == "storyteller"
    assert post.subreddit == "AskReddit"
    authors = [c.author for c in post.comments]
    assert "AutoModerator" not in authors
    assert "[deleted]" not in authors
    assert "helpful_user" in authors
    assert len(post.comments) == 2


def test_chunk_body_text_splits_sentences():
    text = (
        "First sentence here. Second one is longer and keeps going! "
        "Third? And a short one."
    )
    chunks = chunk_body_text(text, max_chars=140)
    assert len(chunks) >= 3
    assert chunks[0].startswith("First")


def test_build_script_from_post(sample_post):
    script = build_script_from_post(sample_post)
    assert sample_post.title in script
    assert "Once upon a time" in script
    assert "Comment by" not in script
    assert "This reminds me" in script


def test_narration_segments_and_timing(sample_post):
    segments = narration_segments(sample_post)
    assert segments[0]["kind"] == "title"
    assert any(s["kind"] == "body_chunk" for s in segments)
    timed = allocate_segment_times(segments, total_duration=10.0)
    assert timed[0]["start"] == 0.0
    assert timed[-1]["end"] == pytest.approx(10.0)
    assert all(s["end"] > s["start"] for s in timed)
    # Title floor should give the hook a readable share on long scripts.
    assert timed[0]["end"] - timed[0]["start"] >= 0.5


def test_write_segment_subtitles(tmp_path):
    segments = [
        {"text": "Hello world", "start": 0.0, "end": 1.5},
        {"text": "Next line", "start": 1.5, "end": 3.0},
    ]
    path = tmp_path / "sub.srt"
    write_segment_subtitles(segments, str(path))
    content = path.read_text(encoding="utf-8")
    assert "Hello world" in content
    assert "Next line" in content
    from moviepy.video.tools.subtitles import file_to_subtitles

    parsed = file_to_subtitles(str(path))
    assert len(parsed) == 2
    assert all(times is not None for times, _ in parsed)


def test_select_comments_prefers_short_high_score():
    comments = [
        RedditComment("long", "x" * 400, score=100),
        RedditComment("punchy", "You need help", score=57),
        RedditComment("mid", "ok story " * 20, score=80),
    ]
    selected = select_comments(comments, limit=2)
    assert len(selected) == 2
    assert selected[0].author == "punchy" or selected[0].author == "mid"
    # Long wall should lose to punchy when scores are comparable-ish.
    assert all(len(c.body) <= 280 for c in selected)
    assert comment_entertainment_score(comments[1]) > comment_entertainment_score(
        comments[0]
    )


def test_render_post_card_and_export(sample_post, tmp_path):
    img = render_post_card(sample_post, width=600)
    assert img.size[0] == 600
    assert img.size[1] > 100

    chunk_img = render_body_chunk_card(sample_post, "Once upon a time.", width=600)
    assert chunk_img.size[0] == 600

    paths = export_card_pngs(sample_post, str(tmp_path), card_width=600)
    assert os.path.isfile(paths["post"])
    assert os.path.isfile(paths["post_title"])
    assert os.path.isfile(paths["comment_0"])
    assert any(k.startswith("body_chunk_") for k in paths)


def test_list_gameplay_files(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"x")
    (tmp_path / "b.txt").write_text("nope")
    (tmp_path / "c.MOV").write_bytes(b"y")
    files = list_gameplay_files(str(tmp_path))
    names = {os.path.basename(p) for p in files}
    assert names == {"a.mp4", "c.MOV"}


def test_post_roundtrip_dict(sample_post):
    restored = RedditPost.from_dict(sample_post.to_dict())
    assert restored.title == sample_post.title
    assert len(restored.comments) == len(sample_post.comments)
    assert isinstance(restored.comments[0], RedditComment)


def test_oauth_configured_reads_config():
    with patch("app.services.reddit.fetch.config") as mock_cfg:
        mock_cfg.reddit = {"client_id": "", "client_secret": ""}
        assert oauth_configured() is False
        mock_cfg.reddit = {"client_id": "abc", "client_secret": "xyz"}
        assert oauth_configured() is True


def test_fetch_post_uses_oauth_when_configured(sample_listing):
    from app.services.reddit import fetch as fetch_mod

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = sample_listing
    mock_response.status_code = 200

    with (
        patch.object(fetch_mod, "oauth_configured", return_value=True),
        patch.object(fetch_mod, "_get_oauth_token", return_value="tok"),
        patch.object(fetch_mod.requests, "get", return_value=mock_response) as mock_get,
    ):
        post = fetch_mod.fetch_post(
            "https://www.reddit.com/r/AskReddit/comments/abc123/title/",
            comment_limit=2,
        )
    assert post.title.startswith("What is")
    assert mock_get.call_args.kwargs["headers"]["Authorization"] == "Bearer tok"
    assert "oauth.reddit.com" in mock_get.call_args.args[0]
