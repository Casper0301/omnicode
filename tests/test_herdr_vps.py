import importlib.util
from importlib.machinery import SourceFileLoader
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
WATCHDOG = REPO / "bin" / "herdr-vps-watchdog"
WRAPPER = REPO / "bin" / "herdr-vps"
HERDR_SERVICE = REPO / "config" / "herdr-vps" / "herdr-dev.service"
WATCHDOG_SERVICE = REPO / "config" / "herdr-vps" / "herdr-vps-watchdog.service"
WATCHDOG_TIMER = REPO / "config" / "herdr-vps" / "herdr-vps-watchdog.timer"
PROVISIONER = REPO / "scripts" / "provision-herdr-vps.sh"
REMOTE_CONFIG = REPO / "config" / "herdr-vps" / "config.toml"
APPLY = REPO / "scripts" / "apply.sh"
PULL = REPO / "scripts" / "pull.sh"
GIB = 1024 ** 3
MIB = 1024 ** 2
WATCHDOG_LOADER = SourceFileLoader("herdr_vps_watchdog", str(WATCHDOG))
WATCHDOG_SPEC = importlib.util.spec_from_loader("herdr_vps_watchdog", WATCHDOG_LOADER)
watchdog = importlib.util.module_from_spec(WATCHDOG_SPEC)
WATCHDOG_LOADER.exec_module(watchdog)


class HerdrVpsProvisioningTests(unittest.TestCase):
    def write_command(self, directory, name, body):
        command = directory / name
        command.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
        command.chmod(0o755)

    def test_local_wrapper_attaches_to_dev_session_on_configured_vps(self):
        wrapper = WRAPPER.read_text(encoding="utf-8")

        self.assertIn("herdr --remote caspers_vps --session dev", wrapper)

    def test_user_service_runs_named_headless_server(self):
        service = HERDR_SERVICE.read_text(encoding="utf-8")

        self.assertIn(
            "ExecStart=/home/user/.local/bin/herdr --session dev server", service
        )

    def test_user_units_do_not_impose_hard_resource_caps(self):
        for unit_path in (HERDR_SERVICE, WATCHDOG_SERVICE, WATCHDOG_TIMER):
            with self.subTest(unit=unit_path.name):
                unit = unit_path.read_text(encoding="utf-8")
                self.assertNotRegex(unit, r"(?m)^\s*(MemoryMax|MemoryHigh|CPUQuota)\s*=")

    def test_provisioner_requires_release_digest_before_remote_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_bin = Path(directory)
            calls = fake_bin / "remote-calls"
            self.write_command(fake_bin, "herdr", "printf 'herdr 0.8.2\\n'\n")
            self.write_command(
                fake_bin,
                "gh",
                "printf 'https://github.com/herdrdev/herdr/releases/download/"
                "v0.8.2/herdr-linux-x86_64\\t\\n'\n",
            )
            for command in ("ssh", "scp"):
                self.write_command(
                    fake_bin,
                    command,
                    f"printf '{command}\\n' >> \"$CALL_LOG\"\nexit 99\n",
                )
            env = os.environ.copy()
            env.update(
                {
                    "PATH": str(fake_bin) + os.pathsep + env["PATH"],
                    "CALL_LOG": str(calls),
                }
            )

            result = subprocess.run(
                [str(PROVISIONER)],
                cwd=REPO,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(calls.exists(), result.stderr)

    def test_remote_config_is_accepted_by_installed_herdr(self):
        env = os.environ.copy()
        env["HERDR_CONFIG_PATH"] = str(REMOTE_CONFIG)

        result = subprocess.run(
            ["herdr", "config", "check"],
            cwd=REPO,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_provisioner_rejects_a_non_linux_x86_64_remote(self):
        provisioner = PROVISIONER.read_text(encoding="utf-8")

        self.assertIn('[[ "$(uname -s)" == "Linux" ]]', provisioner)
        self.assertIn('[[ "$(uname -m)" == "x86_64" ]]', provisioner)

    def test_repo_sync_manages_local_attach_wrapper(self):
        apply = APPLY.read_text(encoding="utf-8")
        pull = PULL.read_text(encoding="utf-8")

        self.assertIn(
            'install -m 755 "$REPO/bin/herdr-vps"        "$H/.local/bin/herdr-vps"',
            apply,
        )
        self.assertIn(
            'cp "$H/.local/bin/herdr-vps" "$REPO/bin/herdr-vps"', pull
        )

    def test_provisioner_uses_privilege_only_for_linger(self):
        provisioner = PROVISIONER.read_text(encoding="utf-8")
        privileged_commands = [
            line.strip()
            for line in provisioner.splitlines()
            if line.strip().startswith("/usr/bin/sudo")
        ]

        self.assertEqual(
            privileged_commands,
            [
                "/usr/bin/sudo -n -u admin /usr/bin/sudo -n "
                "/usr/bin/loginctl enable-linger user"
            ],
        )


class HerdrVpsWatchdogTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.proc = self.root / "proc"
        self.cgroup = self.root / "cgroup"
        self.state = self.root / "state"
        self.proc.mkdir()
        (self.cgroup / "user.slice" / "herdr-dev.service").mkdir(parents=True)
        self.set_memory_available(20 * GIB)

    def tearDown(self):
        self.tempdir.cleanup()

    def set_memory_available(self, bytes_available):
        (self.proc / "meminfo").write_text(
            f"MemAvailable: {bytes_available // 1024} kB\n", encoding="utf-8"
        )

    def add_process(self, pid, *, start_time, rss, command="agent", in_cgroup=True, cgroup_child=""):
        process = self.proc / str(pid)
        process.mkdir(exist_ok=True)
        # Field 22 is starttime.  The command deliberately contains a space to
        # exercise /proc/stat parsing rather than relying on split().
        stat_tail = ["S"] + ["0"] * 18 + [str(start_time)] + ["0"] * 4
        (process / "stat").write_text(
            f"{pid} ({command}) {' '.join(stat_tail)}\n", encoding="utf-8"
        )
        (process / "status").write_text(
            f"Name:\t{command}\nVmRSS:\t{rss // 1024} kB\n", encoding="utf-8"
        )
        if in_cgroup:
            service = self.cgroup / "user.slice" / "herdr-dev.service"
            (service / "cgroup.procs").touch(exist_ok=True)
            procs = service / cgroup_child / "cgroup.procs"
            procs.parent.mkdir(parents=True, exist_ok=True)
            current = procs.read_text(encoding="utf-8") if procs.exists() else ""
            pids = {line for line in current.splitlines() if line}
            pids.add(str(pid))
            procs.write_text("\n".join(sorted(pids)) + "\n", encoding="utf-8")

    def run_watchdog(self, *, main_pid=1):
        env = os.environ.copy()
        env.update(
            {
                "PROC_ROOT": str(self.proc),
                "CGROUP_ROOT": str(self.cgroup),
                "STATE_DIR": str(self.state),
                "CONTROL_GROUP": "/user.slice/herdr-dev.service",
                "MAIN_PID": str(main_pid),
                "HERDR_WATCHDOG_DRY_RUN": "1",
            }
        )
        return subprocess.run(
            [sys.executable, str(WATCHDOG), "--dry-run"],
            cwd=REPO,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def actions(self):
        action_file = self.state / "actions.jsonl"
        if not action_file.exists():
            return []
        return [json.loads(line) for line in action_file.read_text(encoding="utf-8").splitlines()]

    def live_terminate(self, *, metadata=None, opener=None, sender=None, sleeper=None, logger=None):
        self.add_process(101, start_time=1000, rss=7 * GIB)
        return watchdog.terminate(
            self.proc,
            {"pid": 101, "start_time": "1000", "rss": 7 * GIB, "command": "agent"},
            self.state,
            "sustained_growth",
            self.cgroup,
            "/user.slice/herdr-dev.service",
            metadata or (lambda: ("/user.slice/herdr-dev.service", 1)),
            pidfd_opener=opener,
            pidfd_sender=sender,
            pidfd_closer=lambda _pidfd: None,
            sleeper=sleeper or (lambda _seconds: None),
            action_logger=logger,
        )

    def test_healthy_process_exits_zero_without_action(self):
        self.add_process(101, start_time=1000, rss=512 * MIB)

        result = self.run_watchdog()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.actions(), [])

    def test_one_high_sample_does_not_trigger(self):
        self.add_process(101, start_time=1000, rss=7 * GIB)

        result = self.run_watchdog()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.actions(), [])

    def test_three_high_growing_samples_trigger_dry_run_action(self):
        # The workload can live in a descendant cgroup, not only the service
        # root cgroup.
        self.add_process(101, start_time=1000, rss=6 * GIB, cgroup_child="pane.scope")
        self.run_watchdog()
        self.add_process(101, start_time=1000, rss=6 * GIB + 300 * MIB, cgroup_child="pane.scope")
        self.run_watchdog()
        self.add_process(101, start_time=1000, rss=6 * GIB + 600 * MIB, cgroup_child="pane.scope")

        result = self.run_watchdog()

        self.assertEqual(result.returncode, 0, result.stderr)
        actions = self.actions()
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["action"], "would_terminate")
        self.assertEqual(actions[0]["pid"], 101)
        self.assertEqual(actions[0]["reason"], "sustained_growth")

    def test_process_outside_service_cgroup_is_never_a_candidate(self):
        for rss in (6 * GIB, 6 * GIB + 300 * MIB, 6 * GIB + 700 * MIB):
            self.add_process(999, start_time=1000, rss=rss, in_cgroup=False)
            # cgroup metadata exists but does not list the outside process.
            (self.cgroup / "user.slice" / "herdr-dev.service" / "cgroup.procs").touch(exist_ok=True)
            self.run_watchdog()

        self.assertEqual(self.actions(), [])

    def test_main_pid_is_protected_even_when_it_leaks(self):
        for rss in (6 * GIB, 6 * GIB + 300 * MIB, 6 * GIB + 700 * MIB):
            self.add_process(101, start_time=1000, rss=rss)
            self.run_watchdog(main_pid=101)

        self.assertEqual(self.actions(), [])

    def test_pid_reuse_resets_sample_history(self):
        self.add_process(101, start_time=1000, rss=6 * GIB)
        self.run_watchdog()
        self.add_process(101, start_time=2000, rss=7 * GIB)
        self.run_watchdog()
        self.add_process(101, start_time=2000, rss=7 * GIB + 300 * MIB)
        self.run_watchdog()
        self.assertEqual(self.actions(), [])

        self.add_process(101, start_time=2000, rss=7 * GIB + 700 * MIB)
        result = self.run_watchdog()

        self.assertEqual(result.returncode, 0, result.stderr)
        actions = self.actions()
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["start_time"], "2000")

    def test_pressure_fallback_requires_three_consecutive_pressure_samples(self):
        self.set_memory_available(3 * GIB)
        for rss in (2 * GIB, 2 * GIB + 150 * MIB, 2 * GIB + 300 * MIB):
            self.add_process(101, start_time=1000, rss=rss)
            # A second child takes aggregate service RSS over the pressure limit.
            self.add_process(102, start_time=1001, rss=11 * GIB)
            result = self.run_watchdog()

        self.assertEqual(result.returncode, 0, result.stderr)
        actions = self.actions()
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["pid"], 101)
        self.assertEqual(actions[0]["reason"], "memory_pressure")

    def test_incomplete_descendant_cgroup_metadata_fails_closed(self):
        self.add_process(101, start_time=1000, rss=7 * GIB)
        (self.cgroup / "user.slice" / "herdr-dev.service" / "incomplete.scope").mkdir()

        result = self.run_watchdog()

        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.actions(), [])

    def test_cgroup_walk_error_fails_closed(self):
        service = self.cgroup / "user.slice" / "herdr-dev.service"
        (service / "cgroup.procs").touch()

        with mock.patch.object(watchdog.os, "walk", side_effect=OSError("read failed")):
            with self.assertRaises(ValueError):
                watchdog.cgroup_pids(service)

    def test_live_signal_uses_pidfd_and_logs_intent_before_outcome(self):
        signals = []

        self.live_terminate(
            opener=lambda _pid: 42,
            sender=lambda _pidfd, sig: signals.append(sig),
        )

        self.assertEqual(signals, [watchdog.signal.SIGTERM, watchdog.signal.SIGKILL])
        actions = self.actions()
        self.assertEqual([action["action"] for action in actions], [
            "sigterm_intent", "sigterm_sent", "sigkill_intent", "sigkill_sent"
        ])

    def test_live_signal_stops_when_pid_identity_changes_after_pidfd_open(self):
        signals = []

        def reuse_pid(_pid):
            self.add_process(101, start_time=2000, rss=7 * GIB)
            return 42

        self.live_terminate(opener=reuse_pid, sender=lambda _pidfd, sig: signals.append(sig))

        self.assertEqual(signals, [])
        self.assertEqual(self.actions()[0]["action"], "identity_changed")

    def test_live_signal_stops_when_process_leaves_cgroup_before_signal(self):
        signals = []

        def remove_from_cgroup(_pid):
            (self.cgroup / "user.slice" / "herdr-dev.service" / "cgroup.procs").write_text("")
            return 42

        self.live_terminate(opener=remove_from_cgroup, sender=lambda _pidfd, sig: signals.append(sig))

        self.assertEqual(signals, [])
        self.assertEqual(self.actions()[0]["action"], "cgroup_membership_changed")

    def test_live_signal_stops_when_current_main_pid_changes_before_signal(self):
        signals = []
        metadata = lambda: ("/user.slice/herdr-dev.service", 101)

        self.live_terminate(metadata=metadata, opener=lambda _pid: 42,
                            sender=lambda _pidfd, sig: signals.append(sig))

        self.assertEqual(signals, [])
        self.assertEqual(self.actions()[0]["action"], "main_pid_changed")

    def test_live_signal_revalidates_pid_identity_before_sigkill(self):
        signals = []

        def reuse_pid_before_kill(_seconds):
            self.add_process(101, start_time=2000, rss=7 * GIB)

        self.live_terminate(opener=lambda _pid: 42,
                            sender=lambda _pidfd, sig: signals.append(sig),
                            sleeper=reuse_pid_before_kill)

        self.assertEqual(signals, [watchdog.signal.SIGTERM])
        self.assertEqual(self.actions()[-1]["action"], "identity_changed")

    def test_live_signal_revalidates_cgroup_membership_before_sigkill(self):
        signals = []

        def leave_cgroup_before_kill(_seconds):
            (self.cgroup / "user.slice" / "herdr-dev.service" / "cgroup.procs").write_text("")

        self.live_terminate(opener=lambda _pid: 42,
                            sender=lambda _pidfd, sig: signals.append(sig),
                            sleeper=leave_cgroup_before_kill)

        self.assertEqual(signals, [watchdog.signal.SIGTERM])
        self.assertEqual(self.actions()[-1]["action"], "cgroup_membership_changed")

    def test_live_signal_revalidates_main_pid_before_sigkill(self):
        signals = []
        main_pid = [1]

        def become_main_before_kill(_seconds):
            main_pid[0] = 101

        self.live_terminate(metadata=lambda: ("/user.slice/herdr-dev.service", main_pid[0]),
                            opener=lambda _pid: 42,
                            sender=lambda _pidfd, sig: signals.append(sig),
                            sleeper=become_main_before_kill)

        self.assertEqual(signals, [watchdog.signal.SIGTERM])
        self.assertEqual(self.actions()[-1]["action"], "main_pid_changed")

    def test_live_signal_fails_closed_without_pidfd_support(self):
        signals = []

        self.live_terminate(
            opener=lambda _pid: (_ for _ in ()).throw(ValueError("pidfd unavailable")),
            sender=lambda _pidfd, sig: signals.append(sig),
        )

        self.assertEqual(signals, [])
        self.assertEqual(self.actions()[0]["action"], "pidfd_unavailable")

    def test_live_signal_fails_closed_when_intent_logging_fails(self):
        signals = []

        with self.assertRaises(OSError):
            self.live_terminate(opener=lambda _pid: 42,
                                sender=lambda _pidfd, sig: signals.append(sig),
                                logger=lambda _state, _action: (_ for _ in ()).throw(OSError("disk full")))

        self.assertEqual(signals, [])

    def test_live_signal_aborts_when_membership_changes_during_sigterm_intent_log(self):
        signals = []

        def logger(state_dir, action):
            watchdog.append_action(state_dir, action)
            if action["action"] == "sigterm_intent":
                (self.cgroup / "user.slice" / "herdr-dev.service" / "cgroup.procs").write_text("")

        self.live_terminate(opener=lambda _pid: 42,
                            sender=lambda _pidfd, sig: signals.append(sig), logger=logger)

        self.assertEqual(signals, [])
        self.assertEqual([action["action"] for action in self.actions()], [
            "sigterm_intent", "sigterm_aborted"
        ])
        self.assertEqual(self.actions()[-1]["detail"], "cgroup_membership_changed")

    def test_live_signal_aborts_when_main_pid_changes_during_sigterm_intent_log(self):
        signals = []
        main_pid = [1]

        def logger(state_dir, action):
            watchdog.append_action(state_dir, action)
            if action["action"] == "sigterm_intent":
                main_pid[0] = 101

        self.live_terminate(metadata=lambda: ("/user.slice/herdr-dev.service", main_pid[0]),
                            opener=lambda _pid: 42,
                            sender=lambda _pidfd, sig: signals.append(sig), logger=logger)

        self.assertEqual(signals, [])
        self.assertEqual([action["action"] for action in self.actions()], [
            "sigterm_intent", "sigterm_aborted"
        ])
        self.assertEqual(self.actions()[-1]["detail"], "main_pid_changed")

    def test_live_signal_aborts_sigkill_when_membership_changes_during_kill_intent_log(self):
        signals = []

        def logger(state_dir, action):
            watchdog.append_action(state_dir, action)
            if action["action"] == "sigkill_intent":
                (self.cgroup / "user.slice" / "herdr-dev.service" / "cgroup.procs").write_text("")

        self.live_terminate(opener=lambda _pid: 42,
                            sender=lambda _pidfd, sig: signals.append(sig), logger=logger)

        self.assertEqual(signals, [watchdog.signal.SIGTERM])
        self.assertEqual(self.actions()[-1]["action"], "sigkill_aborted")
        self.assertEqual(self.actions()[-1]["detail"], "cgroup_membership_changed")


if __name__ == "__main__":
    unittest.main()
