"""mcp/remote/meta-ads/auth_headers.py: stdout carries only the header JSON; errors never reveal the token."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HELPER = REPO / "mcp" / "remote" / "meta-ads" / "auth_headers.py"
FAKE = "EA" + "Q7x" * 40  # built at runtime: shaped like a Meta token, not a real one


class MetaAdsAuthHeadersTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.home = self.root / "home"

    def tearDown(self):
        self._tmp.cleanup()

    def run_helper(self, *args):
        env = {k: v for k, v in os.environ.items() if k != "HOME"}
        env["HOME"] = str(self.home)
        return subprocess.run([sys.executable, str(HELPER), *args], capture_output=True, text=True, env=env, timeout=30)

    def token_file(self, content, mode=0o600, path=None):
        path = path or self.root / "token.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        path.chmod(mode)
        return path

    def assert_refused(self, result, message="missing or invalid"):
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn(message, result.stderr)
        self.assertNotIn(FAKE[:20], result.stderr)

    def test_valid_token_prints_only_the_header_json(self):
        result = self.run_helper(str(self.token_file(FAKE + "\n")))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"Authorization": "Bearer " + FAKE})
        self.assertEqual(result.stdout.count("\n"), 1)
        self.assertEqual(result.stderr, "")

    def test_default_path_is_under_the_credentials_directory(self):
        default = self.home / ".config/super-computer-ai/credentials/meta-ads/system-user-token.txt"
        self.assert_refused(self.run_helper())                       # missing default file
        self.token_file(FAKE, path=default)
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["Authorization"], "Bearer " + FAKE)

    def test_group_or_world_access_is_refused(self):
        for mode in (0o640, 0o604, 0o620, 0o644):
            self.assert_refused(self.run_helper(str(self.token_file(FAKE, mode=mode))), "readable only by its owner")

    def test_malformed_or_unusual_files_are_refused_without_echo(self):
        for content in ("", "EA" + "Q7x" * 10, "XX" + FAKE[2:], FAKE[:60] + " " + FAKE[60:], FAKE + "é", "\xff" + FAKE):
            self.assert_refused(self.run_helper(str(self.token_file(content))))
        self.assert_refused(self.run_helper(str(self.root)))          # a directory
        self.assert_refused(self.run_helper(str(self.root / "missing.txt")))


if __name__ == "__main__":
    unittest.main()
