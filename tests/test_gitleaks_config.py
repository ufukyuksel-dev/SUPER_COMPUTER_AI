"""Checks the repository .gitleaks.toml against real gitleaks.

Skipped unless a gitleaks binary is available (GITLEAKS env var or PATH); the secret-scan CI job runs it.
Run: GITLEAKS=/path/to/gitleaks python3 -m unittest tests.test_gitleaks_config -v
"""
import os
import secrets
import shutil
import string
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GITLEAKS = os.environ.get("GITLEAKS") or shutil.which("gitleaks")


def random_github_token():
    alphabet = string.ascii_letters + string.digits
    return "ghp_" + "".join(secrets.choice(alphabet) for _ in range(36))


@unittest.skipUnless(GITLEAKS, "gitleaks binary not available")
class GitleaksConfigTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        shutil.copy(REPO / ".gitleaks.toml", self.root / ".gitleaks.toml")

    def tearDown(self):
        self._tmp.cleanup()

    def scan_staged(self):
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)
        return subprocess.run(
            [GITLEAKS, "git", "--pre-commit", "--staged", "--config", ".gitleaks.toml", "--redact",
             "--no-banner", "."],
            cwd=self.root, capture_output=True,
        ).returncode

    def test_clean_env_example_passes(self):
        (self.root / ".env.example").write_text("GITHUB_TOKEN=\nTYPESAFE_API_KEY=\n")
        self.assertEqual(self.scan_staged(), 0)

    def test_real_looking_credential_in_env_example_is_caught(self):
        sub = self.root / "mcp" / "servers" / "x"
        sub.mkdir(parents=True)
        (sub / ".env.example").write_text("GITHUB_TOKEN=" + random_github_token() + "\n")
        self.assertEqual(self.scan_staged(), 1)


if __name__ == "__main__":
    unittest.main()
