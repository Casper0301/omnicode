import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
LANE_PICK = ROOT / "bin" / "lane-pick"


class LanePickAllowlistTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        (self.home / ".claude" / "omnicode").mkdir(parents=True)
        (self.home / ".lanes").mkdir()
        (self.home / "bin").mkdir()
        (self.home / ".claude" / "omnicode" / "ladders.json").write_text(
            json.dumps({
                "classes": {"code": ["grok", "glm", "codex", "claude"]},
                "quota_groups": {"openai": ["codex", "dcode"]},
            }),
            encoding="utf-8",
        )
        for binary in ("grok", "glm", "codex"):
            path = self.home / "bin" / binary
            path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "PATH": f"{self.home / 'bin'}:/usr/bin:/bin",
        }

    def tearDown(self):
        self.temp.cleanup()

    def run_pick(self, *args):
        return subprocess.run(
            [str(LANE_PICK), *args],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )

    def test_allowlist_keeps_ladder_order(self):
        result = self.run_pick("code", "--allow", "grok,codex")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "grok\n")

    def test_allowlist_skips_cooled_lane_and_unsupported_middle_lane(self):
        (self.home / ".lanes" / "health.json").write_text(
            json.dumps({"grok": {"until": time.time() + 3600, "reason": "quota"}}),
            encoding="utf-8",
        )
        result = self.run_pick("code", "--allow", "grok,codex")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "codex\n")
        self.assertIn("grok", result.stderr)
        self.assertNotIn("glm", result.stdout)

    def test_allowlist_rejects_empty_duplicate_unknown_and_out_of_ladder_lanes(self):
        for value in ("", "grok,grok", "grok,unknown", "dcode"):
            with self.subTest(value=value):
                result = self.run_pick("code", "--allow", value)
                self.assertEqual(result.returncode, 2)
                self.assertIn("allow", result.stderr.lower())

    def test_allowlist_requires_exact_two_argument_form(self):
        for args in (("code", "--allow"), ("code", "--allow", "grok", "extra"), ("code", "--bogus", "grok")):
            with self.subTest(args=args):
                result = self.run_pick(*args)
                self.assertEqual(result.returncode, 2)

    def test_legacy_class_resolution_is_unchanged(self):
        result = self.run_pick("code")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "grok\n")


if __name__ == "__main__":
    unittest.main()
