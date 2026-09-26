"""mcp/servers/premiere-pro/scripts/install-macos.sh: --skip-client-config must not touch MCP client config."""
import json
import os
import platform
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SERVER = REPO / "mcp" / "servers" / "premiere-pro"
CLAUDE_CONFIG = Path("Library/Application Support/Claude/claude_desktop_config.json")


@unittest.skipUnless(platform.system() == "Darwin", "the setup script is macOS-only")
class PremiereSetupScriptTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.home = root / "home"
        self.pkg = root / "pkg"
        shutil.copytree(SERVER / "scripts", self.pkg / "scripts")
        shutil.copytree(SERVER / "cep-plugin", self.pkg / "cep-plugin")
        (self.pkg / "dist").mkdir()
        (self.pkg / "dist" / "index.js").write_text("// stub\n")
        bin_dir = root / "bin"
        bin_dir.mkdir()
        (bin_dir / "defaults").write_text("#!/bin/sh\nexit 0\n")  # never touch the real CEP debug prefs
        (bin_dir / "defaults").chmod(0o755)
        self.env = {**os.environ, "HOME": str(self.home), "PATH": f"{bin_dir}:{os.environ['PATH']}"}
        config = self.home / CLAUDE_CONFIG
        config.parent.mkdir(parents=True)
        self.original = json.dumps({"mcpServers": {"premiere-pro": {"command": "node", "args": ["/keep/me.js"]}}})
        config.write_text(self.original)

    def tearDown(self):
        self._tmp.cleanup()

    def run_script(self, *args):
        return subprocess.run(["bash", str(self.pkg / "scripts" / "install-macos.sh"), "--skip-build", *args],
                              env=self.env, text=True, capture_output=True, check=False)

    def test_skip_client_config_installs_cep_only(self):
        result = self.run_script("--skip-client-config")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("MCP client configuration was NOT changed", result.stdout)
        self.assertEqual(self.original, (self.home / CLAUDE_CONFIG).read_text())
        self.assertTrue((self.home / "Library/Application Support/Adobe/CEP/extensions/MCPBridgeCEP").is_dir())
        self.assertEqual(0o700, (self.home / ".premiere-mcp-bridge" / "bridge").stat().st_mode & 0o777)

    def test_default_still_rewrites_client_config(self):
        """Documents why the skill must not recommend the default: it rewrites the Claude Desktop entry."""
        result = self.run_script()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertNotEqual(self.original, (self.home / CLAUDE_CONFIG).read_text())

    def test_unknown_option_is_rejected(self):
        self.assertEqual(1, self.run_script("--nope").returncode)


if __name__ == "__main__":
    unittest.main()
