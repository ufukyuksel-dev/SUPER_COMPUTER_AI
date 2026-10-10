"""Tests for scripts/export_plugin.py (private-content stripping and pre-export safety checks)."""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EXPORTER = REPO / "scripts" / "export_plugin.py"


def load_exporter():
    spec = importlib.util.spec_from_file_location("scai_export_plugin", EXPORTER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


exporter = load_exporter()


class ExportPluginTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "repo"
        (self.root / "scripts").mkdir(parents=True)
        shutil.copy2(REPO / "scripts" / "validate.py", self.root / "scripts" / "validate.py")
        self.out = self.tmp / "plugin"
        self.manifest = {"schema_version": 2, "skills": {}}

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def add_skill(self, name, body, files=None, status="active"):
        folder = self.root / "skills" / "mobile" / name
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text(body, encoding="utf-8")
        for rel, text in (files or {}).items():
            (folder / rel).parent.mkdir(parents=True, exist_ok=True)
            (folder / rel).write_text(text, encoding="utf-8")
        self.manifest["skills"][name] = {"category": "mobile", "status": status}
        (self.root / "skills" / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def run_export(self, names, deny=()):
        return exporter.run(self.root, self.out, list(names), list(deny))

    def test_strips_private_blocks_and_files(self):
        self.add_skill("demo", "# Demo\nPublic.\n<!-- private:start -->\nSee [ref](references/acme.md).\n"
                               "<!-- private:end -->\nEnd.\n",
                       {"references/acme.md": "<!-- private -->\nAcme ids\n", "references/public.md": "ok\n"})
        self.assertEqual(self.run_export(["demo"], deny=["acme"]), [])
        exported = self.out / "skills" / "demo"
        self.assertEqual((exported / "SKILL.md").read_text(), "# Demo\nPublic.\nEnd.\n")
        self.assertFalse((exported / "references" / "acme.md").exists())
        self.assertTrue((exported / "references" / "public.md").exists())

    def test_denied_word_aborts_and_leaves_output_unchanged(self):
        self.add_skill("demo", "# Demo\nAcme specific line.\n")
        findings = self.run_export(["demo"], deny=["acme"])
        self.assertEqual(findings, ["demo/SKILL.md:2: denied word"])
        self.assertFalse(self.out.exists())

    def test_link_to_unexported_file_is_a_finding(self):
        self.add_skill("demo", "# Demo\nRead [ref](references/acme.md).\n",
                       {"references/acme.md": "<!-- private -->\nx\n"})
        self.assertEqual(self.run_export(["demo"]), ["demo/SKILL.md:2: link to a file that was not exported"])

    def test_home_path_is_a_finding(self):
        self.add_skill("demo", "# Demo\nRun " + "/Us" + "ers/someone/app.\n")  # split: keep validate.py clean
        self.assertEqual(self.run_export(["demo"]), ["demo/SKILL.md:2: machine-specific absolute home path"])

    def test_unclosed_block_is_an_error(self):
        self.add_skill("demo", "# Demo\n<!-- private:start -->\nsecret\n")
        with self.assertRaises(exporter.ExportError):
            self.run_export(["demo"])

    def test_inactive_and_unknown_skills_are_errors(self):
        self.add_skill("old", "# Old\n", status="deprecated")
        with self.assertRaises(exporter.ExportError):
            self.run_export(["old"])
        with self.assertRaises(exporter.ExportError):
            self.run_export(["missing"])

    def test_replaces_previous_export_of_same_skill(self):
        self.add_skill("demo", "# Demo\n")
        stale = self.out / "skills" / "demo" / "stale.md"
        stale.parent.mkdir(parents=True)
        stale.write_text("old\n")
        self.assertEqual(self.run_export(["demo"]), [])
        self.assertFalse(stale.exists())


if __name__ == "__main__":
    unittest.main()
