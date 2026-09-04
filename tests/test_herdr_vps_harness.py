import os
import socket
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
            self.write_command(fake_bin, "npm", "exit 99\n")
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

    def test_later_artifact_failure_leaves_no_earlier_harness_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            fake_bin = root / "bin"
            home.mkdir()
            fake_bin.mkdir()
            digest_calls = root / "digest-calls"
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
                "url=''\n"
                "while [[ $# -gt 0 ]]; do\n"
                "  case \"$1\" in\n"
                "    --output) output=\"$2\"; shift 2 ;;\n"
                "    http*) url=\"$1\"; shift ;;\n"
                "    *) shift ;;\n"
                "  esac\n"
                "done\n"
                "if [[ \"$url\" == *omp-linux-x64 ]]; then\n"
                "  printf '%s\\n' '#!/usr/bin/env bash' \"printf 'omp 17.3.0\\\\n'\" > \"$output\"\n"
                "else\n"
                "  printf 'tampered later artifact\\n' > \"$output\"\n"
                "fi\n",
            )
            self.write_command(
                fake_bin,
                "sha256sum",
                "count=0\n"
                "[[ -f \"$DIGEST_CALLS\" ]] && count=\"$(<\"$DIGEST_CALLS\")\"\n"
                "count=$((count + 1))\n"
                "printf '%s\\n' \"$count\" > \"$DIGEST_CALLS\"\n"
                "cat >/dev/null\n"
                "[[ \"$count\" == '1' ]]\n",
            )
            self.write_command(fake_bin, "npm", "exit 99\n")

            env = os.environ.copy()
            env.update(
                {
                    "HOME": str(home),
                    "PATH": str(fake_bin) + os.pathsep + "/usr/bin:/bin",
                    "DIGEST_CALLS": str(digest_calls),
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

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SHA-256 verification failed", result.stderr)
            self.assertFalse((home / ".local" / "bin" / "omp").exists())

    def test_grok_probe_does_not_confuse_an_unrelated_agent_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            fake_bin = root / "bin"
            home.mkdir()
            fake_bin.mkdir()
            generic_agent_called = root / "generic-agent-called"
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
            self.write_command(fake_bin, "grok", "printf 'grok 1.0.5\\n'\n")
            self.write_command(
                fake_bin,
                "agent",
                "touch \"$GENERIC_AGENT_CALLED\"\nprintf 'different-agent 99.0\\n'\n",
            )

            env = os.environ.copy()
            env.update(
                {
                    "HOME": str(home),
                    "PATH": str(fake_bin) + os.pathsep + "/usr/bin:/bin",
                    "GENERIC_AGENT_CALLED": str(generic_agent_called),
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

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("READY grok 1.0.5", result.stdout)
            self.assertFalse(generic_agent_called.exists())

    def test_late_hermes_destination_conflict_is_caught_before_downloads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            fake_bin = root / "bin"
            home.mkdir()
            fake_bin.mkdir()
            unmanaged_uv = home / ".local" / "share" / "herdr-clis" / "uv-0.10.9"
            unmanaged_uv.mkdir(parents=True)
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
                "printf 'curl\\n' >> \"$OPERATION_LOG\"\nexit 88\n",
            )
            self.write_command(fake_bin, "sha256sum", "cat >/dev/null\nexit 0\n")
            self.write_command(fake_bin, "npm", "exit 99\n")

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
            self.assertIn("unmanaged directory", result.stderr)
            self.assertEqual(attempted, "")

    def test_foreign_owned_remote_home_stops_before_any_provision_mutation(self):
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
                "case \"${1:-}\" in\n"
                "  -un) printf 'user\\n' ;;\n"
                f"  -u) printf '{os.getuid() + 10000}\\n' ;;\n"
                "  *) exit 2 ;;\n"
                "esac\n",
            )
            self.write_command(
                fake_bin,
                "uname",
                "case \"${1:-}\" in -s) printf 'Linux\\n' ;; -m) printf 'x86_64\\n' ;; *) exit 2 ;; esac\n",
            )
            self.write_command(fake_bin, "zsh", "exit 0\n")
            for command in ("chmod", "curl", "install", "mkdir", "npm"):
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
                    "HERDR_TEST_ZSH_PATH": str(fake_bin / "zsh"),
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
            self.assertIn("owner", result.stderr)
            self.assertEqual(attempted, "")
            self.assertFalse((home / ".cache").exists())

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

    def make_local_harness(
        self,
        root,
        include_auth=True,
        external_skill_link=False,
        symlink_skill_root=False,
        external_cache_link=False,
        mac_binary=False,
        mac_wrapper=False,
        broken_dcode_alias=False,
        broken_glm=False,
    ):
        local_home = root / "local-home"
        memory_store = (
            local_home / ".claude" / "projects" / "fixture-project" / "memory"
        )
        claude_skill = local_home / ".claude" / "skill-sources" / "claude-skill"
        codex_skill = local_home / ".codex" / "skills" / "source-codex"
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
        (local_home / ".codex" / "skills").mkdir(parents=True, exist_ok=True)
        (local_home / ".claude" / "skills" / "linked-claude").symlink_to(
            claude_skill, target_is_directory=True
        )
        (local_home / ".codex" / "skills" / "linked-codex").symlink_to(
            codex_skill, target_is_directory=True
        )
        (local_home / ".ai-memory").symlink_to(memory_store, target_is_directory=True)
        if symlink_skill_root:
            escaped_root = root / "escaped-skill-root"
            escaped_root.mkdir()
            (escaped_root / "SKILL.md").write_text(
                "escaped root\n", encoding="utf-8"
            )
            (local_home / ".claude" / "skills").rename(
                root / "displaced-skill-root"
            )
            (local_home / ".claude" / "skills").symlink_to(
                escaped_root, target_is_directory=True
            )
        if external_skill_link:
            external_secret = root / "external-secret-tree"
            external_secret.mkdir()
            (external_secret / "token.txt").write_text(
                "SHOULD-NEVER-TRANSFER\n", encoding="utf-8"
            )
            (local_home / ".claude" / "skills" / "external-secret").symlink_to(
                external_secret, target_is_directory=True
            )
        if external_cache_link:
            external_cache = root / "external-cache-tree"
            external_cache.mkdir()
            (external_cache / "token.txt").write_text(
                "SHOULD-NEVER-TRANSFER\n", encoding="utf-8"
            )
            (local_home / ".claude" / "skills" / "cache").symlink_to(
                external_cache, target_is_directory=True
            )
        if mac_binary:
            binary = local_home / ".claude" / "skills" / "opaque-data"
            binary.write_bytes(
                b"\xcf\xfa\xed\xfe\x0c\x00\x00\x01\x03\x00\x00\x80\x02\x00\x00\x00"
            )
            binary.chmod(0o644)

        (local_home / ".local" / "bin").mkdir(parents=True)
        glm = local_home / ".local" / "bin" / "glm"
        if mac_wrapper:
            glm.write_bytes(
                b"\xcf\xfa\xed\xfe\x0c\x00\x00\x01\x03\x00\x00\x80\x02\x00\x00\x00"
            )
        elif broken_glm:
            glm.write_text("#!/bin/zsh\nexit 74\n", encoding="utf-8")
        else:
            glm.write_text(
                "#!/bin/zsh\nexec claude \"$@\"\n", encoding="utf-8"
            )
        glm.chmod(0o755)
        (local_home / ".claude" / "bin").mkdir(parents=True)
        mac_dcode_launcher = local_home / ".claude" / "bin" / "dcode-launcher"
        mac_dcode_launcher.write_text(
            "#!/bin/zsh\n"
            "emulate -L zsh\n"
            "command_name=\"${DCODE_COMMAND_NAME:-${0:t}}\"\n"
            "[[ \"$command_name\" == 'dcode-launcher' ]] && command_name='dcode'\n"
            "unset DCODE_COMMAND_NAME\n"
            "case \"$command_name\" in dcode|deepagents-code) ;; *) exit 64 ;; esac\n"
            + (
                "[[ \"$command_name\" == 'deepagents-code' ]] && exit 65\n"
                if broken_dcode_alias
                else ""
            )
            +
            "real=\"$HOME/.local/share/uv/tools/deepagents-code/bin/$command_name\"\n"
            "unset OPENAI_API_KEY OPENAI_BASE_URL\n"
            "original_args=(\"$@\")\n"
            "cleaned_args=()\n"
            "has_no_mcp=0\n"
            "has_explicit_stdin=0\n"
            "arg_index=1\n"
            "while (( arg_index <= ${#original_args} )); do\n"
            "  arg=\"${original_args[arg_index]}\"\n"
            "  case \"$arg\" in\n"
            "    --no-mcp) has_no_mcp=1; cleaned_args+=(\"$arg\"); (( arg_index += 1 )) ;;\n"
            "    --stdin) has_explicit_stdin=1; cleaned_args+=(\"$arg\"); (( arg_index += 1 )) ;;\n"
            "    --mcp-config)\n"
            "      if (( arg_index + 1 <= ${#original_args} )) && "
            "[[ \"${original_args[arg_index + 1]}\" == \"$HOME/.deepagents/dcode-mcp.json\" ]]; then\n"
            "        (( arg_index += 2 ))\n"
            "      else\n"
            "        cleaned_args+=(\"$arg\"); (( arg_index += 1 ))\n"
            "      fi ;;\n"
            "    *) cleaned_args+=(\"$arg\"); (( arg_index += 1 )) ;;\n"
            "  esac\n"
            "done\n"
            "set -- \"${cleaned_args[@]}\"\n"
            "if [[ -S /dev/fd/0 ]] && (( ! has_explicit_stdin )); then exec </dev/null; fi\n"
            "if [[ -L \"$HOME/.deepagents/.mcp.json\" ]] && (( ! has_no_mcp )); then\n"
            "  exec \"$real\" --no-mcp \"$@\"\n"
            "fi\n"
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

    def make_transport(
        self,
        root,
        remote_home,
        failing_find=False,
        failing_file=False,
        have_zsh=True,
        remote_uid=None,
    ):
        fake_bin = root / "transport-bin"
        remote_bin = root / "remote-bin"
        transport_log = root / "transport.log"
        fake_bin.mkdir()
        remote_bin.mkdir()
        self.write_command(
            remote_bin,
            "id",
            "case \"${1:-}\" in\n"
            "  -un) printf 'user\\n' ;;\n"
            f"  -u) printf '{os.getuid() if remote_uid is None else remote_uid}\\n' ;;\n"
            "  *) exit 2 ;;\n"
            "esac\n",
        )
        self.write_command(
            remote_bin,
            "uname",
            "case \"${1:-}\" in -s) printf 'Linux\\n' ;; -m) printf 'x86_64\\n' ;; *) exit 2 ;; esac\n",
        )
        if have_zsh:
            self.write_command(
                remote_bin,
                "zsh",
                "exec /bin/zsh \"$@\"\n",
            )
        self.write_command(
            fake_bin,
            "ssh",
            "printf 'ssh\\n' >> \"$TRANSPORT_LOG\"\n"
            "incoming=\"$(mktemp)\"\n"
            "patched=\"${incoming}.patched\"\n"
            "/bin/cat > \"$incoming\"\n"
            "/usr/bin/sed "
            "-e \"s|expected_home=\\\"/home/user\\\"|expected_home=\\\"$FAKE_REMOTE_HOME\\\"|\" "
            "-e \"s|/usr/bin/zsh|$FAKE_REMOTE_ZSH|g\" "
            "-e \"s|/bin/zsh|$FAKE_REMOTE_ZSH|g\" "
            "\"$incoming\" > \"$patched\"\n"
            "script_args=()\n"
            "seen_separator=0\n"
            "for arg in \"$@\"; do\n"
            "  if [[ \"$seen_separator\" == '1' ]]; then\n"
            "    [[ \"$arg\" == /home/user/* ]] && arg=\"$FAKE_REMOTE_HOME${arg#/home/user}\"\n"
            "    script_args+=(\"$arg\")\n"
            "  fi\n"
            "  [[ \"$arg\" == '--' ]] && seen_separator=1\n"
            "done\n"
            "set +e\n"
            "if (( ${#script_args[@]} )); then\n"
            "  remote_output=\"$(HOME=\"$FAKE_REMOTE_HOME\" PATH=\"$FAKE_REMOTE_BIN:/usr/bin:/bin\" "
            "HERDR_TEST_ZSH_PATH=\"$FAKE_REMOTE_ZSH\" /bin/bash \"$patched\" \"${script_args[@]}\")\"\n"
            "else\n"
            "  remote_output=\"$(HOME=\"$FAKE_REMOTE_HOME\" PATH=\"$FAKE_REMOTE_BIN:/usr/bin:/bin\" "
            "HERDR_TEST_ZSH_PATH=\"$FAKE_REMOTE_ZSH\" /bin/bash \"$patched\")\"\n"
            "fi\n"
            "remote_status=$?\n"
            "set -e\n"
            "if [[ -n \"$remote_output\" ]]; then\n"
            "  printf '%s\\n' \"$remote_output\" | /usr/bin/sed \"s|$FAKE_REMOTE_HOME|/home/user|g\"\n"
            "fi\n"
            "exit \"$remote_status\"\n",
        )
        self.write_command(
            fake_bin,
            "rsync",
            "auth_mode=missing\n"
            "if [[ -e \"$FAKE_REMOTE_HOME/.codex/auth.json\" ]]; then\n"
            "  auth_mode=\"$(/usr/bin/stat -f '%Lp' \"$FAKE_REMOTE_HOME/.codex/auth.json\" 2>/dev/null || /usr/bin/stat -c '%a' \"$FAKE_REMOTE_HOME/.codex/auth.json\")\"\n"
            "fi\n"
            "args=(\"$@\")\n"
            "last=$(( ${#args[@]} - 1 ))\n"
            "destination=\"${args[$last]}\"\n"
            "printf 'rsync|%s|auth=%s\\n' \"$destination\" \"$auth_mode\" >> \"$TRANSPORT_LOG\"\n"
            "prefix='caspers_vps:/home/user'\n"
            "if [[ \"$destination\" == \"$prefix\"* ]]; then\n"
            "  args[$last]=\"$FAKE_REMOTE_HOME${destination#$prefix}\"\n"
            "elif [[ \"$destination\" == \"caspers_vps:$FAKE_REMOTE_HOME\"* ]]; then\n"
            "  args[$last]=\"${destination#caspers_vps:}\"\n"
            "else\n"
            "  exit 81\n"
            "fi\n"
            "PATH=/usr/bin:/bin /usr/bin/rsync \"${args[@]}\"\n",
        )
        if failing_find:
            self.write_command(fake_bin, "find", "exit 73\n")
        if failing_file:
            self.write_command(fake_bin, "file", "exit 74\n")
        return fake_bin, remote_bin

    def run_sync(
        self,
        root,
        include_auth=True,
        regular_memory_link=False,
        permissive_auth=False,
        mac_binary=False,
        mac_wrapper=False,
        external_skill_link=False,
        symlink_skill_root=False,
        external_cache_link=False,
        failing_find=False,
        failing_file=False,
        remote_memory_escape=False,
        remote_auth_parent_escape=False,
        remote_auth_symlink=False,
        remote_existing_auth_mode=None,
        have_zsh=True,
        broken_dcode_alias=False,
        broken_glm=False,
        remote_uid=None,
    ):
        local_home = self.make_local_harness(
            root,
            include_auth=include_auth,
            external_skill_link=external_skill_link,
            symlink_skill_root=symlink_skill_root,
            external_cache_link=external_cache_link,
            mac_binary=mac_binary,
            mac_wrapper=mac_wrapper,
            broken_dcode_alias=broken_dcode_alias,
            broken_glm=broken_glm,
        )
        if permissive_auth:
            (local_home / ".codex" / "auth.json").chmod(0o644)
        remote_home = root / "remote-home"
        remote_home.mkdir()
        outside = root / "outside-remote"
        if remote_memory_escape or remote_auth_parent_escape or remote_auth_symlink:
            outside.mkdir()
        if remote_memory_escape:
            (remote_home / ".ai-memory").symlink_to(outside, target_is_directory=True)
        if remote_auth_parent_escape:
            (remote_home / ".codex").symlink_to(outside, target_is_directory=True)
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
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "if [[ \"${1:-}\" == '--version' ]]; then printf 'deepagents-code 0.1.56\\n'; exit 0; fi\n"
                "{\n"
                "  printf 'command=%s\\n' \"$(basename \"$0\")\"\n"
                "  printf 'openai=%s\\n' \"${OPENAI_API_KEY-unset}\"\n"
                "  printf 'base=%s\\n' \"${OPENAI_BASE_URL-unset}\"\n"
                "  printf 'stdin=%s\\n' \"$([[ -S /dev/fd/0 ]] && printf socket || printf safe)\"\n"
                "  printf 'args='\n"
                "  printf '<%s>' \"$@\"\n"
                "  printf '\\n'\n"
                "} >> \"$DCODE_CAPTURE\"\n",
                encoding="utf-8",
            )
            executable.chmod(0o755)
        (remote_bin_dir / "dcode").symlink_to(dcode_runtime_bin / "dcode")
        claude = remote_bin_dir / "claude"
        claude.write_text(
            "#!/usr/bin/env bash\nprintf 'Claude Code 2.1.237\\n'\n",
            encoding="utf-8",
        )
        claude.chmod(0o755)
        if regular_memory_link:
            memory_link = remote_home / ".claude" / "CLAUDE.md"
            memory_link.parent.mkdir(parents=True, exist_ok=True)
            memory_link.write_text("do not replace\n", encoding="utf-8")
        if remote_existing_auth_mode is not None and not remote_auth_parent_escape:
            auth = remote_home / ".codex" / "auth.json"
            auth.parent.mkdir(parents=True, exist_ok=True)
            auth.write_text('{"token":"OLD"}\n', encoding="utf-8")
            auth.chmod(remote_existing_auth_mode)
        if remote_auth_symlink:
            auth = remote_home / ".codex" / "auth.json"
            auth.parent.mkdir(parents=True, exist_ok=True)
            outside_auth = outside / "auth.json"
            outside_auth.write_text("OUTSIDE-UNCHANGED\n", encoding="utf-8")
            auth.symlink_to(outside_auth)
        fake_bin, remote_bin = self.make_transport(
            root,
            remote_home,
            failing_find=failing_find,
            failing_file=failing_file,
            have_zsh=have_zsh,
            remote_uid=remote_uid,
        )

        env = os.environ.copy()
        env.update(
            {
                "HOME": str(local_home),
                "PATH": str(fake_bin) + os.pathsep + "/usr/bin:/bin",
                "FAKE_REMOTE_HOME": str(remote_home),
                "FAKE_REMOTE_BIN": str(remote_bin),
                "FAKE_REMOTE_ZSH": str(remote_bin / "zsh"),
                "TRANSPORT_LOG": str(root / "transport.log"),
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
            for wrapper in (
                "lanes",
                "lane-pick",
                "goal",
                "omnicode-doctor",
                "apply-race-artifact",
            ):
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
            root = Path(directory)
            result, _, remote_home = self.run_sync(root, regular_memory_link=True)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing to replace unrelated path", result.stderr)
            transfer_log = root / "transport.log"
            operations = transfer_log.read_text(encoding="utf-8")
            self.assertNotIn("rsync|", operations)
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

    def test_unapproved_local_symlink_is_rejected_before_any_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result, _, remote_home = self.run_sync(
                root, external_skill_link=True
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unapproved symlink target", result.stderr)
            self.assertFalse((root / "transport.log").exists())
            self.assertFalse((remote_home / ".ai-memory").exists())

    def test_symlinked_allowlist_root_is_rejected_before_any_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result, _, remote_home = self.run_sync(
                root, symlink_skill_root=True
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("allowlisted root", result.stderr)
            self.assertFalse((root / "transport.log").exists())
            self.assertFalse((remote_home / ".ai-memory").exists())

    def test_external_cache_symlink_is_inspected_before_any_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result, _, remote_home = self.run_sync(
                root, external_cache_link=True
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unapproved symlink target", result.stderr)
            self.assertFalse((root / "transport.log").exists())
            self.assertFalse((remote_home / ".ai-memory").exists())

    def test_local_find_failure_is_rejected_before_any_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result, _, remote_home = self.run_sync(root, failing_find=True)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("failed to enumerate portable tree", result.stderr)
            self.assertFalse((root / "transport.log").exists())
            self.assertFalse((remote_home / ".ai-memory").exists())

    def test_local_file_failure_is_rejected_before_any_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result, _, remote_home = self.run_sync(root, failing_file=True)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("cannot identify portable file", result.stderr)
            self.assertFalse((root / "transport.log").exists())
            self.assertFalse((remote_home / ".ai-memory").exists())

    def test_individual_wrapper_is_scanned_for_mach_o_before_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result, _, remote_home = self.run_sync(root, mac_wrapper=True)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Mac binary in portable file", result.stderr)
            self.assertFalse((root / "transport.log").exists())
            self.assertFalse((remote_home / ".ai-memory").exists())

    def test_remote_memory_escape_is_rejected_before_mkdir_or_transfer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result, _, _ = self.run_sync(root, remote_memory_escape=True)

            self.assertNotEqual(result.returncode, 0)
            operations = (root / "transport.log").read_text(encoding="utf-8")
            self.assertNotIn("rsync|", operations)
            self.assertEqual(list((root / "outside-remote").iterdir()), [])

    def test_remote_auth_parent_escape_is_rejected_before_transfer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result, _, _ = self.run_sync(root, remote_auth_parent_escape=True)

            self.assertNotEqual(result.returncode, 0)
            operations = (root / "transport.log").read_text(encoding="utf-8")
            self.assertNotIn("rsync|", operations)
            self.assertEqual(list((root / "outside-remote").iterdir()), [])

    def test_remote_auth_symlink_is_rejected_without_touching_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result, _, _ = self.run_sync(root, remote_auth_symlink=True)

            self.assertNotEqual(result.returncode, 0)
            operations = (root / "transport.log").read_text(encoding="utf-8")
            self.assertNotIn("rsync|", operations)
            self.assertEqual(
                (root / "outside-remote" / "auth.json").read_text(encoding="utf-8"),
                "OUTSIDE-UNCHANGED\n",
            )

    def test_existing_auth_is_hardened_before_first_transfer_and_stays_private(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result, _, remote_home = self.run_sync(
                root, remote_existing_auth_mode=0o644
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            operations = (root / "transport.log").read_text(encoding="utf-8")
            first_transfer = next(
                line for line in operations.splitlines() if line.startswith("rsync|")
            )
            self.assertIn("auth=600", first_transfer)
            self.assertEqual(
                (remote_home / ".codex" / "auth.json").stat().st_mode & 0o777,
                0o600,
            )

    def test_missing_remote_zsh_stops_before_transfer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result, _, remote_home = self.run_sync(root, have_zsh=False)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("zsh", result.stderr)
            operations = (root / "transport.log").read_text(encoding="utf-8")
            self.assertNotIn("rsync|", operations)
            self.assertFalse((remote_home / ".ai-memory").exists())

    def test_foreign_owned_remote_home_stops_before_sync_mutation_or_transfer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result, _, remote_home = self.run_sync(
                root,
                remote_existing_auth_mode=0o644,
                remote_uid=os.getuid() + 10000,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("owner", result.stderr)
            operations = (root / "transport.log").read_text(encoding="utf-8")
            self.assertNotIn("rsync|", operations)
            self.assertEqual(
                (remote_home / ".codex" / "auth.json").stat().st_mode & 0o777,
                0o644,
            )
            self.assertFalse(any((remote_home / ".cache").glob("herdr-auth-stage.*")))

    def test_broken_bridge_alias_leaves_both_public_commands_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            result, _, remote_home = self.run_sync(
                Path(directory), broken_dcode_alias=True
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("INCOMPLETE dcode bridge", result.stdout)
            launcher = remote_home / ".claude" / "bin" / "dcode-launcher"
            self.assertEqual(
                (remote_home / ".local" / "bin" / "dcode").resolve(),
                launcher.resolve(),
            )
            self.assertEqual(
                (remote_home / ".local" / "bin" / "deepagents-code").resolve(),
                launcher.resolve(),
            )
            capture = Path(directory) / "broken-bridge-capture"
            env = os.environ.copy()
            env.update(
                {
                    "HOME": str(remote_home),
                    "PATH": "/usr/bin:/bin",
                    "DCODE_CAPTURE": str(capture),
                }
            )
            for command_name in ("dcode", "deepagents-code"):
                invocation = subprocess.run(
                    [str(remote_home / ".local" / "bin" / command_name), "run"],
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertNotEqual(invocation.returncode, 0, command_name)
            self.assertFalse(capture.exists())

    def test_glm_wrapper_must_functionally_report_the_pinned_claude_version(self):
        with tempfile.TemporaryDirectory() as directory:
            result, _, _ = self.run_sync(Path(directory), broken_glm=True)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("glm wrapper", result.stderr)

    def test_dcode_bridge_preserves_all_guards_for_both_aliases(self):
        with tempfile.TemporaryDirectory() as directory:
            result, _, remote_home = self.run_sync(Path(directory))
            self.assertEqual(result.returncode, 0, result.stderr)

            deepagents = remote_home / ".deepagents"
            mcp_target = deepagents / "mcp-real.json"
            mcp_target.write_text("{}\n", encoding="utf-8")
            (deepagents / ".mcp.json").symlink_to(mcp_target)
            capture = Path(directory) / "dcode-capture"
            env = os.environ.copy()
            env.update(
                {
                    "HOME": str(remote_home),
                    "PATH": "/usr/bin:/bin",
                    "DCODE_CAPTURE": str(capture),
                    "OPENAI_API_KEY": "forbidden-key",
                    "OPENAI_BASE_URL": "https://forbidden.example",
                }
            )

            left, right = socket.socketpair()
            try:
                first = subprocess.run(
                    [
                        str(remote_home / ".local" / "bin" / "dcode"),
                        "run",
                        "--mcp-config",
                        str(deepagents / "dcode-mcp.json"),
                        "keep-me",
                    ],
                    env=env,
                    stdin=left,
                    text=True,
                    capture_output=True,
                    check=False,
                )
            finally:
                left.close()
                right.close()
            second = subprocess.run(
                [str(remote_home / ".local" / "bin" / "deepagents-code"), "help"],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            captured = capture.read_text(encoding="utf-8")
            self.assertIn("command=dcode", captured)
            self.assertIn("command=deepagents-code", captured)
            self.assertEqual(captured.count("openai=unset"), 2)
            self.assertEqual(captured.count("base=unset"), 2)
            self.assertIn("stdin=safe", captured)
            self.assertIn("<--no-mcp>", captured)
            self.assertNotIn("dcode-mcp.json", captured)
            self.assertIn("<keep-me>", captured)


if __name__ == "__main__":
    unittest.main()
