"""Offline selection tests: never import uploader credential/API setup."""
import ast
import datetime
import io
import os
import random
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock


class MediaPoolOutcomeTests(unittest.TestCase):
    def execute(self, metas, history, existing):
        source = Path(__file__).with_name("auto_post_facebook.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        selected = ast.Module(body=[node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in {"pick_video", "run"}],
            type_ignores=[])

        class Clock(datetime.datetime):
            @classmethod
            def now(cls):
                return cls(2026, 8, 31, 20, 30)

        post = Mock(return_value=0)
        scope = {
            "os": types.SimpleNamespace(environ={}, path=types.SimpleNamespace(
                exists=lambda p: p in existing, basename=os.path.basename)),
            "datetime": types.SimpleNamespace(datetime=Clock), "random": random,
            "time": types.SimpleNamespace(strftime=lambda _: "2026-08-31"),
            "load_approved_entries": lambda: metas,
            "load_posted": lambda: {"files": history},
            "_resolve_approved_path": lambda m: m["path"] if m["path"] in existing else None,
            "_norm": lambda p: p, "_post": post,
            "APPROVED_LOG": "offline-approval-fixture.json",
        }
        exec(compile(selected, "offline_selection", "exec"), scope)
        output = io.StringIO()
        with redirect_stdout(output):
            result = scope["run"](now=True)
        return result, output.getvalue(), post

    def test_all_missing_is_hold_not_successful_cooldown(self):
        result, output, post = self.execute([{"path": "missing.mp4"}], [], set())
        self.assertEqual(3, result)
        self.assertIn("HOLD_MEDIA", output)
        self.assertNotIn("14日以内", output)
        post.assert_not_called()

    def test_real_cooldown_remains_normal_skip(self):
        result, output, post = self.execute([{"path": "present.mp4"}],
            [{"abspath": "present.mp4", "uploaded_at": "2026-08-30 18:34:00"}],
            {"present.mp4"})
        self.assertEqual(0, result)
        self.assertIn("14日以内", output)
        post.assert_not_called()

    def test_missing_plus_cooldown_reports_incomplete_pool(self):
        result, output, post = self.execute(
            [{"path": "missing.mp4"}, {"path": "present.mp4"}],
            [{"abspath": "present.mp4", "uploaded_at": "2026-08-30 18:34:00"}],
            {"present.mp4"})
        self.assertEqual(3, result)
        self.assertIn("1/2", output)
        post.assert_not_called()

    def test_valid_fresh_candidate_still_works(self):
        result, _, post = self.execute(
            [{"path": "missing.mp4"}, {"path": "fresh.mp4"}], [], {"fresh.mp4"})
        self.assertEqual(0, result)
        post.assert_called_once_with("fresh.mp4", "")

    def test_relocated_path_keeps_cooldown_by_basename(self):
        result, output, post = self.execute(
            [{"path": "new/place/present.mp4"}],
            [{"abspath": "old/place/present.mp4", "uploaded_at": "2026-08-30 18:34:00"}],
            {"new/place/present.mp4"})
        self.assertEqual(0, result)
        self.assertIn("14日以内", output)
        post.assert_not_called()

    def test_empty_pool_never_posts(self):
        result, _, post = self.execute([], [], set())
        self.assertEqual(0, result)
        post.assert_not_called()

    def test_hidden_wrapper_preserves_synchronous_child_exit(self):
        wrapper = Path(__file__).with_name("run_hidden.vbs").read_text(encoding="utf-8")
        self.assertIn('exitCode = CreateObject("WScript.Shell").Run ', wrapper)
        self.assertIn(', 0, True', wrapper)
        self.assertIn('WScript.Quit exitCode', wrapper)


if __name__ == "__main__":
    unittest.main()
