"""scripts/new_skill.py (all-or-nothing scaffolding) and scripts/migrate_manual_skills.py (read-only report)."""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HAS_YAML = importlib.util.find_spec("yaml") is not None


def tree_digest(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "dir"
            for p in sorted(root.rglob("*"))}


@unittest.skipUnless(HAS_YAML, "PyYAML required (validator)")
class NewSkillTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="scai-newskill-")
        self.repo = Path(self._tmp.name) / "repo"
        for part in ("scripts", "skills", "agents", "instructions", "third_party"):
            shutil.copytree(REPO / part, self.repo / part)

    def tearDown(self):
        self._tmp.cleanup()

    def run_script(self, *args):
        return subprocess.run([sys.executable, str(self.repo / "scripts" / "new_skill.py"), *args],
                              text=True, capture_output=True, check=False)

    def validate(self):
        return subprocess.run([sys.executable, str(self.repo / "scripts" / "skills" / "validate_skills.py")],
                              text=True, capture_output=True, check=False)

    def test_basic_skill_scaffold_validates(self):
        result = self.run_script("video-subtitles", "--category", "media", "--description",
                                 "Create and align subtitles for videos. Use when subtitles are requested.")
        self.assertEqual(0, result.returncode, result.stdout)
        entry = json.loads((self.repo / "skills/manifest.json").read_text())["skills"]["video-subtitles"]
        self.assertEqual({"category": "media", "status": "active", "profile": "basic",
                          "platforms": ["claude", "codex"], "bundles": ["media"]}, entry)
        check = self.validate()
        self.assertEqual(0, check.returncode, check.stdout + check.stderr)

    def test_strict_skill_scaffold_validates_after_routing_row(self):
        result = self.run_script("vector-db-ops", "--category", "ai-engineering", "--display-name", "Vector DB Ops",
                                 "--short-description", "Operate vector databases in production",
                                 "--default-prompt", "Use $vector-db-ops to plan vector database operations.")
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn("| `vector-db-ops` |", result.stdout)
        self.assertTrue((self.repo / "skills/ai-engineering/vector-db-ops/agents/openai.yaml").is_file())
        self.assertIn("missing routing row for strict skill vector-db-ops", self.validate().stdout)
        routing = self.repo / "instructions/global/30-ai-engineering-routing.md"
        routing.write_text(routing.read_text() + "| `vector-db-ops` | vector database operations |\n")
        check = self.validate()
        self.assertEqual(0, check.returncode, check.stdout + check.stderr)

    def test_failure_rolls_back_everything(self):
        before = tree_digest(self.repo / "skills")
        bad = Path(self._tmp.name) / "bad.json"
        bad.write_text("{not json")
        result = self.run_script("broken-skill", "--category", "brand-new", "--profile", "basic",
                                 "--description", "x", "--display-name", "Broken Skill",
                                 "--short-description", "A broken metadata scaffold here",
                                 "--default-prompt", "Use $broken-skill.", "--mcp-tools-json", str(bad))
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertEqual(before, tree_digest(self.repo / "skills"))

    def test_rejections_write_nothing(self):
        before = tree_digest(self.repo / "skills")
        cases = [
            ("ai-research", "--category", "media", "--description", "dup"),                 # existing name
            ("Bad_Name", "--category", "media", "--description", "x"),                      # invalid name
            ("x-skill", "--category", "ai-engineering", "--profile", "basic", "--description", "x"),  # strict category
            ("y-skill", "--category", "media"),                                             # basic without description
        ]
        for args in cases:
            with self.subTest(args=args):
                self.assertEqual(1, self.run_script(*args).returncode)
        self.assertEqual(before, tree_digest(self.repo / "skills"))


class ManualReportTest(unittest.TestCase):
    def test_report_is_read_only_and_shows_differences(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            copy = home / ".claude/skills/Mobile_UI_Review"
            copy.mkdir(parents=True)
            (copy / "SKILL.md").write_text("---\nname: Mobile_UI_Review\n---\nold body\n")
            (copy / "notes.txt").write_text("extra\n")
            os.symlink(REPO / "skills/browser/jev-browser", home / ".claude/skills/jev-browser") \
                if (home / ".claude/skills").exists() else None
            before = tree_digest(home)
            result = subprocess.run([sys.executable, str(REPO / "scripts/migrate_manual_skills.py"), "--home", raw],
                                    text=True, capture_output=True, check=False)
            self.assertEqual(0, result.returncode)
            self.assertIn("mobile-ui-review <- ~/.claude/skills/Mobile_UI_Review: hand-copied directory present", result.stdout)
            self.assertIn("only in copy:    notes.txt", result.stdout)
            self.assertIn("differs:         SKILL.md", result.stdout)
            self.assertIn("jev-browser <- ~/.claude/skills/jev-browser: already a link", result.stdout)
            self.assertIn("~/.codex/skills/Mobile_UI_Review: not present", result.stdout)
            self.assertEqual(before, tree_digest(home))


if __name__ == "__main__":
    unittest.main()
