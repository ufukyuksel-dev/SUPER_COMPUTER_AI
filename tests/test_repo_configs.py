"""Repository configuration files parse and agree with the manifests."""
import importlib.util
import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HAS_YAML = importlib.util.find_spec("yaml") is not None
YAML_FILES = (".pre-commit-config.yaml", ".github/workflows/ci.yml", ".github/workflows/secret-scan.yml")


@unittest.skipUnless(HAS_YAML, "PyYAML required")
class RepoConfigTest(unittest.TestCase):
    def setUp(self):
        import yaml
        self.yaml = yaml
        self.manifest = json.loads((REPO / "skills/manifest.json").read_text(encoding="utf-8"))["skills"]
        self.roles = json.loads((REPO / "agents/manifest.json").read_text(encoding="utf-8"))["roles"]

    def test_yaml_files_parse(self):
        for rel in YAML_FILES:
            with self.subTest(file=rel):
                self.assertIsInstance(self.yaml.safe_load((REPO / rel).read_text(encoding="utf-8")), dict)

    def test_source_map_agrees_with_manifests(self):
        sources = json.loads((REPO / "scripts/migration/source_map.json").read_text(encoding="utf-8"))["sources"]
        mapped = set(sources["AI_Developer"]["skills"]["names"])
        for name, category in sources["AI_SKILLS"]["skills"]["names"].items():
            self.assertEqual(category, self.manifest[name]["category"], name)
            mapped.add(name)
        mapped |= set(sources["manual-copies"]["skills"]) | set(sources["GoogleAds"]["skills"])
        mapped |= set(sources.get("PremiereProMCP", {}).get("skills", {}))
        for name in sources["AI_Developer"]["skills"]["names"]:
            self.assertEqual("ai-engineering", self.manifest[name]["category"], name)
        self.assertEqual(set(self.manifest), mapped, "every manifest skill has a recorded origin")
        self.assertEqual(set(self.roles), set(sources["AI_Developer"]["roles"]["names"]))


if __name__ == "__main__":
    unittest.main()
