"""Offline byte-identity tests for relocated approved media."""
import ast
import hashlib
import os
import tempfile
import unittest
from pathlib import Path


class ApprovedMediaRelocationTests(unittest.TestCase):
    def load_scope(self, roots):
        source = Path(__file__).with_name("auto_post_facebook.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        wanted = {"_norm", "_sha256", "_media_candidate_index", "_resolve_approved_path"}
        selected = ast.Module(body=[node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in wanted], type_ignores=[])
        scope = {
            "os": os,
            "hashlib": hashlib,
            "APPROVED_MEDIA_ROOTS": roots,
            "_MEDIA_CANDIDATE_INDEX": None,
        }
        exec(compile(selected, "offline_relocation", "exec"), scope)
        return scope

    def test_missing_original_resolves_only_exact_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            moved = root / "nested" / "approved.mp4"
            moved.parent.mkdir()
            moved.write_bytes(b"approved-safe-fixture")
            expected = hashlib.sha256(moved.read_bytes()).hexdigest()
            scope = self.load_scope([str(root)])
            result = scope["_resolve_approved_path"]({
                "path": str(root / "old" / "approved.mp4"),
                "sha256": expected,
            })
            self.assertEqual(os.path.normcase(str(moved)), os.path.normcase(result))

    def test_same_name_with_wrong_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            moved = root / "approved.mp4"
            moved.write_bytes(b"different-bytes")
            scope = self.load_scope([str(root)])
            result = scope["_resolve_approved_path"]({
                "path": str(root / "old" / "approved.mp4"),
                "sha256": hashlib.sha256(b"expected-bytes").hexdigest(),
            })
            self.assertIsNone(result)

    def test_relocation_without_approval_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "approved.mp4").write_bytes(b"unverifiable")
            scope = self.load_scope([str(root)])
            result = scope["_resolve_approved_path"]({
                "path": str(root / "old" / "approved.mp4"),
                "sha256": "",
            })
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
