import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PROVISIONER = REPO / "scripts" / "provision-herdr-vps-clis.sh"
SYNC = REPO / "scripts" / "sync-herdr-vps-harness.sh"
REMOTE_PROFILE = REPO / "config" / "herdr-vps" / "remote-profile.sh"


class HerdrVpsCliProvisioningTests(unittest.TestCase):
    maxDiff = None

    def write_command(self, directory, name, body):
        command = directory / name
        command.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + body, encoding="utf-8")
        command.chmod(0o755)
        return command

    def patched_provisioner(self, root):
        script = PROVISIONER.read_text(encoding="utf-8")
        original = 'expected_home="/home/user"'
        replacement = f'expected_home="{root / "home"}"'
        self.assertEqual(script.count(original), 1)
        patched = root / "provision-herdr-vps-clis.sh"
        patched.write_text(script.replace(original, replacement), encoding="utf-8")
        patched.chmod(0o755)
        return patched

    def test_manifest_resolves_exact_reproducible_runtime_inputs(self):
        result = subprocess.run(
            ["bash", str(PROVISIONER), "--manifest"],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "claude|2.1.237|npm|@anthropic-ai/claude-code@2.1.237|sha512-abVRJmxRjeoti4i5luV56PZ2T73gJOO7Y1puy/SsXpF5sid0PXbqBkbX4jQMLtdy2Ho4MftJ71v1vCXYrhb9Ww==",
                "codex|0.148.0|npm|@openai/codex@0.148.0|sha512-bh5kH9+BMrFaHGmLeoSansPdfRksvr4UXzjQInns/KRO7r8VJ+6AAW+SqUsE8XcG3+OW/mI4EEy8Gpo9UDXGvQ==",
                "pi|0.84.2|npm|@earendil-works/pi-coding-agent@0.84.2|sha512-l4E+B7hgXKWddRo8bC/eSue2aWZjEgJ9xIpf5p0Og+lq8a2TArCwJ0HCoCPCgaBP/tN4zbYH/wOwvx9pJpeLCA==",
                "omp|17.3.0|native|https://github.com/can1357/oh-my-pi/releases/download/v17.3.0/omp-linux-x64|sha256:287f07366f29896ef1e345423dab79b82a8dc0c1593383e20dfdd62a9dd2e799",
                "dcode|0.1.56|wheel|https://files.pythonhosted.org/packages/93/6c/a8b9b424fd8acbd24fe83df1a60733fc3ee9bf7b699146854fbce77788c3/deepagents_code-0.1.56-py3-none-any.whl|sha256:635979453e26fc78e838d639a83f50de29d72d418ace6746c82bccded8bd8936",
                "opencode|1.17.13|native|https://github.com/anomalyco/opencode/releases/download/v1.17.13/opencode-linux-x64.tar.gz|sha256:157afa289d1a8d9372de0ce19ac726119b937a1f6b201808d46f06e4e59bb348",
                "hermes|0.20.4|git|https://github.com/NousResearch/hermes-agent.git|commit:e624e9fde561e1add9388384012b295fde669ade",
                "grok|1.0.5|unavailable|https://x.ai/cli/grok-1.0.5-linux-x86_64|no-official-sha256",
                "cursor-agent|2026.08.11-e8db854|unavailable|https://downloads.cursor.com/lab/2026.08.11-e8db854/linux/x64/agent-cli-package.tar.gz|no-official-sha256",
                "glm|sync-only|wrapper|~/.local/bin/glm|portable-zai-auth",
            ],
        )

    def test_remote_check_rejects_a_mismatched_active_cli_before_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            fake_bin = root / "bin"
            home.mkdir()
            fake_bin.mkdir()
            operations = root / "operations"
            remote_profile = root / "remote-profile.sh"
            remote_profile.write_text("# profile\n", encoding="utf-8")
            provisioner = self.patched_provisioner(root)

            self.write_command(
                fake_bin,
                "id",
                "[[ \"${1:-}\" == '-un' ]] && printf 'user\\n' || exit 2\n",
            )
            self.write_command(
                fake_bin,
                "uname",
                "case \"${1:-}\" in -s) printf 'Linux\\n' ;; -m) printf 'x86_64\\n' ;; *) exit 2 ;; esac\n",
            )
            self.write_command(fake_bin, "claude", "printf 'Claude Code 9.9.9\\n'\n")
            for command in ("curl", "npm", "install", "git", "python3"):
                self.write_command(
                    fake_bin,
                    command,
                    f"printf '{command} %s\\n' \"$*\" >> \"$OPERATION_LOG\"\nexit 91\n",
                )

            env = os.environ.copy()
            env.update(
                {
                    "HOME": str(home),
                    "PATH": str(fake_bin) + os.pathsep + "/usr/bin:/bin",
                    "OPERATION_LOG": str(operations),
                }
            )
            result = subprocess.run(
                ["bash", str(provisioner), "--remote", str(remote_profile), "--check"],
                cwd=REPO,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            attempted = operations.read_text(encoding="utf-8") if operations.exists() else ""
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("replacement required", result.stderr)
            self.assertIn("claude", result.stderr)
            self.assertEqual(attempted, "")
            self.assertFalse((home / ".config" / "herdr" / "remote-profile.sh").exists())

    def test_native_digest_failure_never_installs_the_download(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            fake_bin = root / "bin"
            home.mkdir()
            fake_bin.mkdir()
            operations = root / "operations"
            remote_profile = root / "remote-profile.sh"
            remote_profile.write_text("# profile\n", encoding="utf-8")
            provisioner = self.patched_provisioner(root)

            self.write_command(
                fake_bin,
                "id",
                "[[ \"${1:-}\" == '-un' ]] && printf 'user\\n' || exit 2\n",
            )
            self.write_command(
                fake_bin,
                "uname",
                "case \"${1:-}\" in -s) printf 'Linux\\n' ;; -m) printf 'x86_64\\n' ;; *) exit 2 ;; esac\n",
            )
            self.write_command(
                fake_bin,
                "curl",
                "output=''\n"
                "while [[ $# -gt 0 ]]; do\n"
                "  if [[ \"$1\" == '--output' ]]; then output=\"$2\"; shift 2; else shift; fi\n"
                "done\n"
                "printf 'tampered artifact\\n' > \"$output\"\n",
            )
            self.write_command(fake_bin, "sha256sum", "cat >/dev/null\nexit 1\n")
            self.write_command(
                fake_bin,
                "install",
                "printf 'install %s\\n' \"$*\" >> \"$OPERATION_LOG\"\nexit 90\n",
            )

            env = os.environ.copy()
            env.update(
                {
                    "HOME": str(home),
                    "PATH": str(fake_bin) + os.pathsep + "/usr/bin:/bin",
                    "OPERATION_LOG": str(operations),
                }
            )
            result = subprocess.run(
                ["bash", str(provisioner), "--remote", str(remote_profile)],
                cwd=REPO,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            attempted = operations.read_text(encoding="utf-8") if operations.exists() else ""
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SHA-256 verification failed", result.stderr)
            self.assertNotIn("omp", attempted)
            self.assertFalse((home / ".local" / "bin" / "omp").exists())

    def test_remote_profile_adds_user_local_paths_once(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            home.mkdir()
            env = os.environ.copy()
            env.update({"HOME": str(home), "PATH": "/usr/bin:/bin"})
            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    '. "$1"; . "$1"; printf "%s\\n" "$PATH"',
                    "bash",
                    str(REMOTE_PROFILE),
                ],
                cwd=REPO,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            entries = result.stdout.strip().split(":")
            self.assertEqual(entries.count(str(home / ".local" / "bin")), 1)
            self.assertEqual(entries.count(str(home / ".grok" / "bin")), 1)
            self.assertEqual(entries.count(str(home / ".hermes" / "bin")), 1)


class HerdrVpsHarnessSyncTests(unittest.TestCase):
    def write_command(self, directory, name, body):
        command = directory / name
        command.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + body, encoding="utf-8")
        command.chmod(0o755)
        return command

    def make_local_harness(self, root, include_auth=True):
        local_home = root / "local-home"
        memory_store = root / "memory-store"
        claude_skill = root / "plugin-cache" / "claude-skill"
        codex_skill = root / "plugin-cache" / "codex-skill"
        memory_store.mkdir(parents=True)
        claude_skill.mkdir(parents=True)
        codex_skill.mkdir(parents=True)
        (memory_store / "MEMORY.md").write_text("durable memory\n", encoding="utf-8")
        (memory_store / ".env").write_text("MEMORY_SECRET=forbidden\n", encoding="utf-8")
        (claude_skill / "SKILL.md").write_text("claude skill\n", encoding="utf-8")
        (claude_skill / ".env").write_text("SKILL_SECRET=forbidden\n", encoding="utf-8")
        (claude_skill / "session.db").write_text("history\n", encoding="utf-8")
        (codex_skill / "SKILL.md").write_text("codex skill\n", encoding="utf-8")

        (local_home / ".claude" / "skills").mkdir(parents=True)
        (local_home / ".codex" / "skills").mkdir(parents=True)
        (local_home / ".claude" / "skills" / "linked-claude").symlink_to(
            claude_skill, target_is_directory=True
        )
        (local_home / ".codex" / "skills" / "linked-codex").symlink_to(
            codex_skill, target_is_directory=True
        )
        (local_home / ".ai-memory").symlink_to(memory_store, target_is_directory=True)

        (local_home / ".local" / "bin").mkdir(parents=True)
        glm = local_home / ".local" / "bin" / "glm"
        glm.write_text("#!/usr/bin/env bash\nprintf 'glm\\n'\n", encoding="utf-8")
        glm.chmod(0o755)
        (local_home / ".claude" / "bin").mkdir(parents=True)
        mac_dcode_launcher = local_home / ".claude" / "bin" / "dcode-launcher"
        mac_dcode_launcher.write_text(
            "#!/bin/zsh\n"
            "emulate -L zsh\n"
            "launcher=\"${0:A}\"\n"
            "command_name=\"${0:t}\"\n"
            "[[ \"$command_name\" == 'dcode-launcher' ]] && command_name='dcode'\n"
            "real=\"$HOME/.local/share/uv/tools/deepagents-code/bin/$command_name\"\n"
            "unset OPENAI_API_KEY OPENAI_BASE_URL\n"
            "# MCP guard adds --no-mcp when a bad symlink is present.\n"
            "# Socket-stdin guard checks /dev/fd/0 before exec.\n"
            "exec \"$real\" \"$@\"\n",
            encoding="utf-8",
        )
        mac_dcode_launcher.chmod(0o755)

        if include_auth:
            (local_home / ".codex").mkdir(exist_ok=True)
            (local_home / ".codex" / "auth.json").write_text(
                '{"token":"SUPERSECRET-CODEX"}\n', encoding="utf-8"
            )
            (local_home / ".codex" / "auth.json").chmod(0o600)
            (local_home / ".config" / "zai").mkdir(parents=True)
            (local_home / ".config" / "zai" / "token").write_text(
                "SUPERSECRET-ZAI\n", encoding="utf-8"
            )
            (local_home / ".config" / "zai" / "token").chmod(0o600)
        return local_home

    def make_transport(self, root, remote_home):
        fake_bin = root / "transport-bin"
        remote_bin = root / "remote-bin"
        fake_bin.mkdir()
        remote_bin.mkdir()
        self.write_command(
            remote_bin,
            "id",
            "[[ \"${1:-}\" == '-un' ]] && printf 'user\\n' || exit 2\n",
        )
        self.write_command(
            remote_bin,
            "uname",
            "case \"${1:-}\" in -s) printf 'Linux\\n' ;; -m) printf 'x86_64\\n' ;; *) exit 2 ;; esac\n",
        )
        self.write_command(
            fake_bin,
            "ssh",
            "incoming=\"$(mktemp)\"\n"
            "patched=\"${incoming}.patched\"\n"
            "/bin/cat > \"$incoming\"\n"
            "/usr/bin/sed \"s|expected_home=\\\"/home/user\\\"|expected_home=\\\"$FAKE_REMOTE_HOME\\\"|\" \"$incoming\" > \"$patched\"\n"
            "HOME=\"$FAKE_REMOTE_HOME\" PATH=\"$FAKE_REMOTE_BIN:/usr/bin:/bin\" /bin/bash \"$patched\"\n",
        )
        self.write_command(
            fake_bin,
            "rsync",
            "args=(\"$@\")\n"
            "last=$(( ${#args[@]} - 1 ))\n"
            "destination=\"${args[$last]}\"\n"
            "prefix='caspers_vps:/home/user'\n"
            "[[ \"$destination\" == \"$prefix\"* ]] || exit 81\n"
            "args[$last]=\"$FAKE_REMOTE_HOME${destination#$prefix}\"\n"
            "PATH=/usr/bin:/bin /usr/bin/rsync \"${args[@]}\"\n",
        )
        return fake_bin, remote_bin

    def run_sync(
        self,
        root,
        include_auth=True,
        regular_memory_link=False,
        permissive_auth=False,
        mac_binary=False,
    ):
        local_home = self.make_local_harness(root, include_auth=include_auth)
        if permissive_auth:
            (local_home / ".codex" / "auth.json").chmod(0o644)
        if mac_binary:
            binary = local_home / ".claude" / "skills" / "macos-tool"
            binary.write_bytes(
                b"\xcf\xfa\xed\xfe\x0c\x00\x00\x01\x03\x00\x00\x80\x02\x00\x00\x00"
            )
            binary.chmod(0o755)
        remote_home = root / "remote-home"
        remote_home.mkdir()
        preserved = remote_home / ".claude" / "skills" / "get-cred.md"
        preserved.parent.mkdir(parents=True)
        preserved.write_text("remote-only\n", encoding="utf-8")
        remote_bin_dir = remote_home / ".local" / "bin"
        dcode_runtime_bin = (
            remote_home
            / ".local"
            / "share"
            / "herdr-clis"
            / "dcode-0.1.56"
            / "bin"
        )
        remote_bin_dir.mkdir(parents=True)
        dcode_runtime_bin.mkdir(parents=True)
        for command_name in ("dcode", "deepagents-code"):
            executable = dcode_runtime_bin / command_name
            executable.write_text(
                "#!/usr/bin/env bash\nprintf 'deepagents-code 0.1.56\\n'\n",
                encoding="utf-8",
            )
            executable.chmod(0o755)
        (remote_bin_dir / "dcode").symlink_to(dcode_runtime_bin / "dcode")
        if regular_memory_link:
            memory_link = remote_home / ".claude" / "CLAUDE.md"
            memory_link.parent.mkdir(parents=True, exist_ok=True)
            memory_link.write_text("do not replace\n", encoding="utf-8")
        fake_bin, remote_bin = self.make_transport(root, remote_home)

        env = os.environ.copy()
        env.update(
            {
                "HOME": str(local_home),
                "PATH": str(fake_bin) + os.pathsep + "/usr/bin:/bin",
                "FAKE_REMOTE_HOME": str(remote_home),
                "FAKE_REMOTE_BIN": str(remote_bin),
            }
        )
        result = subprocess.run(
            ["bash", str(SYNC)],
            cwd=REPO,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        return result, local_home, remote_home

    def test_sync_preserves_remote_files_and_copies_only_curated_portable_state(self):
        with tempfile.TemporaryDirectory() as directory:
            result, _, remote_home = self.run_sync(Path(directory))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                (remote_home / ".claude" / "skills" / "get-cred.md").read_text(
                    encoding="utf-8"
                ),
                "remote-only\n",
            )
            self.assertEqual(
                (remote_home / ".claude" / "skills" / "linked-claude" / "SKILL.md").read_text(
                    encoding="utf-8"
                ),
                "claude skill\n",
            )
            self.assertFalse(
                (remote_home / ".claude" / "skills" / "linked-claude").is_symlink()
            )
            self.assertEqual(
                (remote_home / ".codex" / "skills" / "linked-codex" / "SKILL.md").read_text(
                    encoding="utf-8"
                ),
                "codex skill\n",
            )
            self.assertTrue((remote_home / ".codex" / "skills").is_dir())
            self.assertFalse((remote_home / ".codex" / "skills").is_symlink())
            self.assertFalse(
                (remote_home / ".claude" / "skills" / "linked-claude" / ".env").exists()
            )
            self.assertFalse(
                (remote_home / ".claude" / "skills" / "linked-claude" / "session.db").exists()
            )
            self.assertFalse((remote_home / ".ai-memory" / ".env").exists())
            self.assertEqual(
                (remote_home / ".codex" / "auth.json").stat().st_mode & 0o777, 0o600
            )
            self.assertEqual(
                (remote_home / ".config" / "zai" / "token").stat().st_mode & 0o777,
                0o600,
            )
            self.assertNotIn("SUPERSECRET", result.stdout + result.stderr)

            dcode = subprocess.run(
                [str(remote_home / ".local" / "bin" / "dcode"), "--version"],
                env={"HOME": str(remote_home), "PATH": "/usr/bin:/bin"},
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(dcode.returncode, 0, dcode.stderr)
            self.assertIn("0.1.56", dcode.stdout)
            launcher = remote_home / ".claude" / "bin" / "dcode-launcher"
            self.assertTrue(launcher.is_file())
            launcher_text = launcher.read_text(encoding="utf-8")
            self.assertIn(
                'real="$HOME/.local/share/herdr-clis/dcode-0.1.56/bin/$command_name"',
                launcher_text,
            )
            self.assertIn("unset OPENAI_API_KEY OPENAI_BASE_URL", launcher_text)
            self.assertIn("--no-mcp", launcher_text)
            self.assertIn("/dev/fd/0", launcher_text)
            self.assertNotIn("share/uv/tools/deepagents-code", launcher_text)
            self.assertEqual((remote_home / ".local" / "bin" / "dcode").resolve(), launcher.resolve())
            self.assertEqual(
                (remote_home / ".local" / "bin" / "deepagents-code").resolve(),
                launcher.resolve(),
            )

            for filename in ("ladders.json", "models.json"):
                self.assertEqual(
                    (remote_home / ".claude" / "omnicode" / filename).read_bytes(),
                    (REPO / "config" / filename).read_bytes(),
                )
            for agent in (REPO / "agents").glob("*.md"):
                self.assertEqual(
                    (remote_home / ".claude" / "agents" / agent.name).read_bytes(),
                    agent.read_bytes(),
                )
            self.assertEqual(
                (remote_home / ".claude" / "workflows" / "race-and-judge.mjs").read_bytes(),
                (REPO / "workflows" / "race-and-judge.mjs").read_bytes(),
            )
            for wrapper in ("lanes", "lane-pick", "goal", "omnicode-doctor"):
                installed = remote_home / ".local" / "bin" / wrapper
                self.assertEqual(installed.read_bytes(), (REPO / "bin" / wrapper).read_bytes())
                self.assertNotEqual(installed.stat().st_mode & 0o111, 0)

            memory_target = remote_home / ".ai-memory" / "MEMORY.md"
            for relative in (
                ".claude/CLAUDE.md",
                ".codex/AGENTS.md",
                ".cursor/AGENTS.md",
                ".grok/AGENTS.md",
                ".agents/AGENTS.md",
            ):
                link = remote_home / relative
                self.assertTrue(link.is_symlink(), relative)
                self.assertEqual(link.resolve(), memory_target.resolve())

            skills_target = remote_home / ".claude" / "skills"
            for relative in (".agents/skills", ".cursor/skills", ".grok/skills"):
                link = remote_home / relative
                self.assertTrue(link.is_symlink(), relative)
                self.assertEqual(link.resolve(), skills_target.resolve())

    def test_missing_optional_auth_is_reported_without_blocking_public_sync(self):
        with tempfile.TemporaryDirectory() as directory:
            result, _, remote_home = self.run_sync(
                Path(directory), include_auth=False
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("INCOMPLETE codex auth: local portable auth not found", result.stdout)
            self.assertIn("INCOMPLETE zai auth: local portable auth not found", result.stdout)
            self.assertTrue((remote_home / ".ai-memory" / "MEMORY.md").is_file())

    def test_sync_refuses_to_replace_an_unrelated_required_link_path(self):
        with tempfile.TemporaryDirectory() as directory:
            result, _, remote_home = self.run_sync(
                Path(directory), regular_memory_link=True
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing to replace unrelated path", result.stderr)
            self.assertEqual(
                (remote_home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8"),
                "do not replace\n",
            )

    def test_sync_rejects_permissive_auth_before_transferring_any_state(self):
        with tempfile.TemporaryDirectory() as directory:
            result, _, remote_home = self.run_sync(
                Path(directory), permissive_auth=True
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("portable auth source must be mode 0600", result.stderr)
            self.assertFalse((remote_home / ".ai-memory").exists())

    def test_sync_rejects_a_mac_binary_before_transferring_any_state(self):
        with tempfile.TemporaryDirectory() as directory:
            result, _, remote_home = self.run_sync(Path(directory), mac_binary=True)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Mac binary in portable tree", result.stderr)
            self.assertFalse((remote_home / ".ai-memory").exists())


if __name__ == "__main__":
    unittest.main()
