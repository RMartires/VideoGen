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
    Segment,
    apply_manim_video_defaults,
    apply_subtitle_timing,
    default_spec,
    render_manim_video,
    validate_or_default,
    _group_sentences_into_buckets,
    _srt_timestamp_to_seconds,
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
        self.assertEqual(len(spec.segments), 5)
        self.assertEqual(spec.segments[0].type, "right_triangle")
        self.assertEqual(spec.segments[-1].type, "equation_reveal")
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

    def test_abstract_segments_dropped_from_geometry_spec(self):
        raw = {
            "segments": [
                {"type": "right_triangle", "side_a": 3, "side_b": 4},
                {"type": "squares_on_sides", "side_a": 3, "side_b": 4},
                {"type": "number_line", "x_range": [-5, 5]},
                {"type": "axes_plot", "function": "x"},
                {"type": "area_grid", "side": 5},
            ]
        }
        spec = validate_or_default(raw, "Pythagoras")
        types = [s.type for s in spec.segments]
        self.assertEqual(
            types, ["right_triangle", "squares_on_sides", "area_grid"]
        )

    def test_squares_transform_counts_as_geometry(self):
        raw = {
            "segments": [
                {"type": "squares_transform", "side_a": 3, "side_b": 4},
                {"type": "right_triangle", "side_a": 3, "side_b": 4},
                {"type": "number_line", "x_range": [0, 10]},
            ]
        }
        spec = validate_or_default(raw, "Pythagoras")
        types = [s.type for s in spec.segments]
        self.assertEqual(types, ["squares_transform", "right_triangle"])

    def test_leading_highlight_dropped_mid_highlight_kept(self):
        raw = {
            "segments": [
                {"type": "highlight", "narration_hint": "nothing on screen yet"},
                {"type": "right_triangle", "side_a": 3, "side_b": 4},
                {"type": "highlight", "narration_hint": "that same triangle"},
                {"type": "area_grid", "side": 5},
            ]
        }
        spec = validate_or_default(raw, "Pythagoras")
        types = [s.type for s in spec.segments]
        self.assertEqual(types, ["right_triangle", "highlight", "area_grid"])

    def test_latex_control_chars_repaired(self):
        # JSON decoding turns \times into "<tab>imes" and \neq into
        # "<newline>eq"; validation must restore the backslash commands.
        raw = {
            "segments": [
                {
                    "type": "equation_reveal",
                    "equations": ["1.1\times10^{12}", "a \neq b"],
                }
            ]
        }
        spec = validate_or_default(raw, "Growth")
        self.assertEqual(
            spec.segments[0].equations,
            ["1.1\\times10^{12}", "a \\neq b"],
        )

    def test_new_animated_segment_types_accepted(self):
        raw = {
            "segments": [
                {
                    "type": "counter_doubling",
                    "start_value": 2,
                    "count": 4,
                    "label": "plants",
                },
                {
                    "type": "growth_bars",
                    "values": [2, 20, 200],
                    "labels": ["Day 1", "Day 10", "Day 20"],
                },
                {"type": "value_pop", "caption": "1,200 plants"},
            ]
        }
        spec = validate_or_default(raw, "Exponential")
        types = [s.type for s in spec.segments]
        self.assertEqual(types, ["counter_doubling", "growth_bars", "value_pop"])
        self.assertEqual(spec.segments[0].start_value, 2)
        self.assertEqual(spec.segments[1].values, [2, 20, 200])

    def test_abstract_growth_segments_dropped_from_geometry_spec(self):
        raw = {
            "segments": [
                {"type": "right_triangle", "side_a": 3, "side_b": 4},
                {"type": "squares_on_sides", "side_a": 3, "side_b": 4},
                {"type": "counter_doubling", "start_value": 2},
                {"type": "growth_bars", "values": [1, 2, 4]},
                {"type": "value_pop", "caption": "25"},
                {"type": "area_grid", "side": 5},
            ]
        }
        spec = validate_or_default(raw, "Pythagoras")
        types = [s.type for s in spec.segments]
        self.assertEqual(
            types,
            ["right_triangle", "squares_on_sides", "area_grid"],
        )

    def test_micro_segment_timing_allows_shorter_gaps(self):
        srt_lines = []
        t = 0.0
        for i in range(12):
            start = t
            end = t + 1.0
            srt_lines.append(
                f"{i + 1}\n"
                f"00:00:{int(start):02d},{int((start % 1) * 1000):03d} --> "
                f"00:00:{int(end):02d},{int((end % 1) * 1000):03d}\n"
                f"beat number {i + 1}\n"
            )
            t += 1.0
        handle = tempfile.NamedTemporaryFile("w", suffix=".srt", delete=False)
        handle.write("\n".join(srt_lines))
        handle.close()
        try:
            segments = [
                Segment(type="value_pop", caption=f"Beat {i}", narration_hint=f"beat number {i + 1}")
                for i in range(12)
            ]
            timed = apply_subtitle_timing(
                SceneSpec(segments=segments),
                subtitle_path=handle.name,
                video_script="",
                total_duration=12.0,
            )
            gaps = [
                timed.segments[i + 1].start - timed.segments[i].start
                for i in range(len(timed.segments) - 1)
            ]
            self.assertTrue(all(g >= 1.0 for g in gaps))
        finally:
            os.unlink(handle.name)

    def test_abstract_segments_kept_without_geometry(self):
        raw = {
            "segments": [
                {"type": "number_line", "x_range": [0, 10]},
                {"type": "bullet_points", "title": "Facts", "points": ["a"]},
            ]
        }
        spec = validate_or_default(raw, "Numbers")
        self.assertEqual(len(spec.segments), 2)


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
                "app.services.manim.video.utils.task_dir",
                return_value=str(task_path),
            ), patch("app.services.manim.video.subprocess.run", side_effect=fake_run):
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
                "app.services.manim.video.utils.task_dir",
                return_value=str(task_path),
            ), patch(
                "app.services.manim.video.subprocess.run", return_value=result
            ):
                with self.assertRaises(RuntimeError):
                    render_manim_video("t2", default_spec("X"))

    def test_render_freeze_extends_short_output(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            task_path = Path(tmp_dir)
            calls = []

            def fake_run(cmd, **kwargs):
                calls.append(cmd)
                if "--media_dir" in cmd:
                    media_dir = Path(cmd[cmd.index("--media_dir") + 1])
                    out_dir = media_dir / "videos" / "720p30"
                    out_dir.mkdir(parents=True, exist_ok=True)
                    (out_dir / "manim_scene.mp4").write_bytes(b"short-video")
                result = MagicMock()
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
                return result

            with patch(
                "app.services.manim.video.utils.task_dir",
                return_value=str(task_path),
            ), patch(
                "app.services.manim.video.subprocess.run", side_effect=fake_run
            ), patch(
                "app.services.manim.video._probe_duration", return_value=40.0
            ):
                out = render_manim_video(
                    task_id="t-short",
                    spec=default_spec("X"),
                    duration=49.0,
                )

            # A tpad freeze-extend command was attempted for the ~9s shortfall.
            ffmpeg_cmds = [c for c in calls if c and c[0] == "ffmpeg"]
            self.assertEqual(len(ffmpeg_cmds), 1)
            vf = ffmpeg_cmds[0][ffmpeg_cmds[0].index("-vf") + 1]
            self.assertIn("tpad=stop_mode=clone", vf)
            self.assertIn("stop_duration=9.000", vf)
            # Mocked ffmpeg wrote no file, so it fell back to the raw copy.
            self.assertTrue(os.path.exists(out))
            self.assertEqual(Path(out).read_bytes(), b"short-video")

    def test_render_raises_when_manim_missing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            task_path = Path(tmp_dir)
            with patch(
                "app.services.manim.video.utils.task_dir",
                return_value=str(task_path),
            ), patch(
                "app.services.manim.video.subprocess.run",
                side_effect=FileNotFoundError(),
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    render_manim_video("t3", default_spec("X"))
                self.assertIn("Manim is not installed", str(ctx.exception))


class SubtitleTimingTest(unittest.TestCase):
    def test_srt_timestamp_to_seconds(self):
        self.assertAlmostEqual(_srt_timestamp_to_seconds("00:00:12,900"), 12.9)

    def test_group_sentences_into_buckets(self):
        sentences = ["One.", "Two.", "Three.", "Four.", "Five."]
        buckets = _group_sentences_into_buckets(sentences, 3)
        self.assertEqual(len(buckets), 3)
        self.assertIn("One", buckets[0])

    def _make_srt(self) -> str:
        srt = """1
00:00:00,100 --> 00:00:05,000
Picture a triangle with legs a and b

2
00:00:05,000 --> 00:00:10,000
Now imagine building a square on each side

3
00:00:10,000 --> 00:00:15,000
Nine plus sixteen gives twenty-five
"""
        handle = tempfile.NamedTemporaryFile("w", suffix=".srt", delete=False)
        handle.write(srt)
        handle.close()
        return handle.name

    def _make_spec(self) -> SceneSpec:
        return SceneSpec(
            segments=[
                Segment(
                    type="right_triangle",
                    narration_hint="triangle with legs a and b",
                ),
                Segment(
                    type="squares_on_sides",
                    narration_hint="building a square on each side",
                ),
                Segment(
                    type="pythagorean_triple",
                    narration_hint="nine plus sixteen",
                ),
            ]
        )

    _SCRIPT = (
        "Picture a triangle with legs a and b. "
        "Now imagine building a square on each side. "
        "Nine plus sixteen gives twenty-five."
    )

    def test_apply_subtitle_timing_assigns_starts_and_durations(self):
        srt_path = self._make_srt()
        try:
            timed = apply_subtitle_timing(
                self._make_spec(),
                subtitle_path=srt_path,
                video_script=self._SCRIPT,
                total_duration=15.0,
            )
            self.assertEqual(len(timed.segments), 3)
            starts = [s.start for s in timed.segments]
            # First visual covers the opening; the rest land on their lines.
            self.assertEqual(starts[0], 0.0)
            self.assertEqual(starts, sorted(starts))
            for prev, cur in zip(starts, starts[1:]):
                self.assertGreaterEqual(cur - prev, 2.0)
            self.assertAlmostEqual(starts[1], 5.0, delta=0.5)
            self.assertAlmostEqual(starts[2], 10.0, delta=0.5)
            # Durations tile the full audio with no gap at the end.
            self.assertAlmostEqual(
                sum(s.duration for s in timed.segments), 15.0, delta=0.01
            )
            self.assertAlmostEqual(
                starts[-1] + timed.segments[-1].duration, 15.0, delta=0.01
            )
        finally:
            os.unlink(srt_path)

    def test_verbatim_hint_beats_fuzzy_early_match(self):
        # Line 1 shares many words with the hint, but the hint appears
        # verbatim only in line 3; the segment must anchor to line 3.
        srt = """1
00:00:00,100 --> 00:00:04,000
Squares and sides are drawn on each figure we see

2
00:00:04,000 --> 00:00:08,000
It all comes down to one geometric trick

3
00:00:08,000 --> 00:00:12,000
Picture a perfect square drawn on each side
"""
        handle = tempfile.NamedTemporaryFile("w", suffix=".srt", delete=False)
        handle.write(srt)
        handle.close()
        try:
            spec = SceneSpec(
                segments=[
                    Segment(
                        type="right_triangle",
                        narration_hint="squares and sides are drawn",
                    ),
                    Segment(
                        type="squares_on_sides",
                        narration_hint="a perfect square drawn on each side",
                    ),
                ]
            )
            timed = apply_subtitle_timing(
                spec,
                subtitle_path=handle.name,
                video_script="",
                total_duration=12.0,
            )
            self.assertEqual(timed.segments[0].start, 0.0)
            self.assertAlmostEqual(timed.segments[1].start, 8.0, delta=0.1)
        finally:
            os.unlink(handle.name)

    def test_apply_subtitle_timing_monotonic_when_hints_out_of_order(self):
        srt_path = self._make_srt()
        try:
            spec = SceneSpec(
                segments=[
                    Segment(
                        type="pythagorean_triple",
                        narration_hint="nine plus sixteen",
                    ),
                    Segment(
                        type="right_triangle",
                        narration_hint="triangle with legs a and b",
                    ),
                ]
            )
            timed = apply_subtitle_timing(
                spec,
                subtitle_path=srt_path,
                video_script=self._SCRIPT,
                total_duration=15.0,
            )
            starts = [s.start for s in timed.segments]
            self.assertEqual(starts[0], 0.0)
            self.assertEqual(starts, sorted(starts))
        finally:
            os.unlink(srt_path)


class ManimDefaultsTest(unittest.TestCase):
    def test_apply_manim_video_defaults(self):
        from app.models.schema import VideoParams

        params = VideoParams(
            video_subject="Test",
            video_script="",
            video_source="manim",
            font_name="STHeitiMedium.ttc",
            font_size=60,
            subtitle_position="bottom",
        )
        apply_manim_video_defaults(params)
        self.assertEqual(params.font_name, "BeVietnamPro-Bold.ttf")
        self.assertEqual(params.font_size, 48)
        self.assertEqual(params.subtitle_position, "custom")
        self.assertEqual(params.custom_position, 78.0)
        self.assertTrue(params.rounded_subtitle_background)


if __name__ == "__main__":
    unittest.main()
