"""scripts/scai_mcp.client_processes: the --mcp precondition must see every Claude Code / Codex writer.

Regression: `ps -o comm=` truncates the executable when more columns follow ("/Applications/Cl"), so the detection
matched nothing. It now parses full command lines from `ps -axww -o pid=,args=`."""
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import scai_mcp  # noqa: E402

# shapes observed on a real machine (home directory replaced)
CLIENTS = """\
44055 /srv/u/Projects/app/node_modules/@anthropic-ai/claude-agent-sdk-darwin-arm64/claude --output-format stream-json
18556 /Applications/Claude.app/Contents/MacOS/Claude
18561 /Applications/Claude.app/Contents/Frameworks/Claude Helper.app/Contents/MacOS/Claude Helper --type=gpu-process
20001 /opt/homebrew/lib/node_modules/@openai/codex/node_modules/@openai/codex-darwin-arm64/vendor/aarch64-apple-darwin/bin/codex
20002 /Applications/ChatGPT.app/Contents/Frameworks/Codex Framework.framework/Codex --type=renderer
20003 node /usr/local/lib/node_modules/@anthropic-ai/claude-code/cli.js
20004 /srv/u/.local/bin/claude
20005 /Applications/Codex.app/Contents/MacOS/Codex
"""
OTHERS = """\
1 /sbin/launchd
301 /bin/zsh -l
302 /opt/homebrew/bin/node /srv/u/Projects/PremiereProMCP/dist/index.js
303 /usr/bin/python3 scripts/install.py --mcp
304 vim notes-about-claude.md
305 /Applications/ChatGPT.app/Contents/MacOS/ChatGPT
"""


class ClientDetectionTest(unittest.TestCase):
    def test_every_client_shape_is_detected(self):
        found = scai_mcp.client_processes(CLIENTS)
        self.assertEqual(len(CLIENTS.splitlines()), len(found), found)
        for pid in ("44055", "18556", "20001", "20002", "20003", "20004", "20005"):
            self.assertTrue(any(f"(pid {pid})" in item for item in found), pid)

    def test_unrelated_processes_are_not_clients(self):
        self.assertEqual([], scai_mcp.client_processes(OTHERS))

    def test_live_process_list_is_parsed_with_full_command_lines(self):
        import inspect
        source = inspect.getsource(scai_mcp.running_clients)
        self.assertIn('"-axww"', source)
        self.assertIn("pid=,args=", source)
        self.assertNotIn("comm=", source)


if __name__ == "__main__":
    unittest.main()


class FailClosedTest(unittest.TestCase):
    """If the process list cannot be trusted, the check must block writing (never report "no clients")."""

    class Result:
        def __init__(self, returncode, stdout, stderr=""):
            self.returncode, self.stdout, self.stderr = returncode, stdout, stderr

    def check(self, result=None, raises=None):
        def fake_run(*args, **kwargs):
            if raises:
                raise raises
            return result
        return scai_mcp.running_clients(run=fake_run)

    def test_untrustworthy_process_lists_block(self):
        import os
        import subprocess
        me = f"{os.getpid()} /usr/bin/python3 scripts/install.py --mcp\n"
        cases = {
            "non-zero exit": self.Result(1, me, "ps: secret-looking --token=abc"),
            "empty output": self.Result(0, ""),
            "whitespace only": self.Result(0, "  \n"),
            "malformed line": self.Result(0, me + "garbage without pid\n"),
            "own process missing": self.Result(0, "1 /sbin/launchd\n"),
            "stdout not text": self.Result(0, None),
        }
        for label, result in cases.items():
            with self.subTest(label):
                found = self.check(result)
                self.assertEqual([scai_mcp.UNVERIFIABLE], found)
                self.assertNotIn("secret-looking", " ".join(found))
        for exc in (OSError("no ps"), subprocess.TimeoutExpired("ps", 10)):
            with self.subTest(type(exc).__name__):
                self.assertEqual([scai_mcp.UNVERIFIABLE], self.check(raises=exc))

    def test_complete_list_without_clients_passes_and_with_clients_blocks(self):
        import os
        me = f"{os.getpid()} /usr/bin/python3 scripts/install.py --mcp\n1 /sbin/launchd\n"
        self.assertEqual([], self.check(self.Result(0, me)))
        found = self.check(self.Result(0, me + "77 /srv/u/.local/bin/claude\n"))
        self.assertEqual(["claude (pid 77)"], found)

    def test_the_installer_blocks_when_the_check_fails(self):
        """End to end: a PATH whose `ps` fails makes install.py --mcp refuse (exit 4) and write nothing."""
        import json
        import os
        import shutil
        import subprocess
        import tempfile
        repo = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(os.path.realpath(tmp))
            fake = tmp / "bin"
            fake.mkdir()
            (fake / "ps").write_text("#!/bin/sh\necho 'ps: failed --token=abc' >&2\nexit 1\n")
            (fake / "ps").chmod(0o755)
            home = tmp / "home"
            home.mkdir()
            (home / ".claude.json").write_text(json.dumps({"mcpServers": {}}, indent=2))
            env = {k: v for k, v in os.environ.items() if not k.startswith(("SCAI_", "CLAUDE_CONFIG", "CODEX_HOME"))}
            env["PATH"] = f"{fake}:{env['PATH']}"
            before = (home / ".claude.json").read_bytes()
            result = subprocess.run([sys.executable, str(repo / "scripts" / "install.py"), "--home", str(home),
                                     "--bundle", "video-editing", "--mcp"], capture_output=True, text=True, env=env)
            self.assertEqual(4, result.returncode, result.stdout + result.stderr)
            self.assertIn("could not be verified", result.stdout)
            self.assertNotIn("--token=abc", result.stdout + result.stderr)
            self.assertEqual(before, (home / ".claude.json").read_bytes())
            self.assertFalse((home / ".local/state/super-computer-ai/journals").exists()
                             and any((home / ".local/state/super-computer-ai/journals").iterdir()))
            shutil.rmtree(fake)
