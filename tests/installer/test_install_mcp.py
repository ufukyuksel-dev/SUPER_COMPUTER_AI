"""Acceptance tests for scripts/install.py --mcp (plan phase 2F: §3a, §3b, §4, §5a; plan v7 §8.3 h, j, k).

Every test uses a fixture repository (install.py + scai_mcp.py + run_mcp.py + a small registry) and an isolated HOME
whose ~/.claude.json and ~/.codex/config.toml contain foreign entries, comments and a fake token. Fault injection:
SCAI_TEST_MODE=1 + SCAI_FAULT=<step>:<point>; a concurrent writer: SCAI_TEST_TOUCH=<step>; running clients:
SCAI_TEST_CLIENT_PROCS; no swap syscall: SCAI_TEST_NO_SWAP=1.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
FAKE = "EA" + "Zq9" * 30   # shaped like a Meta token, built at runtime
STUB_SERVER = """import json, os, sys
with open(os.environ["STUB_OUT"], "w") as f:
    json.dump({"argv": sys.argv[1:], "env": {k: v for k, v in os.environ.items() if k.startswith(("STUB_", "ACCT_", "OLD_"))}}, f)
"""


def write(path: Path, text: str, mode: int = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if mode is not None:
        path.chmod(mode)
    return path


def build_repo(root: Path) -> Path:
    repo = root / "repo"
    (repo / "scripts").mkdir(parents=True)
    for name in ("install.py", "scai_mcp.py", "run_mcp.py"):
        shutil.copy(SCRIPTS / name, repo / "scripts" / name)
    skills = {"alpha-skill": {"category": "cat-a", "status": "active", "profile": "basic",
                              "platforms": ["claude", "codex"], "bundles": ["one"]},
              "beta-skill": {"category": "cat-a", "status": "active", "profile": "basic",
                             "platforms": ["claude"], "bundles": ["two"]}}
    write(repo / "skills" / "manifest.json", json.dumps({"schema_version": 2, "skills": skills}))
    for name in skills:
        write(repo / "skills" / "cat-a" / name / "SKILL.md", f"---\nname: {name}\ndescription: x\n---\n")
    write(repo / "agents" / "manifest.json", json.dumps({"schema_version": 1, "roles": {}}))
    write(repo / "instructions" / "global" / "10-home.md", "## Home rule\n")
    write(repo / "scripts" / "migration" / "source_map.json", json.dumps({"schema_version": 1, "sources": {
        "AI_Developer": {"skills": {"from": "x/{name}", "names": []}, "roles": {"claude": {"from": "x"},
                                                                              "codex": {"from": "x"}, "names": []}},
        "AI_SKILLS": {"skills": {"names": {}}}, "manual-copies": {"skills": {}}}}))
    registry = {"schema_version": 1, "servers": {
        "stub": {"kind": "local", "transport": "stdio", "path": "mcp/servers/stub", "runtime": "python",
                 "launch": {"command": "python3", "args": ["{path}/server.py", "--who", "{client}"]},
                 "env": {"STUB_MODE": {"required": False}, "STUB_CONFIG": {"required": False, "kind": "path"},
                         "STUB_KEY": {"required": False, "secret": True}},
                 "variants": {"stub-alt": {"args": ["{path}/server.py", "--alt", "{client}"]}},
                 "skills": [], "bundles": ["one"]},
        "acct": {"kind": "local", "transport": "stdio", "path": "mcp/servers/acct", "runtime": "python",
                 "launch": {"command": "python3", "args": ["{path}/server.py"]},
                 "env": {"ACCT_CONFIG": {"required": True, "kind": "path"}, "ACCT_AUDIT": {"required": False, "kind": "path"},
                         "ACCT_TOKEN": {"required": False, "secret": True}},
                 "legacy_env": {"ACCT_CONFIG": "OLD_ACCT_CONFIG"}, "skills": [], "bundles": ["one"]},
        "helped": {"kind": "remote", "transport": "http", "url": "https://example.invalid/mcp",
                   "auth": {"method": "headers_helper", "helper": "mcp/remote/helped/auth.py",
                            "argument": {"default": "~/.config/super-computer-ai/credentials/helped/token.txt"}},
                   "skills": [], "bundles": ["two"]},
        "oauthy": {"kind": "remote", "transport": "http", "url": "https://example.invalid/oauth",
                   "auth": {"method": "oauth"}, "skills": [], "bundles": ["one"]}},
        "external": []}
    write(repo / "mcp" / "registry.json", json.dumps(registry, indent=2))
    write(repo / "mcp" / "servers" / "stub" / "server.py", STUB_SERVER)
    write(repo / "mcp" / "servers" / "acct" / "server.py", STUB_SERVER)
    write(repo / "mcp" / "remote" / "helped" / "auth.py", "print('{}')\n", mode=0o755)
    return repo


def claude_doc(home: Path) -> dict:
    return {
        "numStartups": 3,
        "mcpServers": {"ai-orchestration": {"type": "http", "url": "http://127.0.0.1:1/mcp"},
                       "MCP_DOCKER": {"command": "docker", "args": ["mcp"], "env": {"TOKEN_X": FAKE}}},
        "projects": {str(home / "proj"): {"allowedTools": [], "mcpServers": {"UnityMCP": {"command": "u"}}}},
        "zLast": "ü",
    }


CODEX = f'''model = "gpt-x"  # preamble comment

# AI orchestration (foreign)
[mcp_servers."ai-orchestration"]
url = "http://127.0.0.1:1/mcp"

[mcp_servers."ai-orchestration".tools."memory.write"]
approval = "never"

[mcp_servers.elevenlabs]
command = "x"
# foreign comment

[mcp_servers.elevenlabs.env]
ELEVEN_API_KEY = "{FAKE}"

[projects."/x"]
trust_level = "trusted"
'''


class McpBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(os.path.realpath(self._tmp.name))   # the installer resolves /var -> /private/var
        self.repo = build_repo(self.root)
        self.home = self.make_home(self.root / "home")

    def tearDown(self):
        self._tmp.cleanup()

    def make_home(self, home: Path, codex: bool = True, claude: bool = True) -> Path:
        home.mkdir(parents=True)
        (home / "proj").mkdir()
        if claude:
            write(home / ".claude.json", json.dumps(claude_doc(home), indent=2, ensure_ascii=False), mode=0o600)
        if codex:
            write(home / ".codex" / "config.toml", CODEX, mode=0o600)
        write(home / ".config" / "super-computer-ai" / "credentials" / "helped" / "token.txt", "t\n", mode=0o600)
        return home

    # ---- helpers
    def run_install(self, *args, home=None, check=None, env=None):
        environment = {k: v for k, v in os.environ.items() if not k.startswith(("SCAI_", "CLAUDE_CONFIG", "CODEX_HOME"))}
        environment.update({"SCAI_TEST_MODE": "1", "SCAI_TEST_CLIENT_PROCS": ""})
        environment.update(env or {})
        result = subprocess.run([sys.executable, str(self.repo / "scripts" / "install.py"), "--home",
                                 str(home or self.home), *args], capture_output=True, text=True, env=environment)
        if check is not None:
            self.assertEqual(check, result.returncode, result.stdout + result.stderr)
        return result

    def files(self, home=None) -> dict:
        home = home or self.home
        out = {}
        for rel in (".claude.json", ".codex/config.toml"):
            path = home / rel
            out[rel] = path.read_bytes() if path.exists() else None
        return out

    def claude(self, home=None) -> dict:
        return json.loads((home or self.home).joinpath(".claude.json").read_text(encoding="utf-8"))

    def codex(self, home=None) -> str:
        return (home or self.home).joinpath(".codex", "config.toml").read_text(encoding="utf-8")

    def journals(self, home=None):
        return sorted((home or self.home).joinpath(".local/state/super-computer-ai/journals").glob("journal-*.json"))

    def last_journal(self, home=None) -> Path:
        return self.journals(home)[-1]

    def overlay(self, instances: dict, home=None) -> Path:
        home = home or self.home
        return write(home / ".config/super-computer-ai/private/mcp/instances.json",
                     json.dumps({"schema_version": 1, "instances": instances}))

    def entry_steps(self, journal: Path) -> list:
        return [s for s in json.loads(journal.read_text())["steps"] if s.get("entry")]

    def _probe_steps(self, home: Path) -> list:
        probe = self.root / f"probe-{home.name}"
        shutil.copytree(home, probe, symlinks=True)
        self.run_install("--mcp", home=probe, check=0)
        steps = self.entry_steps(self.last_journal(probe))
        shutil.rmtree(probe)
        return steps

    def leftovers(self, home=None) -> list:
        home = home or self.home
        return sorted(p.name for d in (home, home / ".codex") if d.is_dir() for p in d.iterdir()
                      if ".scai-swap-" in p.name)


class InstallTest(McpBase):
    def test_first_install_adds_entries_and_keeps_every_foreign_byte(self):
        before = self.files()
        self.run_install("--mcp", check=0)
        doc = self.claude()
        original = claude_doc(self.home)
        self.assertEqual(list(doc["mcpServers"])[:2], ["ai-orchestration", "MCP_DOCKER"])
        self.assertEqual(sorted(doc["mcpServers"]), sorted(["ai-orchestration", "MCP_DOCKER", "stub", "stub-alt", "oauthy", "helped"]))
        for key in ("ai-orchestration", "MCP_DOCKER"):
            self.assertEqual(doc["mcpServers"][key], original["mcpServers"][key])
        self.assertEqual(doc["projects"], original["projects"])
        self.assertEqual([k for k in doc if k != "mcpServers"], [k for k in original if k != "mcpServers"])
        stub = doc["mcpServers"]["stub"]
        self.assertEqual(stub["args"][1:], ["--spec", str(self.home / ".local/state/super-computer-ai/mcp/instances.json"),
                                            "stub", "--client", "claude"])
        self.assertNotIn("acct", doc["mcpServers"])     # needs account config: no default instance
        codex = self.codex()
        self.assertTrue(codex.startswith(CODEX), "foreign TOML (incl. comments) must stay byte-identical")
        self.assertIn('[mcp_servers.stub]\ncommand = "', codex)
        self.assertIn("[mcp_servers.helped]", codex)    # first install selects every bundle
        # uninstall returns both files to their exact original bytes
        self.run_install("--uninstall", check=0)
        self.assertEqual(before, self.files())

    def test_second_run_is_a_no_op_and_check_is_clean(self):
        self.run_install("--mcp", check=0)
        before, journals = self.files(), self.journals()
        result = self.run_install(check=0)
        self.assertIn("already up to date", result.stdout)
        self.assertEqual(before, self.files())
        self.assertEqual(journals, self.journals())
        self.run_install("--check", check=0)

    def test_rollback_restores_bit_identical_files_and_spec(self):
        before = self.files()
        self.run_install("--mcp", check=0)
        self.assertTrue((self.home / ".local/state/super-computer-ai/mcp/instances.json").is_file())
        self.run_install("--rollback", self.last_journal().name, check=0)
        self.assertEqual(before, self.files())
        self.assertFalse((self.home / ".local/state/super-computer-ai/mcp/instances.json").exists())

    def test_spec_is_private_and_holds_only_resolved_values(self):
        self.run_install("--mcp", check=0)
        spec_path = self.home / ".local/state/super-computer-ai/mcp/instances.json"
        self.assertEqual(0o600, spec_path.stat().st_mode & 0o777)
        self.assertEqual(0o700, spec_path.parent.stat().st_mode & 0o777)
        spec = json.loads(spec_path.read_text())["instances"]
        self.assertEqual(sorted(spec), ["stub", "stub-alt"])
        self.assertTrue(os.path.isabs(spec["stub"]["command"]))
        self.assertEqual(spec["stub"]["args"], [str(self.repo / "mcp/servers/stub/server.py"), "--who", "{client}"])
        self.assertEqual(spec["stub"]["credentials_env_file"],
                         str(self.home / ".config/super-computer-ai/credentials/stub/.env"))

    def test_no_mcp_removes_only_owned_entries(self):
        before = self.files()
        self.run_install("--mcp", check=0)
        self.run_install("--no-mcp", check=0)
        self.assertEqual(before, self.files())
        self.assertFalse((self.home / ".local/state/super-computer-ai/mcp/instances.json").exists())

    def test_deselected_bundle_removes_its_servers(self):
        self.run_install("--mcp", check=0)
        self.assertIn("helped", self.claude()["mcpServers"])
        self.run_install("--remove-bundle", "two", check=0)
        self.assertNotIn("helped", self.claude()["mcpServers"])
        self.assertIn("stub", self.claude()["mcpServers"])

    def test_helper_entry_points_at_the_token_file_and_holds_no_secret(self):
        self.run_install("--mcp", check=0)
        helper = self.claude()["mcpServers"]["helped"]["headersHelper"]
        self.assertIn(str(self.repo / "mcp/remote/helped/auth.py"), helper)
        self.assertIn(str(self.home / ".config/super-computer-ai/credentials/helped/token.txt"), helper)
        self.assertIn('http_headers_helper = "', self.codex())

    def test_j_dry_run_and_check_never_print_values(self):
        self.overlay({"acct-main": {"server": "acct", "env": {"ACCT_CONFIG": str(write(self.home / "acct.json", "{}"))}}})
        for args in (("--dry-run", "--mcp"), ("--check",)):
            result = self.run_install(*args)
            out = result.stdout + result.stderr
            self.assertNotIn(FAKE[:12], out)
            self.assertNotIn("Zq9Zq9", out)
            self.assertNotIn(str(self.home / "acct.json"), out)
        self.assertIn("add mcp claude:user:acct-main", self.run_install("--dry-run", "--mcp").stdout)

    def test_running_client_blocks_with_zero_writes(self):
        before = self.files()
        result = self.run_install("--mcp", check=4, env={"SCAI_TEST_CLIENT_PROCS": "claude (pid 1)"})
        self.assertIn("close", result.stdout.lower())
        self.assertEqual(before, self.files())
        self.assertEqual([], self.journals())

    def test_missing_swap_syscall_is_a_conflict_not_a_blind_replace(self):
        before = self.files()
        result = self.run_install("--mcp", env={"SCAI_TEST_NO_SWAP": "1"})
        self.assertEqual(2, result.returncode, result.stdout)
        self.assertIn("atomic swap", result.stdout)
        self.assertEqual(before, self.files())
        self.assertEqual([], self.leftovers())

    def test_unrelated_client_change_between_runs_is_kept(self):
        self.run_install("--mcp", check=0)
        doc = self.claude()
        doc["numStartups"] = 99                      # what Claude Code does all the time
        write(self.home / ".claude.json", json.dumps(doc, indent=2, ensure_ascii=False), mode=0o600)
        self.run_install("--check", check=0)
        self.run_install("--uninstall", check=0)
        self.assertEqual(99, self.claude()["numStartups"])
        self.assertNotIn("stub", self.claude()["mcpServers"])


class OwnershipTest(McpBase):
    def test_unowned_entry_with_the_same_name_is_a_conflict_until_mapped(self):
        doc = claude_doc(self.home)
        doc["mcpServers"]["stub"] = {"command": "old-stub"}
        write(self.home / ".claude.json", json.dumps(doc, indent=2, ensure_ascii=False), mode=0o600)
        before = self.files()
        result = self.run_install("--mcp", check=2)
        self.assertIn("not owned", result.stdout)
        fingerprint = result.stdout.split("fingerprint sha256:")[1].split(")")[0]
        self.assertEqual(before, self.files())
        write(self.home / ".config/super-computer-ai/private/migration/mcp_map.json", json.dumps(
            {"schema_version": 1, "entries": {"claude/user/stub": {"sha256": fingerprint}}}))
        self.run_install("--mcp", check=0)
        self.assertEqual(self.claude()["mcpServers"]["stub"]["args"][-1], "claude")
        self.assertEqual(list(self.claude()["mcpServers"])[2], "stub", "adopted entry keeps its position")
        self.run_install("--rollback", self.last_journal().name, check=0)
        self.assertEqual(before, self.files())

    def test_legacy_entries_are_retired_only_with_the_exact_fingerprint(self):
        doc = claude_doc(self.home)
        doc["mcpServers"]["old-server"] = {"command": "java", "args": ["-jar", "old.jar"]}
        write(self.home / ".claude.json", json.dumps(doc, indent=2, ensure_ascii=False), mode=0o600)
        write(self.home / ".codex/config.toml", CODEX + '\n[mcp_servers.old-server]\ncommand = "java"\n', mode=0o600)
        before = self.files()
        claude_fp = __import__("hashlib").sha256(json.dumps(doc["mcpServers"]["old-server"], sort_keys=True,
                                                            separators=(",", ":")).encode()).hexdigest()
        codex_fp = __import__("hashlib").sha256(b'[mcp_servers.old-server]\ncommand = "java"\n').hexdigest()
        mapping = self.home / ".config/super-computer-ai/private/migration/mcp_map.json"
        write(mapping, json.dumps({"schema_version": 1, "entries": {
            "claude/user/old-server": {"sha256": "0" * 64, "retire": True},
            "codex/user/old-server": {"sha256": codex_fp, "retire": True}}}))
        self.assertIn("differs from its reviewed fingerprint", self.run_install("--mcp", check=2).stdout)
        self.assertEqual(before, self.files())
        write(mapping, json.dumps({"schema_version": 1, "entries": {
            "claude/user/old-server": {"sha256": claude_fp, "retire": True},
            "codex/user/old-server": {"sha256": codex_fp, "retire": True}}}))
        self.run_install("--mcp", check=0)
        self.assertNotIn("old-server", self.claude()["mcpServers"])
        self.assertNotIn("old-server", self.codex())
        self.run_install("--rollback", self.last_journal().name, check=0)
        self.assertEqual(before, self.files())

    def test_local_scope_legacy_entry_is_retired_and_rolled_back(self):
        before = self.files()
        unity = json.dumps({"command": "u"}, sort_keys=True, separators=(",", ":"))
        fingerprint = __import__("hashlib").sha256(unity.encode()).hexdigest()
        mapping = self.home / ".config/super-computer-ai/private/migration/mcp_map.json"
        key = f"claude/local:{self.home / 'proj'}/UnityMCP"
        write(mapping, json.dumps({"schema_version": 1, "entries": {key: {"sha256": "0" * 64, "retire": True}}}))
        self.assertIn("differs from its reviewed fingerprint", self.run_install("--mcp", check=2).stdout)
        self.assertEqual(before, self.files())
        write(mapping, json.dumps({"schema_version": 1, "entries": {key: {"sha256": fingerprint, "retire": True}}}))
        self.run_install("--mcp", check=0)
        self.assertNotIn("UnityMCP", self.claude()["projects"][str(self.home / "proj")].get("mcpServers", {}))
        self.run_install("--rollback", self.last_journal().name, check=0)
        self.assertEqual(before, self.files())

    def test_malformed_mcp_map_keys_are_conflicts(self):
        mapping = self.home / ".config/super-computer-ai/private/migration/mcp_map.json"
        for key in ("claude/UnityMCP", "codex/local:/x/y", "claude/local:relative/x", "other/user/x",
                    "claude/local:/a/../b/x"):
            with self.subTest(key=key):
                write(mapping, json.dumps({"schema_version": 1, "entries": {key: {"sha256": "0" * 64, "retire": True}}}))
                self.assertIn("mcp_map key", self.run_install("--mcp", "--dry-run", check=2).stdout)

    def test_entry_edited_between_check_and_write_is_never_overwritten(self):
        for fmt in ("claude-json", "codex-toml"):
            with self.subTest(fmt=fmt, direction="forward"):
                home = self.make_home(self.root / f"edit-fwd-{fmt}")
                step = next(s["id"] for s in self._probe_steps(home) if s["entry"]["format"] == fmt
                            and s["entry"]["name"] == "stub")
                result = self.run_install("--mcp", home=home, env={"SCAI_TEST_EDIT_ENTRY": str(step)})
                self.assertEqual(2, result.returncode, result.stdout)
                self.assertIn("changed while the installer was working on it", result.stdout)
                self.assertIn("USER-EDIT", (home / (".claude.json" if fmt == "claude-json" else ".codex/config.toml")).read_text())
            with self.subTest(fmt=fmt, direction="rollback"):
                home = self.make_home(self.root / f"edit-rb-{fmt}")
                self.run_install("--mcp", home=home, check=0)
                journal = self.last_journal(home)
                step = next(s["id"] for s in self.entry_steps(journal) if s["entry"]["format"] == fmt
                            and s["entry"]["name"] == "stub")
                result = self.run_install("--rollback", journal.name, home=home, env={"SCAI_TEST_EDIT_ENTRY": f"rb:{step}"})
                self.assertEqual(2, result.returncode, result.stdout)
                self.assertIn("USER-EDIT", (home / (".claude.json" if fmt == "claude-json" else ".codex/config.toml")).read_text())

    def test_owned_entry_edited_by_hand_is_never_overwritten(self):
        self.run_install("--mcp", check=0)
        doc = self.claude()
        doc["mcpServers"]["stub"]["env"] = {"USER_EDIT": "1"}
        write(self.home / ".claude.json", json.dumps(doc, indent=2, ensure_ascii=False), mode=0o600)
        edited = self.files()
        self.assertIn("changed since install", self.run_install("--no-mcp", check=2).stdout)
        self.assertEqual(edited, self.files(), "a refused plan writes nothing")
        result = self.run_install("--rollback", self.last_journal().name)
        self.assertEqual(2, result.returncode, result.stdout)     # rollback stops at the edited entry (plan §8.3 e2)
        self.assertEqual({"USER_EDIT": "1"}, self.claude()["mcpServers"]["stub"]["env"], "the user's change is kept")
        self.assertIn("left open", result.stdout)

    def test_unsupported_file_shapes_are_refused(self):
        write(self.home / ".claude.json", json.dumps(claude_doc(self.home), indent=4), mode=0o600)
        before = self.files()
        self.assertIn("round-trip", self.run_install("--mcp", check=2).stdout)
        self.assertEqual(before, self.files())
        write(self.home / ".claude.json", json.dumps(claude_doc(self.home), indent=2, ensure_ascii=False), mode=0o600)
        write(self.home / ".codex/config.toml", CODEX + 'notes = """\n[mcp_servers.fake]\n"""\n', mode=0o600)
        before = self.files()
        self.assertIn("multi-line", self.run_install("--mcp", check=2).stdout)
        self.assertEqual(before, self.files())

    def test_local_scope_needs_an_existing_claude_project(self):
        self.overlay({"acct-proj": {"server": "acct", "env": {"ACCT_CONFIG": str(write(self.home / "a.json", "{}"))},
                                    "claude_scope": "local:~/proj"}})
        self.run_install("--mcp", check=0)
        project = self.claude()["projects"][str(self.home / "proj")]
        self.assertEqual(list(project["mcpServers"]), ["UnityMCP", "acct-proj"])
        self.assertNotIn("acct-proj", self.claude()["mcpServers"])
        self.overlay({"acct-proj": {"server": "acct", "env": {"ACCT_CONFIG": str(self.home / "a.json")},
                                    "claude_scope": "local:~/proj"},
                      "acct-other": {"server": "acct", "env": {"ACCT_CONFIG": str(self.home / "a.json")},
                                     "claude_scope": "local:~/never-opened"}})
        self.assertIn("open Claude Code there once", self.run_install("--mcp", check=2).stdout)


class ProjectRetireTest(McpBase):
    """Legacy entries in a project's repository file (<dir>/.mcp.json) are retired through the same journaled,
    fingerprint-checked entry steps (retire only — the installer never adds entries to a project file)."""

    PROJECT = {"mcpServers": {"ads-old": {"type": "stdio", "command": "uv", "args": ["run", "server.py"]},
                              "ads-test": {"type": "stdio", "command": "uv", "args": ["run", "test.py"]},
                              "ads-meta": {"type": "http", "url": "https://example.invalid/mcp"}}}

    def setUp(self):
        super().setUp()
        self.project = self.home / "Projects" / "Ads"
        self.mcp_json = write(self.project / ".mcp.json", json.dumps(self.PROJECT, indent=2), mode=0o644)

    def fingerprint(self, name):
        return __import__("hashlib").sha256(json.dumps(self.PROJECT["mcpServers"][name], sort_keys=True,
                                                       separators=(",", ":")).encode()).hexdigest()

    def map_entries(self, entries):
        write(self.home / ".config/super-computer-ai/private/migration/mcp_map.json",
              json.dumps({"schema_version": 1, "entries": entries}))

    def key(self, name):
        return f"claude/project:{self.project}/{name}"

    def test_reviewed_project_entries_are_retired_and_rolled_back_bit_identically(self):
        original = self.mcp_json.read_bytes()
        self.map_entries({self.key(n): {"sha256": self.fingerprint(n), "retire": True} for n in ("ads-old", "ads-meta")})
        self.run_install("--mcp", check=0)
        left = json.loads(self.mcp_json.read_text())["mcpServers"]
        self.assertEqual(list(left), ["ads-test"], "only reviewed entries go; the rest of the project file stays")
        self.assertEqual(0o644, self.mcp_json.stat().st_mode & 0o777)
        self.run_install("--rollback", self.last_journal().name, check=0)
        self.assertEqual(original, self.mcp_json.read_bytes())

    def test_changed_project_entry_or_non_retire_key_is_a_conflict_with_zero_writes(self):
        original = self.mcp_json.read_bytes()
        self.map_entries({self.key("ads-old"): {"sha256": "0" * 64, "retire": True}})
        self.assertIn("differs from its reviewed fingerprint", self.run_install("--mcp", check=2).stdout)
        self.map_entries({self.key("ads-old"): {"sha256": self.fingerprint("ads-old")}})
        self.assertIn("can only be retired", self.run_install("--mcp", check=2).stdout)
        self.assertEqual(original, self.mcp_json.read_bytes())
        self.assertEqual([], self.journals())

    def _project_home(self, name):
        home = self.make_home(self.root / name)
        project = home / "Projects" / "Ads"
        mcp_json = write(project / ".mcp.json", json.dumps(self.PROJECT, indent=2), mode=0o644)
        write(home / ".config/super-computer-ai/private/migration/mcp_map.json", json.dumps(
            {"schema_version": 1, "entries": {f"claude/project:{project}/ads-old":
                                              {"sha256": self.fingerprint("ads-old"), "retire": True}}}))
        return home, project, mcp_json

    def test_interrupted_project_retire_resumes_or_rolls_back(self):
        probe, _, _ = self._project_home("pr-probe")             # same layout, its own paths: step ids match
        self.run_install("--mcp", home=probe, check=0)
        step = next(st["id"] for st in self.entry_steps(self.last_journal(probe)) if st["entry"]["scope"].startswith("project:"))
        for point in ("entry-after-prepare", "entry-after-swap", "entry-after-verify-record", "after-apply"):
            for direction in ("resume", "rollback"):
                with self.subTest(point=point, direction=direction):
                    home, project, mcp_json = self._project_home(f"pr-{point}-{direction}")
                    original = mcp_json.read_bytes()
                    self.assertEqual(99, self.run_install("--mcp", home=home, env={"SCAI_FAULT": f"{step}:{point}"}).returncode)
                    if direction == "resume":
                        self.run_install("--resume", home=home, check=0)
                        self.assertNotIn("ads-old", json.loads(mcp_json.read_text())["mcpServers"])
                    else:
                        self.run_install("--rollback", self.last_journal(home).name, home=home, check=0)
                        self.assertEqual(original, mcp_json.read_bytes())
                    self.assertEqual([], sorted(p.name for p in project.iterdir() if ".scai-swap-" in p.name))


class StatusTest(McpBase):
    """install.py --status: the fitting recovery command per journal; --after limits it to a cutover's journals."""

    def test_status_reports_each_state_with_the_right_command(self):
        self.run_install("--mcp", check=0)
        done = self.last_journal().name
        result = self.run_install("--status", check=0)
        self.assertIn(f"{done}  complete", result.stdout)
        self.assertIn(f"--rollback {done}", result.stdout)
        # an interrupted run: open -> resume or rollback, exit 4
        self.assertEqual(99, self.run_install("--no-mcp", env={"SCAI_FAULT": "2:after-done"}).returncode)  # steps 0-2 done
        open_name = self.last_journal().name
        result = self.run_install("--status", "--after", done, check=4)
        self.assertIn(f"{open_name}  open", result.stdout)
        self.assertIn("--resume", result.stdout)
        self.assertNotIn(done, result.stdout, "--after hides the journals written before the cutover")
        # an interrupted rollback: rolling_back -> only --rollback, never --resume
        self.assertEqual(99, self.run_install("--rollback", open_name, env={"SCAI_FAULT": "rb:0:after-intent"}).returncode)
        result = self.run_install("--status", "--after", done, check=4)
        self.assertIn(f"{open_name}  rolling_back", result.stdout)
        self.assertIn(f"--rollback {open_name}", result.stdout)
        self.assertNotIn("--resume", result.stdout)
        # an unfinished journal that existed before --after is still shown, flagged
        result = self.run_install("--status", "--after", open_name, check=4)
        self.assertIn("existed before --after", result.stdout)

    def test_status_without_journals(self):
        self.assertIn("no journals", self.run_install("--status", check=0).stdout)


class OverlayTest(McpBase):
    def test_first_time_invalid_instance_is_skipped_with_a_notice_and_check_reports_it(self):
        self.overlay({"acct-main": {"server": "acct", "env": {"ACCT_CONFIG": str(self.home / "missing.json")}},
                      "stub-secret": {"server": "stub", "env": {"STUB_KEY": "inline"}}})
        result = self.run_install("--mcp", check=0)
        self.assertIn("acct-main' not installed", result.stdout)
        self.assertIn("is secret", result.stdout)
        self.assertNotIn("acct-main", self.claude()["mcpServers"])
        self.assertNotIn("stub", self.claude()["mcpServers"], "an invalid overlay instance still suppresses the default")
        self.run_install("--check", check=1)

    def test_installed_instance_whose_file_disappears_is_a_conflict_not_a_removal(self):
        config = write(self.home / "acct.json", "{}")
        self.overlay({"acct-main": {"server": "acct", "env": {"ACCT_CONFIG": str(config)}}})
        self.run_install("--mcp", check=0)
        installed = self.files()
        config.unlink()
        result = self.run_install(check=2)
        self.assertIn("--remove-mcp acct-main", result.stdout)
        self.assertEqual(installed, self.files())
        self.run_install("--remove-mcp", "acct-main", check=0)
        self.assertNotIn("acct-main", self.claude()["mcpServers"])

    def test_overlay_removed_after_install_is_a_conflict(self):
        config = write(self.home / "acct.json", "{}")
        self.overlay({"acct-main": {"server": "acct", "env": {"ACCT_CONFIG": str(config)}},
                      "stub-main": {"server": "stub", "env": {"STUB_MODE": "x"}}})
        self.run_install("--mcp", check=0)
        installed = self.files()
        shutil.rmtree(self.home / ".config/super-computer-ai/private")
        result = self.run_install(check=2)
        self.assertIn("no longer defined in the overlay", result.stdout)
        self.assertEqual(installed, self.files())
        self.assertNotIn("stub-alt", self.claude()["mcpServers"], "no default instance replaces an owned overlay one")

    def test_instance_deleted_from_a_valid_overlay_needs_remove_mcp(self):
        config = write(self.home / "acct.json", "{}")
        self.overlay({"acct-main": {"server": "acct", "env": {"ACCT_CONFIG": str(config)}},
                      "acct-test": {"server": "acct", "env": {"ACCT_CONFIG": str(config)}}})
        self.run_install("--mcp", check=0)
        self.overlay({"acct-main": {"server": "acct", "env": {"ACCT_CONFIG": str(config)}}})
        self.assertIn("--remove-mcp acct-test", self.run_install(check=2).stdout)
        self.run_install("--remove-mcp", "acct-test", check=0)
        self.assertNotIn("acct-test", self.claude()["mcpServers"])
        self.assertIn("acct-main", self.claude()["mcpServers"])

    def test_required_env_missing_empty_or_relative_is_invalid(self):
        config = write(self.home / "acct.json", "{}")
        self.overlay({"acct-none": {"server": "acct"},
                      "acct-empty": {"server": "acct", "env": {"ACCT_CONFIG": " "}},
                      "acct-rel": {"server": "acct", "env": {"ACCT_CONFIG": "acct.json"}},
                      "acct-relopt": {"server": "acct", "env": {"ACCT_CONFIG": str(config), "ACCT_AUDIT": "logs/a.jsonl"}},
                      "acct-ok": {"server": "acct", "env": {"ACCT_CONFIG": "~/acct.json"}}})
        result = self.run_install("--mcp", check=0)
        servers = self.claude()["mcpServers"]
        for name, reason in (("acct-none", "is required"), ("acct-empty", "is required"), ("acct-rel", "absolute path"),
                             ("acct-relopt", "absolute path")):
            self.assertNotIn(name, servers)
            self.assertIn(f"'{name}' not installed", result.stdout)
            self.assertIn(reason, result.stdout.split(f"'{name}' not installed")[1].splitlines()[0])
        self.assertIn("acct-ok", servers)
        spec = json.loads((self.home / ".local/state/super-computer-ai/mcp/instances.json").read_text())["instances"]
        self.assertEqual(spec["acct-ok"]["env"], {"ACCT_CONFIG": str(config)})

    def test_wrapper_never_inherits_another_accounts_configuration(self):
        config = write(self.home / "acct.json", "{}")
        self.overlay({"acct-test": {"server": "acct", "env": {"ACCT_CONFIG": str(config)}}})
        self.run_install("--mcp", check=0)
        entry = self.claude()["mcpServers"]["acct-test"]
        out = self.root / "acct-out.json"
        env = {"PATH": os.environ["PATH"], "STUB_OUT": str(out),       # exported by a shell set up for production:
               "ACCT_CONFIG": "/prod/config.json", "ACCT_AUDIT": "/prod/audit.jsonl", "OLD_ACCT_CONFIG": "/prod/old.json"}
        result = subprocess.run([entry["command"], *entry["args"]], env=env, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        got = {k: v for k, v in json.loads(out.read_text())["env"].items() if k != "STUB_OUT"}
        self.assertEqual(got, {"ACCT_CONFIG": str(config)}, "only the instance's own configuration reaches the server")

    def test_credentials_file_supplies_only_declared_secrets(self):
        config = write(self.home / "acct.json", "{}")
        self.overlay({"acct-test": {"server": "acct", "env": {"ACCT_CONFIG": str(config)}}})
        write(self.home / ".config/super-computer-ai/credentials/acct/.env",
              "ACCT_TOKEN=t0k\nACCT_CONFIG=/prod/config.json\nACCT_AUDIT=/prod/audit.jsonl\nOLD_ACCT_CONFIG=/prod/old.json\n",
              mode=0o600)
        self.run_install("--mcp", check=0)
        entry = self.claude()["mcpServers"]["acct-test"]
        out = self.root / "creds-out.json"
        result = subprocess.run([entry["command"], *entry["args"]], capture_output=True, text=True,
                                env={"PATH": os.environ["PATH"], "STUB_OUT": str(out)})
        self.assertEqual(0, result.returncode, result.stderr)
        got = {k: v for k, v in json.loads(out.read_text())["env"].items() if k != "STUB_OUT"}
        self.assertEqual(got, {"ACCT_CONFIG": str(config), "ACCT_TOKEN": "t0k"})
        self.assertIn("ignoring non-secret keys", result.stderr)
        self.assertNotIn("/prod", result.stderr, "names only, never values")
        self.assertEqual("", result.stdout)

    def test_codex_only_instance_and_codex_tool_filter(self):
        self.overlay({"helped-main": {"server": "helped", "helper_args": [str(write(self.home / "tok", "t"))],
                                      "clients": ["codex"], "codex": {"enabled_tools": ["a", "b"]}}})
        self.run_install("--mcp", check=0)
        self.assertNotIn("helped-main", self.claude()["mcpServers"])
        self.assertIn('[mcp_servers.helped-main]\nurl = "https://example.invalid/mcp"', self.codex())
        self.assertIn('enabled_tools = ["a", "b"]', self.codex())


class WrapperIsolationTest(McpBase):
    """§3b: the generated entry carries its own spec; the wrapper never falls back to the process HOME."""

    def run_entry(self, home: Path, name: str, process_home: Path, extra_env=None) -> dict:
        entry = self.claude(home)["mcpServers"][name]
        out = self.root / f"out-{home.name}-{name}.json"
        env = {"PATH": os.environ["PATH"], "HOME": str(process_home), "STUB_OUT": str(out), "STUB_MODE": "exported"}
        env.update(extra_env or {})
        result = subprocess.run([entry["command"], *entry["args"]], env=env, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stdout, "the wrapper must not write to stdout (MCP protocol channel)")
        return json.loads(out.read_text())

    def test_two_homes_never_read_each_others_spec_env_or_credentials(self):
        other = self.make_home(self.root / "other")
        for home, mode in ((self.home, "first"), (other, "second")):
            self.overlay({"stub-main": {"server": "stub", "env": {"STUB_MODE": mode}}}, home=home)
            write(home / ".config/super-computer-ai/credentials/stub/.env", f"STUB_KEY={mode}-secret\n", mode=0o600)
            self.run_install("--mcp", home=home, check=0)
        first = self.run_entry(self.home, "stub-main", process_home=other)
        second = self.run_entry(other, "stub-main", process_home=self.home)
        self.assertEqual(first["env"], {"STUB_MODE": "first", "STUB_KEY": "first-secret", "STUB_OUT": first["env"]["STUB_OUT"]})
        self.assertEqual(second["env"]["STUB_MODE"], "second")
        self.assertEqual(second["env"]["STUB_KEY"], "second-secret")
        self.assertEqual(first["argv"], ["--who", "claude"])

    def test_scai_home_and_overlay_flag_are_resolved_at_install_time(self):
        scai = self.root / "scai"
        write(scai / "credentials/stub/.env", "STUB_KEY=from-scai\n", mode=0o600)
        write(scai / "private/mcp/instances.json", json.dumps({"schema_version": 1, "instances": {
            "stub-main": {"server": "stub", "env": {"STUB_MODE": "scai"}}}}))
        # --home ignores $SCAI_HOME (isolation); an explicit --overlay is honoured
        self.run_install("--mcp", "--overlay", str(scai / "private"), env={"SCAI_HOME": str(scai)}, check=0)
        got = self.run_entry(self.home, "stub-main", process_home=self.root, extra_env={"SCAI_HOME": "/nowhere"})
        self.assertEqual(got["env"]["STUB_MODE"], "scai")
        self.assertNotIn("STUB_KEY", got["env"], "credentials come from the install HOME, never from $SCAI_HOME at runtime")

    def test_credentials_file_must_be_private_and_exported_values_win(self):
        self.overlay({"stub-main": {"server": "stub", "env": {}}})
        creds = write(self.home / ".config/super-computer-ai/credentials/stub/.env", "STUB_KEY=file\n", mode=0o644)
        self.run_install("--mcp", check=0)
        entry = self.claude()["mcpServers"]["stub-main"]
        result = subprocess.run([entry["command"], *entry["args"]], capture_output=True, text=True,
                                env={"PATH": os.environ["PATH"], "STUB_OUT": str(self.root / "x.json")})
        self.assertEqual(2, result.returncode)
        self.assertIn("chmod 600", result.stderr)
        self.assertEqual("", result.stdout)
        creds.chmod(0o600)
        got = self.run_entry(self.home, "stub-main", self.home, extra_env={"STUB_KEY": "exported"})
        self.assertEqual(got["env"]["STUB_KEY"], "exported")

    def test_unknown_instance_or_spec_fails_cleanly(self):
        self.run_install("--mcp", check=0)
        entry = self.claude()["mcpServers"]["stub"]
        args = list(entry["args"])
        args[args.index("stub")] = "nope"
        result = subprocess.run([entry["command"], *args], capture_output=True, text=True)
        self.assertEqual((2, ""), (result.returncode, result.stdout))
        self.assertIn("not in", result.stderr)


class FaultTest(McpBase):
    """§5a: kills at every point of an entry write; races end in a lossless conflict."""

    POINTS = ("after-intent", "entry-after-prepare", "entry-after-swap", "entry-after-verify-record",
              "entry-after-tmp-unlink", "after-apply", "after-done")

    def entry_ids(self, home: Path) -> dict:
        probe = self.root / f"probe-{home.name}"
        shutil.copytree(home, probe, symlinks=True)
        self.run_install("--mcp", home=probe, check=0)
        steps = self.entry_steps(self.last_journal(probe))
        shutil.rmtree(probe)
        return {(s["entry"]["format"], s["entry"]["name"]): s["id"] for s in steps}

    def assert_resume_and_rollback(self, home: Path, fault: str, original: dict, expected: dict):
        # --resume
        work = self.root / f"w-{fault.replace(':', '_')}"
        shutil.copytree(home, work, symlinks=True)
        result = self.run_install("--mcp", home=work, env={"SCAI_FAULT": fault})
        self.assertEqual(99, result.returncode, f"{fault}: {result.stdout}")
        self.run_install("--resume", home=work, check=0)
        self.assertEqual(self.normalize(expected, home), self.normalize(self.files(work), work, home), fault)
        self.assertEqual([], self.leftovers(work), fault)
        # direct --rollback (no resume in between)
        work2 = self.root / f"r-{fault.replace(':', '_')}"
        shutil.copytree(home, work2, symlinks=True)
        self.assertEqual(99, self.run_install("--mcp", home=work2, env={"SCAI_FAULT": fault}).returncode)
        self.run_install("--rollback", self.last_journal(work2).name, home=work2, check=0)
        self.assertEqual(self.normalize(original, home), self.normalize(self.files(work2), work2, home), fault)
        self.assertEqual([], self.leftovers(work2), fault)
        shutil.rmtree(work)
        shutil.rmtree(work2)

    @staticmethod
    def normalize(files: dict, *homes: Path) -> dict:
        """Replace HOME paths (a copied HOME still contains the original HOME's paths in its files)."""
        out = {}
        for key, value in files.items():
            for home in sorted(homes, key=lambda h: -len(str(h))):
                value = value.replace(str(home).encode(), b"<HOME>") if value is not None else None
            out[key] = value
        return out

    def expected_after_install(self, home: Path) -> dict:
        ref = self.root / f"ref-{home.name}"
        shutil.copytree(home, ref, symlinks=True)
        self.run_install("--mcp", home=ref, check=0)
        files = self.files(ref)
        shutil.rmtree(ref)
        return self.normalize(files, ref, home)

    def test_kill_points_existing_files(self):
        original = self.files()
        expected = {k: (v.replace(b"<HOME>", str(self.home).encode()) if v else v)
                    for k, v in self.expected_after_install(self.home).items()}
        ids = self.entry_ids(self.home)
        for fmt in ("claude-json", "codex-toml"):
            step = ids[(fmt, "stub")]
            for point in self.POINTS:
                with self.subTest(fmt=fmt, point=point):
                    self.assert_resume_and_rollback(self.home, f"{step}:{point}", original, expected)

    def test_kill_points_in_a_clean_home_create_and_remove_the_files(self):
        clean = self.make_home(self.root / "clean", codex=False, claude=False)
        original = self.files(clean)
        self.assertEqual({".claude.json": None, ".codex/config.toml": None}, original)
        expected = {k: (v.replace(b"<HOME>", str(clean).encode()) if v else v)
                    for k, v in self.expected_after_install(clean).items()}
        ids = self.entry_ids(clean)
        first = min(ids.values())           # the step that creates a file
        for point in ("entry-after-prepare", "entry-after-swap", "entry-after-verify-record", "entry-after-tmp-unlink"):
            with self.subTest(point=point):
                self.assert_resume_and_rollback(clean, f"{first}:{point}", original, expected)
        self.run_install("--mcp", home=clean, check=0)
        self.run_install("--rollback", self.last_journal(clean).name, home=clean, check=0)
        self.assertEqual(original, self.files(clean))
        self.assertFalse((clean / ".codex/config.toml").exists())

    def test_rollback_kill_points(self):
        for fmt in ("claude-json", "codex-toml"):
            for point in ("entry-after-prepare", "entry-after-swap", "entry-after-verify-record", "entry-after-tmp-unlink"):
                with self.subTest(fmt=fmt, point=point):
                    work = self.make_home(self.root / f"rb-{fmt}-{point}")   # journals hold absolute paths: fresh HOME
                    original = self.files(work)
                    self.run_install("--mcp", home=work, check=0)
                    journal = self.last_journal(work)
                    step = next(s["id"] for s in self.entry_steps(journal)
                                if s["entry"]["format"] == fmt and s["entry"]["name"] == "stub")
                    result = self.run_install("--rollback", journal.name, home=work, env={"SCAI_FAULT": f"rb:{step}:{point}"})
                    self.assertEqual(99, result.returncode, result.stdout)
                    self.run_install("--rollback", journal.name, home=work, check=0)
                    self.assertEqual(original, self.files(work))
                    self.assertEqual([], self.leftovers(work))

    def test_row4_killed_after_prepare_then_unrelated_change_redoes_the_entry(self):
        step = self.entry_ids(self.home)[("claude-json", "stub")]
        self.assertEqual(99, self.run_install("--mcp", env={"SCAI_FAULT": f"{step}:entry-after-prepare"}).returncode)
        doc = self.claude()
        doc["numStartups"] = 42                             # Claude wrote the file after our temp was prepared
        write(self.home / ".claude.json", json.dumps(doc, indent=2, ensure_ascii=False), mode=0o600)
        self.run_install("--resume", check=0)
        self.assertEqual(42, self.claude()["numStartups"])
        self.assertIn("stub", self.claude()["mcpServers"])
        self.assertEqual([], self.leftovers())

    def test_row11_swap_done_but_temp_missing_is_a_conflict(self):
        step = self.entry_ids(self.home)[("claude-json", "stub")]
        self.assertEqual(99, self.run_install("--mcp", env={"SCAI_FAULT": f"{step}:entry-after-swap"}).returncode)
        for name in self.leftovers():
            (self.home / name).unlink()                     # the pre-swap content can no longer be proven intact
        live = self.files()
        result = self.run_install("--resume")
        self.assertEqual(2, result.returncode, result.stdout)
        self.assertEqual(live, self.files())

    def test_rows7_13_verified_but_temp_replaced_is_kept(self):
        for label, home, fmt in (("swap", self.home, "claude-json"),
                                 ("create", self.make_home(self.root / "c713", codex=False, claude=False), "codex-toml")):
            with self.subTest(label):
                ids = self.entry_ids(home)
                step = min(i for (f, _), i in ids.items() if f == fmt)
                self.assertEqual(99, self.run_install("--mcp", home=home,
                                                      env={"SCAI_FAULT": f"{step}:entry-after-verify-record"}).returncode)
                tmp = [p for d in (home, home / ".codex") if d.is_dir() for p in d.iterdir() if ".scai-swap-" in p.name]
                self.assertEqual(1, len(tmp))
                tmp[0].unlink()
                tmp[0].write_text("someone else's content\n")  # unknown content (a new inode) at the temp name
                result = self.run_install("--resume", home=home)
                self.assertEqual(2, result.returncode, result.stdout)
                self.assertEqual("someone else's content\n", tmp[0].read_text())

    def test_delete_flow_kill_points_in_rollback_of_a_clean_home(self):
        for point in ("entry-after-prepare", "entry-after-swap", "entry-after-verify-record", "entry-after-tmp-unlink"):
            with self.subTest(point=point):
                home = self.make_home(self.root / f"del-{point}", codex=False, claude=False)
                self.run_install("--mcp", home=home, check=0)
                journal = self.last_journal(home)
                creator = min(s["id"] for s in self.entry_steps(journal) if s["entry"]["format"] == "codex-toml")
                result = self.run_install("--rollback", journal.name, home=home, env={"SCAI_FAULT": f"rb:{creator}:{point}"})
                self.assertEqual(99, result.returncode, result.stdout)
                self.run_install("--rollback", journal.name, home=home, check=0)
                self.assertEqual({".claude.json": None, ".codex/config.toml": None}, self.files(home))
                self.assertEqual([], self.leftovers(home))

    def test_concurrent_write_during_file_removal_is_restored_not_lost(self):
        home = self.make_home(self.root / "delrace", codex=False, claude=False)
        self.run_install("--mcp", home=home, check=0)
        journal = self.last_journal(home)
        creator = min(s["id"] for s in self.entry_steps(journal) if s["entry"]["format"] == "codex-toml")
        result = self.run_install("--rollback", journal.name, home=home, env={"SCAI_TEST_TOUCH": f"rb:{creator}"})
        self.assertEqual(2, result.returncode, result.stdout)
        self.assertTrue(self.codex(home).endswith("# written concurrently\n"), "the newer version is back in place")
        self.assertEqual([], self.leftovers(home))

    def test_recovery_itself_killed_between_temp_removal_and_journal_write(self):
        cases = (("swap", False, "claude-json"), ("create", True, "codex-toml"))
        for label, clean, fmt in cases:
            for direction in ("resume", "rollback"):
                with self.subTest(label=label, direction=direction):
                    home = self.make_home(self.root / f"rec-{label}-{direction}", codex=not clean, claude=not clean)
                    original = self.files(home)
                    ids = self._probe_steps(home)
                    step = (min(s["id"] for s in ids if s["entry"]["format"] == fmt) if clean else
                            next(s["id"] for s in ids if s["entry"]["format"] == fmt and s["entry"]["name"] == "stub"))
                    # 1) the install is killed after the swap record is prepared (row 3 / row 8: cleanup needed)
                    self.assertEqual(99, self.run_install("--mcp", home=home,
                                                          env={"SCAI_FAULT": f"{step}:entry-after-prepare"}).returncode)
                    journal = self.last_journal(home).name
                    # 2) the recovery is killed after removing our temp file, before recording it
                    args = ("--resume",) if direction == "resume" else ("--rollback", journal)
                    result = self.run_install(*args, home=home, env={"SCAI_FAULT": f"{step}:reconcile-after-unlink"})
                    self.assertEqual(99, result.returncode, result.stdout)
                    # 3) the next recovery completes without a conflict
                    self.run_install(*args, home=home, check=0)
                    self.assertEqual([], self.leftovers(home))
                    if direction == "rollback":
                        self.assertEqual(original, self.files(home))
                    else:
                        self.run_install("--check", home=home, check=0)

    def test_concurrent_write_before_swap_is_a_lossless_conflict(self):
        ids = self.entry_ids(self.home)
        step = ids[("claude-json", "stub")]
        result = self.run_install("--mcp", env={"SCAI_TEST_TOUCH": str(step)})
        self.assertEqual(2, result.returncode, result.stdout)
        self.assertIn("concurrent version", result.stdout)
        kept = [self.home / n for n in self.leftovers()]
        self.assertEqual(1, len(kept))
        concurrent = json.loads(kept[0].read_text())
        self.assertTrue(concurrent["concurrentWrite"], "the concurrent version is kept byte for byte")
        self.assertIn("stub", self.claude()["mcpServers"], "the live file holds the installer's version")
        self.assertEqual(2, self.run_install("--resume").returncode, "resume refuses until the human merged")
        self.assertEqual(2, self.run_install("--rollback", self.last_journal().name).returncode)
        kept[0].unlink()                                   # the human merged and removed the copy
        self.run_install("--resume", check=0)
        self.assertEqual([], self.leftovers())

    def test_race_detected_then_killed_is_still_a_conflict_from_the_files_alone(self):
        step = self.entry_ids(self.home)[("codex-toml", "stub")]
        result = self.run_install("--mcp", env={"SCAI_TEST_TOUCH": str(step), "SCAI_FAULT": f"{step}:entry-after-detect"})
        self.assertEqual(99, result.returncode)
        result = self.run_install("--resume")
        self.assertEqual(2, result.returncode, result.stdout)
        kept = [self.home / ".codex" / n for n in self.leftovers() if n.startswith(".config.toml")]
        self.assertEqual(1, len(kept))
        self.assertTrue(kept[0].read_text().endswith("# written concurrently\n"))

    def test_file_created_by_someone_else_during_creation(self):
        clean = self.make_home(self.root / "clean2", codex=False, claude=False)
        step = min(i for (fmt, _), i in self.entry_ids(clean).items() if fmt == "codex-toml")   # creates the file
        # (a) created right before our link(): EEXIST -> conflict, their file untouched, our temp removed
        foreign_env = {"SCAI_TEST_TOUCH": str(step)}
        result = self.run_install("--mcp", home=clean, env=foreign_env)
        self.assertEqual(2, result.returncode, result.stdout)
        self.assertEqual(b"# created by someone else\n", (clean / ".codex/config.toml").read_bytes())
        self.assertEqual([], self.leftovers(clean))
        # (b) killed after prepare, then created by someone else -> resume: conflict (row 10), theirs untouched
        clean3 = self.make_home(self.root / "clean3", codex=False, claude=False)
        step3 = min(i for (fmt, _), i in self.entry_ids(clean3).items() if fmt == "codex-toml")
        self.assertEqual(99, self.run_install("--mcp", home=clean3, env={"SCAI_FAULT": f"{step3}:entry-after-prepare"}).returncode)
        write(clean3 / ".codex/config.toml", "# theirs\n")
        self.assertEqual(2, self.run_install("--resume", home=clean3).returncode)
        self.assertEqual("# theirs\n", (clean3 / ".codex/config.toml").read_text())
        self.assertEqual([], self.leftovers(clean3))


if __name__ == "__main__":
    unittest.main()
