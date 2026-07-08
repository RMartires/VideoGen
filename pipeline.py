#!/usr/bin/env python3
"""
Automated reel pipeline for MoneyPrinterTurbo.

Flow:
  1. Research a niche domain and produce N reel topics (LLM)
  2. Start the local API server
  3. Generate N vertical reels via POST /api/v1/videos
  4. Copy finished reels to storage/ready-to-post/YYYY-MM-DD/
  5. Write an upload checklist with Instagram captions (manual posting)
  6. Stop the server when finished

Usage:
  uv run python pipeline.py
  uv run python pipeline.py --count 3 --domain "Resume / Job seekers / tips"
  uv run python pipeline.py --topics-file topics.txt
  uv run python pipeline.py --post-limit 2
  uv run python pipeline.py --count 1 --voice-name "chatterbox:Emily.wav-Female"

Requires config.toml with LLM and Pexels/Pixabay keys.
Chatterbox: set [chatterbox] base_url and pick a voice like chatterbox:Emily.wav-Female.
Upload-Post is optional; leave upload_post_auto_upload = false for manual posting.
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence
from urllib.parse import urlparse

import requests
from loguru import logger

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import config  # noqa: E402
from app.models import const  # noqa: E402
from app.services import voice as voice_service  # noqa: E402
from app.services.llm import (  # noqa: E402
    build_style_script_prompt,
    _generate_response,
    generate_social_metadata,
)
from app.utils import utils  # noqa: E402

DEFAULT_DOMAIN = "Resume / Job seekers / tips"
DEFAULT_COUNT = 3
DEFAULT_POST_LIMIT = 2
DEFAULT_LANGUAGE = "English"
DEFAULT_VOICE = "en-US-AriaNeural-Female"
DEFAULT_VOICE_VOLUME = 1.6
DEFAULT_POLL_INTERVAL = 5
DEFAULT_SERVER_TIMEOUT = 120
DEFAULT_TASK_TIMEOUT = 3600
OUTBOX_DIR = ROOT_DIR / "storage" / "ready-to-post"
CHECKLIST_FILENAME = "UPLOAD-CHECKLIST.md"


@dataclass
class ReelResult:
    topic: str
    task_id: str | None = None
    success: bool = False
    video_path: str | None = None
    outbox_path: str | None = None
    caption: str | None = None
    hashtags: list[str] = field(default_factory=list)
    script: str | None = None
    cross_posted: bool | None = None
    error: str | None = None


@dataclass
class PipelineConfig:
    domain: str = DEFAULT_DOMAIN
    count: int = DEFAULT_COUNT
    post_limit: int = DEFAULT_POST_LIMIT
    language: str = DEFAULT_LANGUAGE
    voice_name: str = DEFAULT_VOICE
    video_source: str = "pexels"
    video_aspect: str = "9:16"
    paragraph_number: int = 1
    video_clip_duration: int = 5
    match_materials_to_script: bool = True
    subtitle_enabled: bool = True
    bgm_type: str = ""
    voice_volume: float = DEFAULT_VOICE_VOLUME
    script_style: str = "reel"
    host: str = "127.0.0.1"
    port: int = field(default_factory=lambda: int(config.listen_port))
    poll_interval: int = DEFAULT_POLL_INTERVAL
    server_timeout: int = DEFAULT_SERVER_TIMEOUT
    task_timeout: int = DEFAULT_TASK_TIMEOUT
    delay_between_reels: int = 10
    reuse_server: bool = False
    dry_run: bool = False
    topics: list[str] = field(default_factory=list)


class ServerProcess:
    def __init__(self, host: str, port: int, timeout: int):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://{host}:{port}"
        self.process: subprocess.Popen[str] | None = None
        self._started_by_pipeline = False
        self._log_file = None

    def is_healthy(self) -> bool:
        for path in ("/openapi.json", "/docs"):
            try:
                response = requests.get(f"{self.base_url}{path}", timeout=3)
                if response.status_code == 200:
                    return True
            except requests.RequestException:
                continue
        return False

    def start(self) -> None:
        if self.is_healthy():
            logger.info(f"API server already running at {self.base_url}")
            return

        python_cmd = _resolve_python_command()
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT_DIR)

        log_path = ROOT_DIR / "storage" / "pipeline-server.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_file = open(log_path, "a", encoding="utf-8")

        logger.info(f"Starting API server at {self.base_url} ...")
        self.process = subprocess.Popen(
            [*python_cmd, "main.py"],
            cwd=ROOT_DIR,
            env=env,
            stdout=self._log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self._started_by_pipeline = True

        deadline = time.time() + self.timeout
        while time.time() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(
                    f"API server exited early with code {self.process.returncode}. "
                    f"See {log_path}"
                )
            if self.is_healthy():
                logger.success(f"API server is ready at {self.base_url}")
                return
            time.sleep(1)

        raise TimeoutError(
            f"API server did not become healthy within {self.timeout}s. See {log_path}"
        )

    def stop(self) -> None:
        if not self._started_by_pipeline or self.process is None:
            return

        if self.process.poll() is None:
            logger.info("Stopping API server ...")
            self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                logger.warning("API server did not stop gracefully; killing process")
                self.process.kill()
                self.process.wait(timeout=5)

        if self._log_file:
            self._log_file.close()
            self._log_file = None

        self.process = None
        self._started_by_pipeline = False
        logger.info("API server stopped")


def _default_voice_from_config() -> str:
    ui_voice = (config.ui.get("voice_name") or "").strip()
    if ui_voice:
        return ui_voice

    chatterbox_voices = config.chatterbox.get("voices") or []
    if chatterbox_voices:
        first_voice = str(chatterbox_voices[0]).strip()
        if first_voice.startswith("chatterbox:"):
            return first_voice
        return f"chatterbox:{first_voice}"

    return DEFAULT_VOICE


def _chatterbox_voice_file(voice_name: str) -> str:
    parsed = voice_name.split(":", 1)[-1].strip()
    if parsed.endswith(("-Female", "-Male")):
        parsed = parsed.rsplit("-", 1)[0]
    return parsed


def verify_chatterbox_if_needed(voice_name: str) -> None:
    if not voice_service.is_chatterbox_voice(voice_name):
        return

    base_url = (config.chatterbox.get("base_url") or "").strip().rstrip("/")
    if not base_url:
        raise RuntimeError(
            "Chatterbox voice selected but [chatterbox] base_url is missing in config.toml"
        )

    voice_file = _chatterbox_voice_file(voice_name)
    logger.info(
        f"Using Chatterbox TTS at {base_url} with voice {voice_file} "
        f"(model={config.chatterbox.get('model_id', 'chatterbox')})"
    )

    try:
        response = requests.get(
            base_url.replace("/v1", "") + "/get_predefined_voices",
            timeout=10,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Chatterbox server not reachable at {base_url} "
                f"(status {response.status_code})"
            )
        available = {
            item.get("filename", "")
            for item in response.json()
            if isinstance(item, dict)
        }
        if voice_file not in available:
            sample = ", ".join(sorted(available)[:5])
            raise RuntimeError(
                f"Chatterbox voice '{voice_file}' not found. Examples: {sample}"
            )
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Could not reach Chatterbox at {base_url}. Is it running on port 4123?"
        ) from exc


def _resolve_python_command() -> list[str]:
    venv_python = ROOT_DIR / ".venv" / "bin" / "python"
    if venv_python.is_file():
        return [str(venv_python)]
    if shutil.which("uv"):
        return ["uv", "run", "python"]
    return [sys.executable]


def _slugify(text: str, max_length: int = 60) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    if not slug:
        slug = "reel"
    return slug[:max_length].strip("-")


def _resolve_local_video_path(task_id: str, video_ref: str) -> Path:
    if not video_ref:
        raise ValueError("missing video path")

    candidate = Path(video_ref)
    if candidate.is_file():
        return candidate.resolve()

    normalized = video_ref.replace("\\", "/")
    if normalized.startswith(("http://", "https://")):
        normalized = urlparse(normalized).path.lstrip("/")

    tasks_prefix = "tasks/"
    if normalized.startswith(tasks_prefix):
        normalized = normalized[len(tasks_prefix) :]

    if normalized.startswith(f"{task_id}/"):
        local_path = Path(utils.task_dir(task_id)) / Path(normalized).name
        if local_path.is_file():
            return local_path.resolve()

    task_final = Path(utils.task_dir(task_id)) / "final-1.mp4"
    if task_final.is_file():
        return task_final.resolve()

    raise FileNotFoundError(
        f"could not resolve local video for task {task_id}: {video_ref}"
    )


def _build_research_prompt(domain: str, count: int, language: str) -> str:
    return f"""
# Role: Short-form video strategist

## Goal
Research the niche "{domain}" and propose {count} distinct Instagram Reel topics that would perform well with job seekers.

## Requirements
1. Each topic must be specific, actionable, and hook-driven.
2. Prefer formats like "3 resume mistakes...", "Why recruiters reject...", "How to answer tell me about yourself".
3. Avoid duplicate angles.
4. Keep each topic under 120 characters.
5. Topics must be suitable for 30-45 second vertical reels with stock footage.
6. Write topics in {language}.

## Output format
Return ONLY a JSON array of strings. No markdown, no commentary.

Example:
["3 resume mistakes that get you rejected instantly", "How to explain a career gap in interviews"]
""".strip()


def _parse_topics_response(raw: str, count: int) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return []

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            topics = [str(item).strip() for item in parsed if str(item).strip()]
            return topics[:count]
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"\[.*\]", text, re.DOTALL)
    if fenced:
        try:
            parsed = json.loads(fenced.group())
            if isinstance(parsed, list):
                topics = [str(item).strip() for item in parsed if str(item).strip()]
                return topics[:count]
        except json.JSONDecodeError:
            pass

    topics: list[str] = []
    for line in text.splitlines():
        cleaned = re.sub(r"^[\s\d\-\*\.\)]+", "", line).strip().strip('"')
        if cleaned and not cleaned.startswith("{") and not cleaned.startswith("["):
            topics.append(cleaned)
    return topics[:count]


def research_topics(cfg: PipelineConfig) -> list[str]:
    if cfg.topics:
        logger.info(f"Using {len(cfg.topics)} topics from input")
        return cfg.topics[: cfg.count]

    logger.info(f"Researching {cfg.count} reel topics for niche: {cfg.domain}")
    prompt = _build_research_prompt(cfg.domain, cfg.count, cfg.language)
    response = _generate_response(prompt)
    topics = _parse_topics_response(response, cfg.count)

    if len(topics) < cfg.count:
        raise RuntimeError(
            f"Expected {cfg.count} topics but got {len(topics)}. LLM response:\n{response}"
        )

    for index, topic in enumerate(topics, start=1):
        logger.info(f"  Topic {index}: {topic}")

    return topics


def _build_video_payload(topic: str, cfg: PipelineConfig) -> dict:
    payload = {
        "video_subject": topic,
        "video_language": cfg.language,
        "video_aspect": cfg.video_aspect,
        "video_source": cfg.video_source,
        "video_count": 1,
        "paragraph_number": cfg.paragraph_number,
        "video_clip_duration": cfg.video_clip_duration,
        "match_materials_to_script": cfg.match_materials_to_script,
        "voice_name": cfg.voice_name,
        "voice_volume": cfg.voice_volume,
        "subtitle_enabled": cfg.subtitle_enabled,
        "bgm_type": cfg.bgm_type,
    }
    payload["video_script_prompt"] = build_style_script_prompt(
        style=cfg.script_style,
        chatterbox=voice_service.is_chatterbox_voice(cfg.voice_name),
    )
    return payload


def _create_video_task(base_url: str, topic: str, cfg: PipelineConfig) -> str:
    response = requests.post(
        f"{base_url}/api/v1/videos",
        json=_build_video_payload(topic, cfg),
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    task_id = payload.get("data", {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"Missing task_id in API response: {payload}")
    return task_id


def _wait_for_task(base_url: str, task_id: str, cfg: PipelineConfig) -> dict:
    deadline = time.time() + cfg.task_timeout
    while time.time() < deadline:
        response = requests.get(f"{base_url}/api/v1/tasks/{task_id}", timeout=30)
        response.raise_for_status()
        task = response.json().get("data", {})
        state = task.get("state")
        progress = task.get("progress", 0)
        logger.info(f"Task {task_id}: state={state}, progress={progress}%")

        if state == const.TASK_STATE_COMPLETE:
            return task
        if state == const.TASK_STATE_FAILED:
            raise RuntimeError(f"Task {task_id} failed")

        time.sleep(cfg.poll_interval)

    raise TimeoutError(f"Task {task_id} timed out after {cfg.task_timeout}s")


def _build_instagram_caption(metadata: dict) -> str:
    caption = (metadata.get("caption") or "").strip()
    hashtags = metadata.get("hashtags") or []
    hashtag_line = " ".join(hashtags).strip()
    if caption and hashtag_line:
        return f"{caption}\n\n{hashtag_line}"
    return caption or hashtag_line


def _stage_reel_for_manual_upload(
    result: ReelResult,
    index: int,
    outbox_dir: Path,
    cfg: PipelineConfig,
) -> ReelResult:
    if not result.success or not result.task_id or not result.video_path:
        return result

    source_path = _resolve_local_video_path(result.task_id, result.video_path)
    filename = f"{index:02d}-{_slugify(result.topic)}.mp4"
    destination = outbox_dir / filename
    shutil.copy2(source_path, destination)
    result.outbox_path = str(destination)

    metadata = generate_social_metadata(
        video_subject=result.topic,
        video_script=result.script or "",
        language=cfg.language,
        platform="instagram_reels",
    )
    result.caption = _build_instagram_caption(metadata)
    result.hashtags = list(metadata.get("hashtags") or [])

    sidecar = destination.with_suffix(".json")
    sidecar.write_text(
        json.dumps(
            {
                "topic": result.topic,
                "task_id": result.task_id,
                "video_file": destination.name,
                "caption": result.caption,
                "hashtags": result.hashtags,
                "script": result.script,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.success(f"Staged for manual upload: {destination}")
    return result


def generate_reel(base_url: str, topic: str, cfg: PipelineConfig) -> ReelResult:
    result = ReelResult(topic=topic)
    try:
        task_id = _create_video_task(base_url, topic, cfg)
        result.task_id = task_id
        logger.info(f"Started reel task {task_id} for topic: {topic}")

        task = _wait_for_task(base_url, task_id, cfg)
        videos = task.get("videos") or []
        if not videos:
            raise RuntimeError(f"Task {task_id} completed without videos")

        result.video_path = videos[0]
        result.script = task.get("script")
        result.success = True

        cross_post_results = task.get("cross_post_results") or []
        if cross_post_results:
            result.cross_posted = any(item.get("success") for item in cross_post_results)
        else:
            result.cross_posted = None

        logger.success(f"Reel ready: {result.video_path}")
        if result.cross_posted is True:
            logger.success("Instagram upload reported success via Upload-Post")
        elif result.cross_posted is False:
            logger.warning("Instagram upload was attempted but reported failure")
    except Exception as exc:
        result.error = str(exc)
        logger.error(f"Failed reel for topic '{topic}': {exc}")

    return result


def _write_upload_checklist(
    outbox_dir: Path,
    results: list[ReelResult],
    post_limit: int,
) -> Path:
    successful = [result for result in results if result.success and result.outbox_path]
    post_today = successful[:post_limit]
    save_for_later = successful[post_limit:]

    lines = [
        f"# Upload checklist — {outbox_dir.name}",
        "",
        f"Generated **{len(successful)}** reel(s). Post **{min(post_limit, len(successful))}** today, save the rest for upcoming days.",
        "",
        "## How to post (free)",
        "",
        "1. Open Instagram on your phone (or [Meta Business Suite](https://business.facebook.com)).",
        "2. Create a new Reel and upload the `.mp4` file from this folder.",
        "3. Copy the caption from the matching section below (hashtags included).",
        "4. Publish. Repeat tomorrow with the next reel(s) from **Save for later**.",
        "",
    ]

    if post_today:
        lines.extend(["## Post today", ""])
        for result in post_today:
            video_name = Path(result.outbox_path).name
            lines.extend(
                [
                    f"### {video_name}",
                    "",
                    f"- [ ] **Topic:** {result.topic}",
                    f"- [ ] **File:** `{video_name}`",
                    "",
                    "**Caption (copy/paste):**",
                    "",
                    "```",
                    result.caption or result.topic,
                    "```",
                    "",
                ]
            )

    if save_for_later:
        lines.extend(["## Save for later", ""])
        for result in save_for_later:
            video_name = Path(result.outbox_path).name
            lines.extend(
                [
                    f"- [ ] `{video_name}` — {result.topic}",
                ]
            )
        lines.append("")

    failed = [result for result in results if not result.success]
    if failed:
        lines.extend(["## Failed generations", ""])
        for result in failed:
            lines.append(f"- {result.topic}: {result.error or 'unknown error'}")
        lines.append("")

    checklist_path = outbox_dir / CHECKLIST_FILENAME
    checklist_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Wrote upload checklist to {checklist_path}")
    return checklist_path


def _parse_args(argv: Sequence[str] | None = None) -> PipelineConfig:
    parser = argparse.ArgumentParser(
        description="Research topics, generate reels, and stage them for manual Instagram posting."
    )
    parser.add_argument(
        "--domain",
        default=DEFAULT_DOMAIN,
        help=f"Niche to research (default: {DEFAULT_DOMAIN!r})",
    )
    parser.add_argument(
        "--count",
        "-n",
        type=int,
        default=DEFAULT_COUNT,
        help=f"Number of reels to generate (default: {DEFAULT_COUNT})",
    )
    parser.add_argument(
        "--post-limit",
        type=int,
        default=DEFAULT_POST_LIMIT,
        help=f"How many reels to recommend posting today (default: {DEFAULT_POST_LIMIT})",
    )
    parser.add_argument(
        "--language",
        default=DEFAULT_LANGUAGE,
        help=f"Language for scripts and voice (default: {DEFAULT_LANGUAGE})",
    )
    parser.add_argument(
        "--voice-name",
        default=_default_voice_from_config(),
        help="TTS voice (defaults to config.toml [ui] voice_name or [chatterbox] voices)",
    )
    parser.add_argument(
        "--video-source",
        default="pexels",
        choices=["pexels", "pixabay", "coverr", "manim"],
        help="Visual source: stock footage provider or 'manim' for math-explainer visuals",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="API host to connect to",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(config.listen_port),
        help=f"API port (default: {config.listen_port})",
    )
    parser.add_argument(
        "--delay-between-reels",
        type=int,
        default=10,
        help="Seconds to wait between reel jobs",
    )
    parser.add_argument(
        "--reuse-server",
        action="store_true",
        help="Do not stop an already-running API server",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only research topics; do not start server or generate videos",
    )
    parser.add_argument(
        "--topic",
        help="Use a fixed topic instead of LLM research (implies --count 1 unless overridden)",
    )
    parser.add_argument(
        "--bgm-type",
        default="none",
        choices=["none", "random", "custom"],
        help="Background music mode (default: none — voice only)",
    )
    parser.add_argument(
        "--style",
        default="reel",
        choices=["reel", "soulful-poem", "math-explainer"],
        help="Script style: reel (default), soulful-poem, or math-explainer",
    )
    parser.add_argument(
        "--voice-volume",
        type=float,
        default=float(config.ui.get("voice_volume", DEFAULT_VOICE_VOLUME) or DEFAULT_VOICE_VOLUME),
        help="Speech volume multiplier for the final video (default: 1.6)",
    )
    parser.add_argument(
        "--topics-file",
        help="Optional text file with one topic per line (skips LLM research)",
    )
    args = parser.parse_args(argv)

    topics: list[str] = []
    if args.topic:
        topics = [args.topic.strip()]
    elif args.topics_file:
        topics_path = Path(args.topics_file)
        topics = [
            line.strip()
            for line in topics_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    if args.count < 1:
        parser.error("--count must be >= 1")
    if args.post_limit < 1:
        parser.error("--post-limit must be >= 1")

    bgm_type = "" if args.bgm_type == "none" else args.bgm_type

    return PipelineConfig(
        domain=args.domain,
        count=args.count,
        post_limit=args.post_limit,
        language=args.language,
        voice_name=args.voice_name,
        video_source=args.video_source,
        host=args.host,
        port=args.port,
        delay_between_reels=args.delay_between_reels,
        reuse_server=args.reuse_server,
        dry_run=args.dry_run,
        topics=topics,
        bgm_type=bgm_type,
        voice_volume=max(0.6, min(5.0, float(args.voice_volume))),
        script_style=args.style,
    )


def _print_summary(results: list[ReelResult], outbox_dir: Path | None) -> int:
    logger.info("Pipeline summary")
    success_count = 0
    for index, result in enumerate(results, start=1):
        status = "OK" if result.success else "FAILED"
        logger.info(f"  {index}. [{status}] {result.topic}")
        if result.outbox_path:
            logger.info(f"     outbox: {result.outbox_path}")
        if result.error:
            logger.info(f"     error: {result.error}")
        if result.success:
            success_count += 1

    if outbox_dir:
        logger.info(f"Open checklist: {outbox_dir / CHECKLIST_FILENAME}")

    logger.info(f"Completed {success_count}/{len(results)} reels successfully")
    return 0 if success_count == len(results) else 1


def _save_run_report(
    cfg: PipelineConfig,
    topics: list[str],
    results: list[ReelResult],
    outbox_dir: Path | None,
) -> Path:
    report_dir = ROOT_DIR / "storage" / "pipeline-runs"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{time.strftime('%Y%m%d-%H%M%S')}.json"
    payload = {
        "domain": cfg.domain,
        "count": cfg.count,
        "post_limit": cfg.post_limit,
        "outbox_dir": str(outbox_dir) if outbox_dir else None,
        "topics": topics,
        "results": [
            {
                "topic": result.topic,
                "task_id": result.task_id,
                "success": result.success,
                "video_path": result.video_path,
                "outbox_path": result.outbox_path,
                "caption": result.caption,
                "hashtags": result.hashtags,
                "cross_posted": result.cross_posted,
                "error": result.error,
            }
            for result in results
        ],
    }
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"Saved pipeline report to {report_path}")
    return report_path


def run_pipeline(cfg: PipelineConfig) -> int:
    verify_chatterbox_if_needed(cfg.voice_name)
    topics = research_topics(cfg)
    if cfg.dry_run:
        print(json.dumps({"topics": topics}, ensure_ascii=False, indent=2))
        return 0

    outbox_dir = OUTBOX_DIR / time.strftime("%Y-%m-%d")
    outbox_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Manual upload outbox: {outbox_dir}")

    server = ServerProcess(cfg.host, cfg.port, cfg.server_timeout)
    atexit.register(server.stop)

    def _handle_signal(signum, _frame):
        logger.warning(f"Received signal {signum}, shutting down ...")
        server.stop()
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    results: list[ReelResult] = []
    try:
        server.start()
        for index, topic in enumerate(topics):
            if index > 0 and cfg.delay_between_reels > 0:
                logger.info(
                    f"Waiting {cfg.delay_between_reels}s before next reel ..."
                )
                time.sleep(cfg.delay_between_reels)
            result = generate_reel(server.base_url, topic, cfg)
            if result.success:
                result = _stage_reel_for_manual_upload(
                    result, index + 1, outbox_dir, cfg
                )
            results.append(result)
    finally:
        if not cfg.reuse_server:
            server.stop()
        else:
            atexit.unregister(server.stop)

    if any(result.success for result in results):
        _write_upload_checklist(outbox_dir, results, cfg.post_limit)

    _save_run_report(cfg, topics, results, outbox_dir)
    return _print_summary(results, outbox_dir)


def main() -> int:
    cfg = _parse_args()
    logger.info(
        f"MoneyPrinterTurbo pipeline | domain={cfg.domain!r} "
        f"count={cfg.count} post_limit={cfg.post_limit}"
    )
    return run_pipeline(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
