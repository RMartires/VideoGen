import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.llm import build_style_script_prompt
from pipeline import (
    PipelineConfig,
    _build_instagram_caption,
    _build_video_payload,
    _parse_topics_response,
    _resolve_local_video_path,
    _slugify,
    _write_upload_checklist,
    ReelResult,
)


class PipelineTopicParsingTest(unittest.TestCase):
    def test_parse_json_array(self):
        raw = '["Topic one", "Topic two"]'
        self.assertEqual(_parse_topics_response(raw, 2), ["Topic one", "Topic two"])

    def test_parse_numbered_list(self):
        raw = """
        1. First resume tip
        2. Second resume tip
        """
        self.assertEqual(
            _parse_topics_response(raw, 2),
            ["First resume tip", "Second resume tip"],
        )


class PipelineHelpersTest(unittest.TestCase):
    def test_build_video_payload_includes_chatterbox_prompt(self):
        cfg = PipelineConfig(voice_name="chatterbox:Abigail.wav-Female")
        payload = _build_video_payload("Resume tip", cfg)

        self.assertEqual(payload["voice_name"], "chatterbox:Abigail.wav-Female")
        self.assertIn("Chatterbox-Turbo", payload["video_script_prompt"])
        self.assertIn("HOOK VOICE", payload["video_script_prompt"])
        self.assertIn("[gasp]", payload["video_script_prompt"])
        self.assertEqual(payload["voice_volume"], 1.6)

    def test_build_video_payload_includes_hook_prompt_for_edge(self):
        cfg = PipelineConfig(voice_name="en-US-AriaNeural-Female")
        payload = _build_video_payload("Resume tip", cfg)

        self.assertIn("video_script_prompt", payload)
        self.assertIn("first 3-5 seconds", payload["video_script_prompt"])
        self.assertNotIn("Chatterbox-Turbo", payload["video_script_prompt"])
        self.assertEqual(payload["bgm_type"], "")
        self.assertEqual(payload["voice_volume"], 1.6)

    def test_build_video_payload_for_manim_math_explainer(self):
        cfg = PipelineConfig(
            voice_name="en-US-AriaNeural-Female",
            video_source="manim",
            script_style="math-explainer",
        )
        payload = _build_video_payload("The Pythagorean theorem", cfg)

        self.assertEqual(payload["video_source"], "manim")
        prompt = payload["video_script_prompt"]
        self.assertIn("math-explainer", prompt)
        self.assertIn("ONE mathematical idea", prompt)
        self.assertNotIn("Chatterbox-Turbo", prompt)

    def test_math_explainer_style_prompt_selected(self):
        prompt = build_style_script_prompt(style="math-explainer", chatterbox=False)
        self.assertIn("math-explainer video", prompt)
        # Should not be the default reel prompt.
        self.assertNotIn("scroll-stopper", prompt)

    def test_slugify(self):
        self.assertEqual(
            _slugify("3 Resume Mistakes!!!"),
            "3-resume-mistakes",
        )

    def test_build_instagram_caption(self):
        caption = _build_instagram_caption(
            {
                "caption": "Save this resume tip.",
                "hashtags": ["#resume", "#jobs"],
            }
        )
        self.assertIn("Save this resume tip.", caption)
        self.assertIn("#resume #jobs", caption)

    def test_resolve_local_video_path_from_task_dir(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            task_id = "abc-123"
            task_path = Path(tmp_dir) / task_id
            task_path.mkdir(parents=True)
            video_file = task_path / "final-1.mp4"
            video_file.write_bytes(b"fake")

            def fake_task_dir(sub_dir: str = "") -> str:
                if sub_dir == task_id:
                    return str(task_path)
                return str(task_path.parent)

            with patch("pipeline.utils.task_dir", side_effect=fake_task_dir):
                resolved = _resolve_local_video_path(
                    task_id,
                    f"http://127.0.0.1:8080/tasks/{task_id}/final-1.mp4",
                )
                self.assertEqual(resolved, video_file.resolve())

    def test_write_upload_checklist(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            outbox_dir = Path(tmp_dir)
            results = [
                ReelResult(
                    topic="Resume tip one",
                    success=True,
                    outbox_path=str(outbox_dir / "01-resume-tip-one.mp4"),
                    caption="Caption one\n\n#resume",
                ),
                ReelResult(
                    topic="Resume tip two",
                    success=True,
                    outbox_path=str(outbox_dir / "02-resume-tip-two.mp4"),
                    caption="Caption two\n\n#jobs",
                ),
            ]
            checklist = _write_upload_checklist(outbox_dir, results, post_limit=1)
            content = checklist.read_text(encoding="utf-8")
            self.assertIn("Post today", content)
            self.assertIn("Save for later", content)
            self.assertIn("01-resume-tip-one.mp4", content)
            self.assertIn("02-resume-tip-two.mp4", content)


if __name__ == "__main__":
    unittest.main()
