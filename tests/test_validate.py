"""Tests for scripts/validate.py. Run: python3 -m unittest discover -s tests -q"""
import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("validate", REPO / "scripts" / "validate.py")
validate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate)

# Fake values are built at runtime so this file does not trip the scanners.
FAKE_GITHUB = "ghp_" + "A" * 36
FAKE_AWS = "AKIA" + "B" * 16
FAKE_KEY_HEADER = "-----BEGIN " + "PRIVATE KEY-----"
FAKE_HOME = "/" + "Users" + "/someone/project"
FAKE_UNICODE_HOME = "/" + "home" + "/\u00fcmit/work"


class ValidateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        for name in validate.REQUIRED_ROOT_FILES:
            (self.root / name).write_text("ok\n")

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def rules(self, staged=False):
        return [f.rule for f in validate.validate(self.root, staged=staged)]

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)

    def test_clean_repo_has_no_findings(self):
        self.write("docs/a.md", "Paths like /Users/... are placeholders.\n")
        self.assertEqual(self.rules(), [])

    def test_missing_required_file(self):
        (self.root / "LICENSE").unlink()
        self.assertIn("missing required root file", self.rules())

    def test_env_file_is_forbidden_but_example_allowed(self):
        self.write(".env.example", "API_KEY=\n")
        self.assertEqual(self.rules(), [])
        self.write("mcp/servers/x/.env", "API_KEY=value\n")
        self.write("mcp/servers/x/.env.local", "API_KEY=value\n")
        forbidden = [f for f in validate.validate(self.root) if f.rule.startswith("forbidden file")]
        self.assertEqual(sorted(f.path for f in forbidden), ["mcp/servers/x/.env", "mcp/servers/x/.env.local"])

    def test_gitignored_files_are_skipped(self):
        self.write(".gitignore", ".env\n")
        self.write(".env", "TOKEN=" + FAKE_GITHUB + "\n")
        self.assertEqual(self.rules(), [])

    def test_absolute_home_path_detected(self):
        self.write("skills/s/SKILL.md", "Code: " + FAKE_HOME + "\n")
        findings = validate.validate(self.root)
        self.assertEqual([(f.path, f.line, f.rule) for f in findings],
                         [("skills/s/SKILL.md", 1, "machine-specific absolute home path")])

    def test_secret_patterns_detected_and_not_printed(self):
        self.write("a.txt", "x\n" + FAKE_GITHUB + "\n" + FAKE_AWS + "\n" + FAKE_KEY_HEADER + "\n")
        findings = validate.validate(self.root)
        self.assertEqual(sorted(f.rule for f in findings),
                         ["possible secret (aws-access-key)", "possible secret (github-token)",
                          "possible secret (private-key)"])
        for f in findings:
            self.assertNotIn(FAKE_GITHUB, str(f))
            self.assertNotIn(FAKE_AWS, str(f))

    def test_binary_files_are_skipped(self):
        (self.root / "img.bin").write_bytes(b"\0\1" + FAKE_GITHUB.encode())
        self.assertEqual(self.rules(), [])

    def test_unicode_home_path_detected(self):
        self.write("a.md", "see " + FAKE_UNICODE_HOME + "\n")
        self.assertEqual(self.rules(), ["machine-specific absolute home path"])

    def test_all_pem_and_key_containers_forbidden_by_policy(self):
        for name in ("certs/public-cert.pem", "a/b.p12", "a/c.key", "ssh/id_ed25519"):
            self.write(name, "x\n")
        forbidden = sorted(f.path for f in validate.validate(self.root) if f.rule.startswith("forbidden file"))
        self.assertEqual(forbidden, ["a/b.p12", "a/c.key", "certs/public-cert.pem", "ssh/id_ed25519"])

    # --- symlinks (target is inspected, never followed) ---

    def test_symlink_absolute_target_rejected(self):
        os.symlink(FAKE_HOME, self.root / "abs-link")
        self.assertEqual(self.rules(), ["symlink with absolute target"])

    def test_symlink_escaping_repo_rejected(self):
        (self.root / "skills").mkdir()
        os.symlink("../../outside", self.root / "skills" / "esc")
        self.assertEqual(self.rules(), ["symlink target escapes the repository"])

    def test_symlink_relative_inside_repo_allowed(self):
        self.write("skills/cat/real/SKILL.md", "ok\n")
        (self.root / "links").mkdir()
        os.symlink("../skills/cat/real", self.root / "links" / "real")
        self.assertEqual(self.rules(), [])

    def test_staged_symlink_target_checked_from_index(self):
        os.symlink(FAKE_HOME, self.root / "abs-link")
        self.git("add", "-A")
        self.assertIn("symlink with absolute target", self.rules(staged=True))

    # --- staged mode reads index blobs, not the working tree ---

    def test_staged_detects_content_cleaned_only_in_working_tree(self):
        self.write("a.md", "Code: " + FAKE_HOME + "\n")
        self.git("add", "-A")
        self.write("a.md", "clean\n")  # partial staging: index still has the path
        self.assertEqual(self.rules(staged=False), [])
        self.assertEqual(self.rules(staged=True), ["machine-specific absolute home path"])

    def test_staged_ignores_unstaged_dirty_working_tree(self):
        self.write("a.md", "clean\n")
        self.git("add", "-A")
        self.write("a.md", "Code: " + FAKE_HOME + "\n")
        self.assertEqual(self.rules(staged=True), [])
        self.assertEqual(self.rules(staged=False), ["machine-specific absolute home path"])

    def test_staged_required_files_come_from_index(self):
        self.git("add", "-A")
        self.git("rm", "--cached", "-q", "LICENSE")
        self.assertEqual(self.rules(staged=True), ["missing required root file"])

    # --- reviewed allowlist (.public-safety-allowlist.json) ---

    def allow(self, entries):
        import json
        self.write(".public-safety-allowlist.json", json.dumps({"schema_version": 1, "entries": entries}))

    def entry(self, path="t/test_x.py", match="/" + "Users" + "/het/", rule="home-path"):
        return {"path": path, "rule": rule, "match": match, "reason": "fixture for a path sanitizer"}

    def test_allowlisted_home_path_token_passes(self):
        self.write("t/test_x.py", "x = '" + "/" + "Users" + "/het/secret.prproj'\n")
        self.allow([self.entry()])
        self.assertEqual(self.rules(), [])

    def test_allowlist_matches_whole_user_component_only(self):
        for other in ("/" + "Users" + "/hetty/secret", "/" + "Users" + "/het2/x", "/" + "Users" + "/het.bak/x"):
            with self.subTest(other=other):
                self.write("t/test_x.py", "a = '" + "/" + "Users" + "/het/ok' ; b = '" + other + "'\n")
                self.allow([self.entry()])
                self.assertEqual(self.rules(), ["machine-specific absolute home path"])
        self.write("t/test_x.py", "a = '" + "/" + "Users" + "/het'\n")  # the bare prefix itself is allowed
        self.assertEqual(self.rules(), [])

    def test_other_token_on_same_line_still_fails(self):
        self.write("t/test_x.py", "a='" + "/" + "Users" + "/het/a' b='" + FAKE_HOME + "'\n")
        self.allow([self.entry()])
        self.assertEqual(self.rules(), ["machine-specific absolute home path"])

    def test_allowlist_is_per_file(self):
        self.write("other.py", "x = '" + "/" + "Users" + "/het/a'\n")
        self.write("t/test_x.py", "x = '" + "/" + "Users" + "/het/b'\n")
        self.allow([self.entry()])
        self.assertEqual(self.rules(), ["machine-specific absolute home path"])

    def test_stale_entry_is_a_finding(self):
        self.allow([self.entry()])
        findings = validate.validate(self.root)
        self.assertEqual(1, len(findings))
        self.assertIn("stale entry", findings[0].rule)

    def test_invalid_or_secret_rule_entries_are_rejected(self):
        self.write("t/test_x.py", "x = '" + "/" + "Users" + "/het/a'\n")
        self.allow([self.entry(rule="possible-secret"), self.entry(match="not-a-path")])
        rules = self.rules()
        self.assertEqual(2, sum("needs path, rule (home-path)" in r for r in rules))
        self.assertIn("machine-specific absolute home path", rules)

    def test_secrets_are_never_exempted(self):
        self.write("t/test_x.py", "x = '" + "/" + "Users" + "/het/a'\ntoken = '" + FAKE_GITHUB + "'\n")
        self.allow([self.entry()])
        self.assertEqual(self.rules(), ["possible secret (github-token)"])

    def test_staged_mode_uses_the_staged_allowlist(self):
        self.write("t/test_x.py", "x = '" + "/" + "Users" + "/het/a'\n")
        self.git("add", "-A")  # staged without allowlist
        self.allow([self.entry()])  # allowlist only in the working tree
        self.assertEqual(self.rules(staged=True), ["machine-specific absolute home path"])
        self.assertEqual(self.rules(staged=False), [])

    def test_main_exit_codes(self):
        self.assertEqual(validate.main(["--root", str(self.root)]), 0)
        self.write("a.txt", FAKE_AWS + "\n")
        self.assertEqual(validate.main(["--root", str(self.root)]), 1)
        self.git("add", "-A")
        self.assertEqual(validate.main(["--root", str(self.root), "--staged"]), 1)


if __name__ == "__main__":
    unittest.main()
