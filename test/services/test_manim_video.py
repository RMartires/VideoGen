import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.models.schema import VideoAspect
from app.services import manim_video
from app.services.manim_video import (
    SceneSpec,
    default_spec,
    render_manim_video,
    validate_or_default,
)


class ValidateOrDefaultTest(unittest.TestCase):
    def test_valid_spec_dict(self):
        raw = {
            "title": "Pythagoras",
            "segments": [
                {"type": "title_card", "title": "Pythagorean theorem"},
                {"type": "equation_reveal", "equations": ["a^2 + b^2 = c^2"]},
            ],
        }
        spec = validate_or_default(raw, "Pythagoras")
        self.assertIsInstance(spec, SceneSpec)
        self.assertEqual(spec.title, "Pythagoras")
        self.assertEqual(len(spec.segments), 2)

    def test_valid_spec_json_string(self):
        raw = json.dumps(
            {"segments": [{"type": "number_line", "x_range": [0, 10]}]}
        )
        spec = validate_or_default(raw, "Numbers")
        self.assertEqual(len(spec.segments), 1)
        self.assertEqual(spec.segments[0].type, "number_line")

    def test_malformed_json_falls_back_to_default(self):
        spec = validate_or_default("{not valid json", "Calculus")
        self.assertEqual(spec.title, "Calculus")
        self.assertTrue(spec.segments)

    def test_empty_dict_falls_back(self):
        spec = validate_or_default({}, "Algebra")
        self.assertEqual(spec.title, "Algebra")
        self.assertTrue(spec.segments)

    def test_unknown_segment_types_filtered(self):
        raw = {
            "title": "Mix",
            "segments": [
                {"type": "malicious_code_exec"},
                {"type": "title_card", "title": "Ok"},
            ],
        }
        spec = validate_or_default(raw, "Mix")
        self.assertEqual(len(spec.segments), 1)
        self.assertEqual(spec.segments[0].type, "title_card")

    def test_all_unknown_segments_fall_back_to_default(self):
        raw = {"title": "Bad", "segments": [{"type": "nope"}, {"type": "also_nope"}]}
        spec = validate_or_default(raw, "Geometry")
        # Falls back to the default spec (which has known segment types).
        self.assertTrue(all(s.type in manim_video._SEGMENT_TYPES for s in spec.segments))
        self.assertEqual(spec.title, "Geometry")

    def test_default_spec_is_valid(self):
        spec = default_spec("Fractals")
        self.assertEqual(spec.title, "Fractals")
        self.assertTrue(spec.segments)
        for segment in spec.segments:
            self.assertIn(segment.type, manim_video._SEGMENT_TYPES)

    def test_geometry_segment_types_accepted(self):
        raw = {
            "segments": [
                {"type": "right_triangle", "side_a": 3, "side_b": 4},
                {"type": "pythagorean_triple", "side_a": 3, "side_b": 4},
                {"type": "area_grid", "side": 3},
            ]
        }
        spec = validate_or_default(raw, "Pythagoras")
        self.assertEqual(len(spec.segments), 3)
        self.assertEqual(spec.segments[0].type, "right_triangle")
        self.assertEqual(spec.segments[1].type, "pythagorean_triple")


class ResolutionTest(unittest.TestCase):
    def test_portrait(self):
        self.assertEqual(
            manim_video._resolution_for_aspect(VideoAspect.portrait), (1080, 1920)
        )

    def test_landscape(self):
        self.assertEqual(
            manim_video._resolution_for_aspect(VideoAspect.landscape), (1920, 1080)
        )

    def test_square(self):
        self.assertEqual(
            manim_video._resolution_for_aspect(VideoAspect.square), (1080, 1080)
        )


class RenderManimVideoTest(unittest.TestCase):
    def test_render_builds_command_and_returns_mp4(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            task_path = Path(tmp_dir)

            def fake_run(cmd, **kwargs):
                # Simulate manim writing an mp4 under the media dir.
                media_dir = Path(cmd[cmd.index("--media_dir") + 1])
                out_dir = media_dir / "videos" / "720p30"
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "manim_scene.mp4").write_bytes(b"fake-video")
                result = MagicMock()
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
                # Expose captured args for assertions.
                fake_run.captured = {"cmd": cmd, "env": kwargs.get("env", {})}
                return result

            with patch(
                "app.services.manim_video.utils.task_dir",
                return_value=str(task_path),
            ), patch("app.services.manim_video.subprocess.run", side_effect=fake_run):
                spec = default_spec("Vectors")
                out = render_manim_video(
                    task_id="t1",
                    spec=spec,
                    video_aspect=VideoAspect.portrait,
                    duration=42.0,
                )

            self.assertTrue(os.path.exists(out))
            self.assertEqual(Path(out).name, "manim_scene.mp4")
            # Spec file was written.
            self.assertTrue((task_path / "manim_spec.json").exists())
            # Resolution and duration flow into the command / env.
            cmd = fake_run.captured["cmd"]
            self.assertIn("1080,1920", cmd)
            self.assertEqual(fake_run.captured["env"]["MANIM_TARGET_DURATION"], "42.0")
            self.assertIn("MANIM_SPEC_PATH", fake_run.captured["env"])

    def test_render_raises_on_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            task_path = Path(tmp_dir)
            result = MagicMock()
            result.returncode = 1
            result.stdout = "boom"
            result.stderr = "error"
            with patch(
                "app.services.manim_video.utils.task_dir",
                return_value=str(task_path),
            ), patch(
                "app.services.manim_video.subprocess.run", return_value=result
            ):
                with self.assertRaises(RuntimeError):
                    render_manim_video("t2", default_spec("X"))

    def test_render_raises_when_manim_missing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            task_path = Path(tmp_dir)
            with patch(
                "app.services.manim_video.utils.task_dir",
                return_value=str(task_path),
            ), patch(
                "app.services.manim_video.subprocess.run",
                side_effect=FileNotFoundError(),
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    render_manim_video("t3", default_spec("X"))
                self.assertIn("Manim is not installed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
