"""herdr-open-url normalization checks (no network, no tunnel)."""
import os
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "herdr-open-url"


def run(arg: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "HERDR_OPEN_URL_DRYRUN": "1"}
    return subprocess.run(
        ["bash", str(SCRIPT), arg], capture_output=True, text=True, env=env
    )


class TestNormalization(unittest.TestCase):
    def test_full_https_unchanged(self):
        self.assertEqual(run("https://casperschive.no").stdout.strip(), "https://casperschive.no")

    def test_bare_domain_gets_https(self):
        self.assertEqual(run("casperschive.no").stdout.strip(), "https://casperschive.no")

    def test_bare_domain_with_path(self):
        self.assertEqual(run("example.com/a?b=c").stdout.strip(), "https://example.com/a?b=c")

    def test_bare_host_with_port(self):
        self.assertEqual(run("staging.casperschive.no:8443/x").stdout.strip(), "https://staging.casperschive.no:8443/x")

    def test_localhost_gets_http(self):
        self.assertEqual(run("localhost:3000").stdout.strip(), "http://localhost:3000")

    def test_ipv6_gets_http(self):
        self.assertEqual(run("[::1]:5173").stdout.strip(), "http://[::1]:5173")

    def test_refuses_garbage(self):
        self.assertNotEqual(run("not a url").returncode, 0)

    def test_refuses_empty_and_multiline(self):
        self.assertNotEqual(run("casperschive.no/ x").returncode, 0)


if __name__ == "__main__":
    unittest.main()
