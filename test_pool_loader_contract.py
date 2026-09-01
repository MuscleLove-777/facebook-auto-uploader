# -*- coding: utf-8 -*-
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pool_loader


class FacebookPoolLoaderContractTests(unittest.TestCase):
    def _write_pool(self, root: str, *, x_action: str, x_cadence: float) -> Path:
        path = Path(root) / "content_pool.json"
        path.write_text(
            json.dumps(
                {
                    "version": "contract-test",
                    "generic_trend_candidates": ["固有名詞候補"],
                    "lanes": {
                        "safe_fitness": {
                            "base_tags": ["筋肉女子"],
                            "trend_tags": ["筋トレ"],
                            "caption_templates": ["見てくれ、この圧。{tags}"],
                            "cta_lines": [
                                "停止媒体へ → https://x.com/example",
                                "まとめハブ → https://example.invalid/hub",
                            ],
                            "ng_words": ["adult"],
                        }
                    },
                    "channel_weights": {
                        "x": {
                            "action": x_action,
                            "cadence_factor": x_cadence,
                        }
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return path

    def test_facebook_excludes_generic_trend_and_held_channel_cta(self):
        with tempfile.TemporaryDirectory() as tmp:
            pool = self._write_pool(tmp, x_action="hold", x_cadence=0)
            with patch.object(pool_loader, "LOCAL_POOL", pool):
                insights = pool_loader.as_insights("safe_fitness", platform="facebook")

        self.assertEqual(["筋肉女子", "筋トレ"], insights["recommended_tags"])
        self.assertEqual(1, len(insights["recommended_ctas"]))
        self.assertIn("utm_source=facebook", insights["recommended_ctas"][0])
        self.assertNotIn("x.com", insights["recommended_ctas"][0])

    def test_enabled_channel_cta_remains_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            pool = self._write_pool(tmp, x_action="amplify", x_cadence=1.0)
            with patch.object(pool_loader, "LOCAL_POOL", pool):
                insights = pool_loader.as_insights("safe_fitness", platform="facebook")

        self.assertEqual(2, len(insights["recommended_ctas"]))
        self.assertTrue(all("utm_source=facebook" in c for c in insights["recommended_ctas"]))

    def test_upload_sets_utf8_console_for_windows_dry_run(self):
        source = Path(__file__).with_name("upload.py").read_text(encoding="utf-8")
        self.assertIn('sys.stdout.reconfigure(encoding="utf-8")', source)
        self.assertIn('sys.stderr.reconfigure(encoding="utf-8")', source)


if __name__ == "__main__":
    unittest.main()
