"""Fetch and normalize Reddit posts via OAuth or the public .json endpoint."""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urlparse

import requests
from loguru import logger

from app.config import config

_REDDIT_PATH_RE = re.compile(
    r"^/r/(?P<subreddit>[^/]+)/comments/(?P<post_id>[a-z0-9]+)",
    re.IGNORECASE,
)
_SKIP_AUTHORS = {"automoderator", "[deleted]", "[removed]"}
_COMMENT_SOFT_CAP = 280
_COMMENT_CANDIDATE_CAP = 50

# In-memory OAuth token cache (process-local).
_token_cache: dict[str, Any] = {"access_token": None, "expires_at": 0.0}


@dataclass
class RedditComment:
    author: str
    body: str
    score: int
    is_op: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RedditPost:
    id: str
    subreddit: str
    title: str
    selftext: str
    author: str
    score: int
    permalink: str
    url: str
    comments: list[RedditComment] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["comments"] = [c.to_dict() for c in self.comments]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RedditPost":
        comments = [
            RedditComment(
                author=c.get("author", "unknown"),
                body=c.get("body", ""),
                score=int(c.get("score", 0) or 0),
                is_op=bool(c.get("is_op", False)),
            )
            for c in data.get("comments") or []
        ]
        return cls(
            id=str(data.get("id", "")),
            subreddit=str(data.get("subreddit", "")),
            title=str(data.get("title", "")),
            selftext=str(data.get("selftext", "")),
            author=str(data.get("author", "unknown")),
            score=int(data.get("score", 0) or 0),
            permalink=str(data.get("permalink", "")),
            url=str(data.get("url", "")),
            comments=comments,
        )


def parse_reddit_url(url: str) -> tuple[str, str]:
    """
    Return (subreddit, post_id) from a Reddit post URL.

    Accepts www/old/new reddit hosts and optional query fragments.
    """
    raw = (url or "").strip()
    if not raw:
        raise ValueError("reddit_url is required")

    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw

    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if host not in {
        "reddit.com",
        "www.reddit.com",
        "old.reddit.com",
        "new.reddit.com",
        "m.reddit.com",
        "np.reddit.com",
    }:
        raise ValueError(f"not a Reddit URL: {url}")

    match = _REDDIT_PATH_RE.match(parsed.path or "")
    if not match:
        raise ValueError(
            f"could not parse Reddit post path from URL: {url} "
            "(expected /r/<subreddit>/comments/<id>/...)"
        )
    return match.group("subreddit"), match.group("post_id")


def reddit_json_url(url: str) -> str:
    """Build the public .json API URL for a Reddit post."""
    subreddit, post_id = parse_reddit_url(url)
    return f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json"


def oauth_configured() -> bool:
    """True when Reddit script-app client credentials are present."""
    reddit_cfg = getattr(config, "reddit", None) or {}
    client_id = str(reddit_cfg.get("client_id", "") or "").strip()
    client_secret = str(reddit_cfg.get("client_secret", "") or "").strip()
    return bool(client_id and client_secret)


def _user_agent() -> str:
    reddit_cfg = getattr(config, "reddit", None) or {}
    return str(
        reddit_cfg.get(
            "user_agent",
            "MoneyPrinterTurbo/1.3 (Reddit story mode)",
        )
    )


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").strip()
    # Collapse excessive blank lines for TTS.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _truncate_comment_body(body: str, soft_cap: int = _COMMENT_SOFT_CAP) -> str:
    text = (body or "").strip()
    if len(text) <= soft_cap:
        return text
    return text[: soft_cap - 1].rstrip() + "…"


def comment_entertainment_score(comment: RedditComment) -> float:
    """Higher is better: score rewarded, long walls penalized."""
    length = max(len((comment.body or "").strip()), 1)
    return float(comment.score) / (1.0 + length / 80.0)


def select_comments(
    comments: list[RedditComment],
    limit: int,
    *,
    soft_cap: int = _COMMENT_SOFT_CAP,
) -> list[RedditComment]:
    """
    Rank comments for entertainment and soft-truncate bodies.

    Prefers high-score short punches over long essays.
    ``limit=0`` returns an empty list (story mode omits comments).
    """
    limit = max(0, min(15, int(limit)))
    if limit == 0:
        return []
    ranked = sorted(comments, key=comment_entertainment_score, reverse=True)
    selected: list[RedditComment] = []
    for comment in ranked:
        body = _truncate_comment_body(comment.body, soft_cap=soft_cap)
        if not body:
            continue
        selected.append(
            RedditComment(
                author=comment.author,
                body=body,
                score=comment.score,
                is_op=comment.is_op,
            )
        )
        if len(selected) >= limit:
            break
    return selected


def _collect_comments(
    listing: dict[str, Any],
    op_author: str,
    *,
    candidate_cap: int = _COMMENT_CANDIDATE_CAP,
) -> list[RedditComment]:
    children = (listing.get("data") or {}).get("children") or []
    comments: list[RedditComment] = []
    for child in children:
        if child.get("kind") != "t1":
            continue
        data = child.get("data") or {}
        if data.get("stickied"):
            continue
        author = _clean_text(data.get("author")) or "unknown"
        if author.lower() in _SKIP_AUTHORS:
            continue
        body = _clean_text(data.get("body"))
        if not body:
            continue
        comments.append(
            RedditComment(
                author=author,
                body=body,
                score=int(data.get("score", 0) or 0),
                is_op=author.lower() == (op_author or "").lower(),
            )
        )
        if len(comments) >= candidate_cap:
            break
    return comments


def normalize_listing(
    payload: list[Any] | dict[str, Any],
    *,
    comment_limit: int = 5,
    source_url: str = "",
) -> RedditPost:
    """Normalize a Reddit .json listing response into RedditPost."""
    if isinstance(payload, dict):
        # Some proxies wrap the listing; unwrap if needed.
        if "data" in payload and "children" in (payload.get("data") or {}):
            payload = [payload, {"kind": "Listing", "data": {"children": []}}]
        else:
            raise ValueError("unexpected Reddit JSON shape (expected a list of listings)")

    if not isinstance(payload, list) or len(payload) < 1:
        raise ValueError("empty Reddit JSON response")

    post_listing = payload[0]
    post_children = (post_listing.get("data") or {}).get("children") or []
    if not post_children:
        raise ValueError("Reddit JSON response has no post")

    post_data = post_children[0].get("data") or {}
    author = _clean_text(post_data.get("author")) or "unknown"
    title = _clean_text(post_data.get("title"))
    if not title:
        raise ValueError("Reddit post has no title")

    comment_listing = payload[1] if len(payload) > 1 else {"data": {"children": []}}
    raw_comments = _collect_comments(comment_listing, author)
    comments = select_comments(raw_comments, comment_limit)

    permalink = _clean_text(post_data.get("permalink"))
    canonical = f"https://www.reddit.com{permalink}" if permalink else source_url

    return RedditPost(
        id=str(post_data.get("id") or ""),
        subreddit=_clean_text(post_data.get("subreddit")),
        title=title,
        selftext=_clean_text(post_data.get("selftext")),
        author=author,
        score=int(post_data.get("score", 0) or 0),
        permalink=permalink,
        url=canonical or source_url,
        comments=comments,
    )


def _request_headers(*, bearer: str | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": _user_agent(),
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    return headers


def _tls_verify() -> bool:
    return bool(config.app.get("tls_verify", True))


def _proxies() -> dict | None:
    return config.proxy if config.proxy else None


def _get_oauth_token() -> str:
    """Obtain (and cache) a client-credentials access token."""
    now = time.time()
    cached = _token_cache.get("access_token")
    expires_at = float(_token_cache.get("expires_at") or 0.0)
    if cached and now < expires_at - 30:
        return str(cached)

    reddit_cfg = getattr(config, "reddit", None) or {}
    client_id = str(reddit_cfg.get("client_id", "") or "").strip()
    client_secret = str(reddit_cfg.get("client_secret", "") or "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Reddit OAuth credentials are not configured")

    response = requests.post(
        "https://www.reddit.com/api/v1/access_token",
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
        headers={"User-Agent": _user_agent()},
        timeout=30,
        verify=_tls_verify(),
        proxies=_proxies(),
    )
    response.raise_for_status()
    payload = response.json()
    token = payload.get("access_token")
    if not token:
        raise RuntimeError(f"Reddit OAuth response missing access_token: {payload}")
    expires_in = int(payload.get("expires_in", 3600) or 3600)
    _token_cache["access_token"] = token
    _token_cache["expires_at"] = now + expires_in
    logger.info("obtained Reddit OAuth access token")
    return str(token)


def _fetch_via_oauth(url: str, comment_limit: int) -> RedditPost:
    subreddit, post_id = parse_reddit_url(url)
    token = _get_oauth_token()
    api_url = f"https://oauth.reddit.com/r/{subreddit}/comments/{post_id}"
    logger.info(f"fetching Reddit post via OAuth: {api_url}")
    response = requests.get(
        api_url,
        headers=_request_headers(bearer=token),
        params={"raw_json": "1", "limit": _COMMENT_CANDIDATE_CAP},
        timeout=30,
        verify=_tls_verify(),
        proxies=_proxies(),
    )
    response.raise_for_status()
    return normalize_listing(response.json(), comment_limit=comment_limit, source_url=url)


def _fetch_via_json(url: str, comment_limit: int) -> RedditPost:
    json_url = reddit_json_url(url)
    headers = _request_headers()
    # Prefer a browser-like UA when the configured one is the short default —
    # Reddit frequently 403s short/custom agents from some regions.
    if "MoneyPrinterTurbo" in headers["User-Agent"]:
        headers["User-Agent"] = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    logger.info(f"fetching Reddit post JSON: {json_url}")
    response = requests.get(
        json_url,
        headers=headers,
        params={"raw_json": "1"},
        timeout=30,
        verify=_tls_verify(),
        proxies=_proxies(),
    )
    if response.status_code == 403:
        raise requests.HTTPError(
            "Reddit returned 403 Blocked for the .json API. "
            "Configure [reddit] client_id/client_secret (script app) for OAuth, "
            "use a VPN, or save a fixture for scripts/test_reddit_story.py.",
            response=response,
        )
    response.raise_for_status()
    return normalize_listing(response.json(), comment_limit=comment_limit, source_url=url)


def load_post_from_fixture(path: str, comment_limit: int | None = None) -> RedditPost:
    """Load a RedditPost from a saved JSON fixture (our normalized format or listing)."""
    import json

    reddit_cfg = getattr(config, "reddit", None) or {}
    limit = int(comment_limit if comment_limit is not None else reddit_cfg.get("comment_limit", 0))
    limit = max(0, min(15, limit))

    with open(path, encoding="utf-8") as fp:
        payload = json.load(fp)

    if isinstance(payload, list):
        post = normalize_listing(payload, comment_limit=limit)
    elif isinstance(payload, dict) and "title" in payload:
        post = RedditPost.from_dict(payload)
        post.comments = select_comments(post.comments, limit)
    else:
        raise ValueError(f"unrecognized Reddit fixture format: {path}")
    return post


def fetch_post(url: str, comment_limit: int | None = None) -> RedditPost:
    """Fetch a Reddit post and top comments (OAuth when configured, else .json)."""
    reddit_cfg = getattr(config, "reddit", None) or {}
    limit = int(comment_limit if comment_limit is not None else reddit_cfg.get("comment_limit", 0))
    limit = max(0, min(15, limit))

    post: RedditPost | None = None
    oauth_error: Exception | None = None

    if oauth_configured():
        try:
            post = _fetch_via_oauth(url, limit)
        except Exception as exc:
            oauth_error = exc
            logger.warning(f"Reddit OAuth fetch failed, falling back to .json: {exc}")

    if post is None:
        try:
            post = _fetch_via_json(url, limit)
        except Exception as json_exc:
            if oauth_error is not None:
                raise RuntimeError(
                    f"Reddit OAuth failed ({oauth_error}); .json also failed ({json_exc})"
                ) from json_exc
            raise

    logger.info(
        f"fetched r/{post.subreddit} post {post.id}: "
        f"{len(post.comments)} comments, score={post.score}"
    )
    return post
