import json
import os
from pathlib import Path
import re
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

    def test_scan_ignores_dcode_oauth_notice_but_keeps_real_rate_limits(self):
        notice = (
            "openai_codex.py:547: UserWarning: `_ChatOpenAICodex` is experimental and unofficial. "
            "You are responsible for respecting OpenAI's usage policies, rate limits, and safeguards.\n"
        )
        logfile = self.home / "dcode.log"
        logfile.write_text(notice + "Task timed out\n[lanes] exit=124\n", encoding="utf-8")
        clean = self.run_pick("scan", "dcode", str(logfile))
        self.assertEqual(clean.returncode, 0, clean.stderr)
        self.assertIn("scan: dcode clean", clean.stdout)
        self.assertFalse((self.home / ".lanes" / "health.json").exists())

        logfile.write_text(notice + "Error: 429 Too many requests\n", encoding="utf-8")
        limited = self.run_pick("scan", "dcode", str(logfile))
        self.assertEqual(limited.returncode, 0, limited.stderr)
        health = json.loads((self.home / ".lanes" / "health.json").read_text(encoding="utf-8"))
        for lane in ("codex", "dcode"):
            self.assertGreater(health[lane]["until"], time.time())
            self.assertIn("transient", health[lane]["reason"])

    def test_scan_uses_final_lane_exit_not_successful_review_prose(self):
        logfile = self.home / "review.log"
        text = "Review: test real rate-limit and 429 errors.\n[lanes] exit=0\n"
        logfile.write_text(text, encoding="utf-8")
        clean = self.run_pick("scan", "codex", str(logfile))
        self.assertEqual(clean.returncode, 0, clean.stderr)
        self.assertIn("scan: codex clean", clean.stdout)
        self.assertFalse((self.home / ".lanes" / "health.json").exists())

        logfile.write_text(text + "Error: 429 Too many requests\n[lanes] exit=7\n", encoding="utf-8")
        failed = self.run_pick("scan", "codex", str(logfile))
        self.assertEqual(failed.returncode, 0, failed.stderr)
        self.assertIn("marked codex", failed.stdout)

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


class ModelPolicyTest(unittest.TestCase):
    def test_latest_models_contexts_and_efforts_are_pinned(self):
        models = json.loads((ROOT / "config" / "models.json").read_text(encoding="utf-8"))
        for role in ("architecture_advisor", "rjv_implementer", "rjv_judge"):
            self.assertEqual(models["claude"][role]["resolved"], "claude-fable-5-1")
            self.assertEqual(models["claude"][role]["context_window"], 1_000_000)
        self.assertEqual(models["codex"]["model"], "gpt-6-astra")
        self.assertEqual(models["codex"]["context_window"], 272_000)
        self.assertEqual(models["codex"]["effective_context_window"], 258_400)
        self.assertEqual(models["codex"]["reasoning_effort"], "max")
        self.assertEqual(models["codex"]["forbidden_effort"], "ultra")
        self.assertEqual(models["dcode"]["model"], "openai_codex:gpt-6-astra")
        self.assertEqual(models["dcode"]["reasoning_effort"], "max")
        self.assertEqual(models["dcode"]["quota_group"], "openai")
        self.assertEqual(models["grok"]["model"], "grok-4.6")
        self.assertEqual(models["grok"]["context_window"], 500_000)
        self.assertEqual(models["grok"]["routine_reasoning_effort"], "high")
        self.assertEqual(models["grok"]["rjv_reasoning_effort"], "xhigh")
        self.assertEqual(models["glm"]["resolved"], "glm-5.3[1m]")
        self.assertEqual(models["glm"]["reasoning_effort"], "max")

    def test_active_surfaces_match_model_policy(self):
        grok_agent = (ROOT / "agents" / "grok-implementer.md").read_text(encoding="utf-8")
        fable_agent = (ROOT / "agents" / "fable-advisor.md").read_text(encoding="utf-8")
        workflow = (ROOT / "workflows" / "race-and-judge.mjs").read_text(encoding="utf-8")
        skill = (ROOT / "skill" / "SKILL.md").read_text(encoding="utf-8")
        rjv_skill = (ROOT / "skills" / "rjv" / "SKILL.md").read_text(encoding="utf-8")
        for content in (grok_agent, workflow, skill, rjv_skill):
            self.assertNotIn("grok-4.5", content)
        self.assertIn("-m grok-4.6", grok_agent)
        self.assertIn("--reasoning-effort high", grok_agent)
        self.assertIn("model: fable", fable_agent)
        self.assertIn("-m grok-4.6 --reasoning-effort xhigh", workflow)
        self.assertIn("model: 'fable'", workflow)
        self.assertIn("Grok 4.6", rjv_skill)
        self.assertIn("Fable 5.1", rjv_skill)
        self.assertNotIn("model: 'opus'", workflow)
        self.assertIn("claude-fable-5-1", workflow)
        codex_agent = (ROOT / "agents" / "codex-implementer.md").read_text(encoding="utf-8")
        dcode_agent = (ROOT / "agents" / "dcode-implementer.md").read_text(encoding="utf-8")
        doctor = (ROOT / "bin" / "omnicode-doctor").read_text(encoding="utf-8")
        for content in (codex_agent, dcode_agent, workflow, skill, rjv_skill, doctor):
            self.assertNotIn("gpt-5.6-sol", content)
            self.assertNotIn("GPT-5.6-Sol", content)
            self.assertRegex(content, r"gpt-6-astra|GPT-6 Astra")
        self.assertIn("-m gpt-6-astra", codex_agent)
        self.assertIn("-M openai_codex:gpt-6-astra", dcode_agent)
        self.assertIn("-m gpt-6-astra -c model_reasoning_effort=max", workflow)

    def test_doctor_checks_codex_by_slug_and_default_context(self):
        doctor = (ROOT / "bin" / "omnicode-doctor").read_text(encoding="utf-8")
        probe = re.search(
            r'if python3 -c "(\nimport json,os\n.*?)" 2>/dev/null; then\n  pass "authenticated Codex catalog',
            doctor,
            re.DOTALL,
        )
        self.assertIsNotNone(probe)
        astra = {
            "slug": "gpt-6-astra",
            "context_window": 272000,
            "max_context_window": 872000,
            "supported_reasoning_levels": [{"effort": "max"}],
        }
        for catalog, expected in (
            ([{"slug": "other-model"}, astra], 0),
            ([{"slug": "other-model"}], 1),
            ([{**astra, "context_window": 128000}], 1),
            ([{**astra, "supported_reasoning_levels": [{"effort": "high"}]}], 1),
        ):
            with self.subTest(catalog=catalog), tempfile.TemporaryDirectory() as temp:
                home = Path(temp)
                (home / ".codex").mkdir()
                (home / ".codex" / "models_cache.json").write_text(
                    json.dumps({"models": catalog}), encoding="utf-8"
                )
                result = subprocess.run(
                    ["python3", "-c", probe.group(1)],
                    env={**os.environ, "HOME": str(home)},
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                self.assertEqual(result.returncode, expected, result.stderr)

    def test_ladders_use_latest_grok_as_first_cross_vendor_review(self):
        ladders = json.loads((ROOT / "config" / "ladders.json").read_text(encoding="utf-8"))
        self.assertEqual(ladders["classes"]["research"][0], "grok")
        self.assertEqual(ladders["classes"]["review"][0], "grok")
        self.assertEqual(ladders["classes"]["longcontext"][:2], ["glm", "grok"])
        self.assertEqual(ladders["classes"]["langchain"][:2], ["dcode", "grok"])


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
        (home / ".claude" / "skills").mkdir(parents=True)
        (home / ".agents").mkdir(parents=True)
        (home / ".agents" / "skills").symlink_to(home / ".claude" / "skills", target_is_directory=True)
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

    def test_apply_refuses_a_real_agents_skills_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            (home / ".agents" / "skills").mkdir(parents=True)
            (home / ".claude" / "skills").mkdir(parents=True)
            marker = home / ".agents" / "skills" / "keep-me"
            marker.write_text("keep me\n", encoding="utf-8")
            result = subprocess.run(
                [str(ROOT / "scripts" / "apply.sh")],
                env={**os.environ, "HOME": str(home)},
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep me\n")
            self.assertIn("unsafe skills root", result.stderr)

    def test_apply_installs_goal_executable(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            (home / ".local" / "bin").mkdir(parents=True)
            (home / ".uib" / "node_modules" / "playwright").mkdir(parents=True)
            (home / ".claude" / "skills").mkdir(parents=True)
            (home / ".agents").mkdir(parents=True)
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
            self.assertTrue((home / ".agents" / "skills").is_symlink())
            self.assertEqual(
                (home / ".agents" / "skills").resolve(),
                (home / ".claude" / "skills").resolve(),
            )
            goal = home / ".local" / "bin" / "goal"
            self.assertTrue(goal.is_file())
            self.assertTrue(os.access(goal, os.X_OK))
            installed_models = home / ".claude" / "omnicode" / "models.json"
            self.assertEqual(
                json.loads(installed_models.read_text(encoding="utf-8"))["grok"]["model"],
                "grok-4.6",
            )
            policy = json.loads(installed_models.read_text(encoding="utf-8"))
            self.assertEqual(policy["codex"]["model"], "gpt-6-astra")
            self.assertEqual(policy["dcode"]["model"], "openai_codex:gpt-6-astra")
            self.assertEqual(policy["claude"]["rjv_judge"]["resolved"], "claude-fable-5-1")
            installed_rjv = home / ".claude" / "skills" / "rjv" / "SKILL.md"
            self.assertIn("Grok 4.6", installed_rjv.read_text(encoding="utf-8"))
            self.assertIn("GPT-6 Astra", installed_rjv.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
