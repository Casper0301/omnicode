import json
import os
from pathlib import Path
import shutil
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
        (self.home / ".grok").mkdir()
        (self.home / ".grok" / "auth.json").write_text(
            json.dumps({"default": {"expires_at": "2100-01-01T00:00:00.000000000Z"}}),
            encoding="utf-8",
        )
        (self.home / ".config" / "zai").mkdir(parents=True)
        (self.home / ".config" / "zai" / "token").write_text("opaque-test-token\n", encoding="utf-8")
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
        result = self.run_pick("code", "--allow", "codex,grok")
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

    def test_expired_grok_credential_routes_to_next_healthy_lane(self):
        (self.home / ".grok" / "auth.json").write_text(
            json.dumps({"default": {"expires_at": "2000-01-01T00:00:00.000000000Z"}}),
            encoding="utf-8",
        )
        result = self.run_pick("code")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "glm\n")
        self.assertIn("grok", result.stderr)

    def test_status_hides_retired_health_entries_and_qualifies_unknown_auth(self):
        (self.home / ".lanes" / "health.json").write_text(
            json.dumps({"gemini": {"until": 0, "reason": "retired"}}),
            encoding="utf-8",
        )
        result = self.run_pick("status")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("gemini", result.stdout)
        self.assertIn("grok     AUTH OK", result.stdout)
        self.assertIn("codex    AVAILABLE (auth not probed)", result.stdout)


@unittest.skipUnless(shutil.which("tmux"), "tmux is required for lanes integration tests")
class LanesExitPropagationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.lanes = ROOT / "bin" / "lanes"
        self.env = {**os.environ, "HOME": str(self.home)}

    def tearDown(self):
        self.temp.cleanup()

    def run_lane(self, exit_code):
        started = subprocess.run(
            [str(self.lanes), "start", "unit", "--", "sh", "-c", f"exit {exit_code}"],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(started.returncode, 0, started.stderr)
        session = next(
            line.split("=", 1)[1]
            for line in started.stdout.splitlines()
            if line.startswith("SESSION=")
        )
        waited = subprocess.run(
            [str(self.lanes), "wait", session, "30"],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=40,
            check=False,
        )
        replayed = subprocess.run(
            [str(self.lanes), "result", session],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return waited, replayed

    def test_success_and_failure_codes_are_persisted(self):
        for vendor_code, public_code in ((0, 0), (7, 7), (142, 124)):
            with self.subTest(vendor_code=vendor_code):
                waited, replayed = self.run_lane(vendor_code)
                self.assertEqual(waited.returncode, public_code, waited.stderr)
                self.assertEqual(replayed.returncode, public_code, replayed.stderr)

    def test_wait_returns_142_only_while_session_is_still_running(self):
        started = subprocess.run(
            [str(self.lanes), "start", "slow-unit", "--", "sh", "-c", "sleep 3; exit 0"],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(started.returncode, 0, started.stderr)
        session = next(
            line.split("=", 1)[1]
            for line in started.stdout.splitlines()
            if line.startswith("SESSION=")
        )
        still_running = subprocess.run(
            [str(self.lanes), "wait", session, "1"],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(still_running.returncode, 142, still_running.stderr)
        completed = subprocess.run(
            [str(self.lanes), "wait", session, "30"],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=40,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


class ApplySafetyTest(unittest.TestCase):
    def test_apply_refuses_to_replace_existing_skill_content(self):
        for root in (".agents", ".claude"):
            for collision in ("file", "directory"):
                with self.subTest(root=root, collision=collision), tempfile.TemporaryDirectory() as temp:
                    self._assert_apply_refuses_collision(Path(temp), root, collision)

    def _assert_apply_refuses_collision(self, home, root, collision):
        (home / ".local" / "bin").mkdir(parents=True)
        (home / ".uib" / "node_modules" / "playwright").mkdir(parents=True)
        (home / ".agents" / "skills").mkdir(parents=True)
        (home / ".claude" / "skills").mkdir(parents=True)
        (home / "Library" / "LaunchAgents").mkdir(parents=True)
        target = home / root / "skills" / "omnicode"
        if collision == "file":
            target.write_text("keep me\n", encoding="utf-8")
        else:
            target.mkdir()
            (target / "keep-me").write_text("keep me\n", encoding="utf-8")

        result = subprocess.run(
            [str(ROOT / "scripts" / "apply.sh")],
            env={**os.environ, "HOME": str(home)},
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(target.is_symlink())
        if collision == "file":
            self.assertTrue(target.is_file())
            self.assertEqual(target.read_text(encoding="utf-8"), "keep me\n")
        else:
            self.assertTrue(target.is_dir())
            self.assertEqual((target / "keep-me").read_text(encoding="utf-8"), "keep me\n")
        self.assertIn("refus", result.stderr.lower())

    def test_apply_installs_goal_executable(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            (home / ".local" / "bin").mkdir(parents=True)
            (home / ".uib" / "node_modules" / "playwright").mkdir(parents=True)
            (home / ".agents" / "skills").mkdir(parents=True)
            (home / ".claude" / "skills").mkdir(parents=True)
            (home / "Library" / "LaunchAgents").mkdir(parents=True)
            launchctl = home / ".local" / "bin" / "launchctl"
            launchctl.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            launchctl.chmod(launchctl.stat().st_mode | stat.S_IXUSR)

            result = subprocess.run(
                [str(ROOT / "scripts" / "apply.sh")],
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{home / '.local' / 'bin'}:/usr/bin:/bin",
                },
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            goal = home / ".local" / "bin" / "goal"
            self.assertTrue(goal.is_file())
            self.assertTrue(os.access(goal, os.X_OK))


if __name__ == "__main__":
    unittest.main()
