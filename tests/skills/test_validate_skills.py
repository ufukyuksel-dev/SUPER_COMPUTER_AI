"""Tests for scripts/skills/validate_skills.py (manifest v2, category layout, strict/basic profiles).

Fixture repositories are built in temporary directories. Most fixture runs use --layer0 skip to isolate Layer 1;
the Layer 0 tests run the vendored skill-creator explicitly, and test_real_repository_is_valid runs the real tree
with the default (require).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VALIDATOR = REPO / "scripts" / "skills" / "validate_skills.py"
HAS_YAML = importlib.util.find_spec("yaml") is not None

STRICT_DESCRIPTION = "Use when validating a sample concern. Do NOT use for an adjacent concern."
BASIC_DESCRIPTION = "Handle a sample workflow for tests."


def load_validator():
    spec = importlib.util.spec_from_file_location("scai_validate_skills", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def openai_yaml(name: str, description: str) -> str:
    digest = hashlib.sha256(description.encode("utf-8")).hexdigest()
    return (
        f"# skill-description-sha256: {digest}\n"
        "interface:\n"
        '  display_name: "Sample Skill"\n'
        '  short_description: "Validate a deterministic sample skill"\n'
        f'  default_prompt: "Use ${name} for validation."\n'
    )


class Fixture:
    """A minimal valid repository: one strict skill, one basic skill, one role."""

    def __init__(self, root: Path):
        self.root = root
        self.skills = {
            "sample-skill": {"category": "ai-engineering", "status": "active", "profile": "strict",
                             "platforms": ["claude", "codex"], "bundles": ["ai-engineering"]},
            "basic-skill": {"category": "media", "status": "active", "profile": "basic",
                            "platforms": ["claude"], "bundles": ["media"]},
        }
        self.roles = {"researcher": {"platforms": ["claude", "codex"], "bundles": ["ai-engineering"]}}
        self.write_skill("ai-engineering", "sample-skill", STRICT_DESCRIPTION,
                         "## Tool Requirements & Degradation\n\nNone.\n", with_openai=True)
        self.write_skill("media", "basic-skill", BASIC_DESCRIPTION, "Body.\n")
        self.write("instructions/global/30-ai-engineering-routing.md", "| `sample-skill` | sample |\n")
        self.write("agents/claude/researcher.md", "role\n")
        self.write("agents/codex/researcher.toml", "role = true\n")
        self.save()

    def write(self, rel: str, text: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def write_skill(self, category, name, description, body, with_openai=False, fm_name=None):
        base = f"skills/{category}/{name}"
        self.write(f"{base}/SKILL.md", f"---\nname: {fm_name or name}\ndescription: {description}\n---\n\n{body}")
        if with_openai:
            self.write(f"{base}/agents/openai.yaml", openai_yaml(name, description))

    def save(self):
        self.write("skills/manifest.json", json.dumps({"schema_version": 2, "skills": self.skills}, indent=2))
        self.write("agents/manifest.json", json.dumps({"schema_version": 1, "roles": self.roles}, indent=2))

    def run(self):
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--repo", str(self.root), "--layer0", "skip"],
            text=True, capture_output=True, check=False,
        )


@unittest.skipUnless(HAS_YAML, "install requirements-dev.txt (PyYAML) to run skill validator tests")
class ValidateSkillsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="scai-skills-")
        self.fx = Fixture(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def assertFails(self, expected: str):
        result = self.fx.run()
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn(expected, result.stdout)

    def test_valid_fixture_passes(self):
        result = self.fx.run()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual("OK\n", result.stdout)

    def test_real_repository_is_valid(self):
        result = subprocess.run([sys.executable, str(VALIDATOR)], text=True, capture_output=True, check=False)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    # --- ported legacy failure cases (strict profile) ---

    def test_missing_closing_delimiter(self):
        self.fx.write("skills/ai-engineering/sample-skill/SKILL.md", "---\nname: sample-skill\n")
        self.assertFails("missing closing frontmatter delimiter ---")

    def test_name_directory_mismatch(self):
        self.fx.write_skill("ai-engineering", "sample-skill", STRICT_DESCRIPTION,
                            "## Tool Requirements & Degradation\n", with_openai=True, fm_name="different-skill")
        self.assertFails("name 'different-skill' does not match directory 'sample-skill'")

    def test_strict_missing_use_when(self):
        desc = "Validate things. Do NOT use for other things."
        self.fx.write_skill("ai-engineering", "sample-skill", desc,
                            "## Tool Requirements & Degradation\n", with_openai=True)
        self.assertFails("description must contain 'Use when'")

    def test_unknown_cross_reference(self):
        self.fx.write_skill("ai-engineering", "sample-skill", STRICT_DESCRIPTION,
                            "## Tool Requirements & Degradation\n\nsee skill missing-skill\n", with_openai=True)
        self.assertFails("cross-reference does not resolve: see skill missing-skill")

    def test_planned_reference_without_fallback(self):
        self.fx.skills["future-skill"] = {"category": "ai-engineering", "status": "planned", "profile": "strict",
                                          "platforms": ["codex"], "bundles": ["ai-engineering"]}
        self.fx.save()
        self.fx.write_skill("ai-engineering", "sample-skill", STRICT_DESCRIPTION,
                            "## Tool Requirements & Degradation\n\nDelegate: see skill future-skill.\n",
                            with_openai=True)
        self.assertFails("planned reference requires 'when available, else': see skill future-skill")

    def test_strict_missing_openai_yaml(self):
        (self.fx.root / "skills/ai-engineering/sample-skill/agents/openai.yaml").unlink()
        self.assertFails("missing agents/openai.yaml")

    def test_stale_openai_yaml(self):
        self.fx.write("skills/ai-engineering/sample-skill/agents/openai.yaml",
                      openai_yaml("sample-skill", "an older description"))
        self.assertFails("openai.yaml stale — regenerate")

    def test_strict_skill_needs_routing_row(self):
        self.fx.write("instructions/global/30-ai-engineering-routing.md", "no rows\n")
        self.assertFails("missing routing row for strict skill sample-skill")

    # --- basic profile ---

    def test_basic_profile_does_not_require_strict_contract(self):
        # no 'Use when', no heading, no openai.yaml, mentions another skill name freely
        self.fx.write_skill("media", "basic-skill", BASIC_DESCRIPTION, "Works with sample-skill output.\n")
        self.assertEqual(0, self.fx.run().returncode)

    def test_basic_profile_still_resolves_see_skill(self):
        self.fx.write_skill("media", "basic-skill", BASIC_DESCRIPTION, "see skill nowhere-skill\n")
        self.assertFails("cross-reference does not resolve: see skill nowhere-skill")

    def test_basic_profile_validates_openai_yaml_when_present(self):
        self.fx.write("skills/media/basic-skill/agents/openai.yaml", openai_yaml("basic-skill", "stale"))
        self.assertFails("openai.yaml stale — regenerate")

    # --- manifest / layout ---

    def test_active_skill_missing_from_disk(self):
        self.fx.skills["ghost-skill"] = dict(self.fx.skills["basic-skill"])
        self.fx.save()
        self.assertFails("active skill is missing from disk")

    def test_disk_skill_not_in_manifest(self):
        self.fx.write_skill("media", "orphan-skill", BASIC_DESCRIPTION, "Body.\n")
        self.assertFails("on-disk skill is not active in manifest")

    def test_category_mismatch(self):
        self.fx.skills["basic-skill"]["category"] = "browser"
        self.fx.save()
        result = self.fx.run()
        self.assertEqual(1, result.returncode)
        self.assertIn("active skill is missing from disk", result.stdout)
        self.assertIn("is in category 'media' but manifest says 'browser'", result.stdout)

    def test_same_name_in_two_categories(self):
        self.fx.write_skill("browser", "basic-skill", BASIC_DESCRIPTION, "Body.\n")
        self.assertFails("skill name 'basic-skill' is used in more than one category")

    def test_planned_skill_must_not_exist_on_disk(self):
        self.fx.skills["basic-skill"]["status"] = "planned"
        self.fx.save()
        self.assertFails("planned skill must not exist on disk")

    def test_manifest_schema_errors(self):
        cases = {
            "platforms": (["claude", "vim"], "platforms must be a non-empty unique subset"),
            "bundles": ([], "bundles must be a non-empty unique list"),
            "profile": ("loose", "profile must be one of strict, basic"),
            "status": ("draft", "status must be one of active, planned"),
        }
        for field, (value, message) in cases.items():
            with self.subTest(field=field):
                original = self.fx.skills["basic-skill"][field]
                self.fx.skills["basic-skill"][field] = value
                self.fx.save()
                self.assertFails(message)
                self.fx.skills["basic-skill"][field] = original
                self.fx.save()

    def test_manifest_duplicate_keys_rejected(self):
        text = json.dumps({"schema_version": 2, "skills": self.fx.skills})
        dup = text.replace('"skills": {', '"skills": {"basic-skill": {}, ', 1)
        self.fx.write("skills/manifest.json", dup)
        self.assertFails("duplicate key: basic-skill")

    def test_wrong_schema_version(self):
        self.fx.write("skills/manifest.json", json.dumps({"schema_version": 1, "skills": {}}))
        self.assertFails("must contain exactly schema_version (2) and skills")

    # --- roles ---

    def test_declared_role_file_missing(self):
        (self.fx.root / "agents/codex/researcher.toml").unlink()
        self.assertFails("declared role file is missing")

    def test_undeclared_role_file(self):
        self.fx.write("agents/claude/extra.md", "role\n")
        self.assertFails("role file is not declared for claude")

    # --- strict category / local links ---

    def test_ai_engineering_category_cannot_downgrade_to_basic(self):
        self.fx.skills["sample-skill"]["profile"] = "basic"
        self.fx.save()
        (self.fx.root / "skills/ai-engineering/sample-skill/agents/openai.yaml").unlink()
        result = self.fx.run()
        self.assertEqual(1, result.returncode)
        self.assertIn("skills.sample-skill.profile must be strict for category 'ai-engineering'", result.stdout)
        self.assertIn("missing agents/openai.yaml", result.stdout)  # still validated as strict
        self.assertEqual(2, result.stdout.count("FAIL "), result.stdout)

    def test_missing_local_link_target(self):
        self.fx.write_skill("media", "basic-skill", BASIC_DESCRIPTION,
                            "Read [the probe](references/nonexistent-review-probe.md).\n")
        self.assertFails("SKILL.md: line 6: link target does not exist: references/nonexistent-review-probe.md")

    def test_missing_link_in_reference_file(self):
        self.fx.write("skills/media/basic-skill/references/a.md", "See [b](b.md#part).\n")
        self.assertFails("link target does not exist: b.md#part")

    def test_link_leaving_skill_or_absolute_is_rejected(self):
        self.fx.write("skills/media/other.md", "x\n")
        self.fx.write_skill("media", "basic-skill", BASIC_DESCRIPTION, "[a](../other.md) [b](/etc/hosts) [c](~/x.md)\n")
        result = self.fx.run()
        self.assertEqual(1, result.returncode)
        self.assertIn("link leaves the skill directory: ../other.md", result.stdout)
        self.assertIn("link must be relative to the skill: /etc/hosts", result.stdout)
        self.assertIn("link must be relative to the skill: ~/x.md", result.stdout)

    def test_valid_links_urls_anchors_code_spans_and_fences_pass(self):
        self.fx.write("skills/media/basic-skill/references/ok.md", "fine\n")
        body = ("[ok](references/ok.md#top) [web](https://example.com/x) [anchor](#section) "
                "[mail](mailto:a@example.invalid) `[Title](URL)`\n```\n[fenced](nope.md)\n```\n![img](missing.png)\n")
        self.fx.write_skill("media", "basic-skill", BASIC_DESCRIPTION, body)
        result = self.fx.run()
        self.assertEqual(0, result.returncode, result.stdout)

    # --- Layer 0 ---

    def run_layer0(self, mode, env_extra, validator=VALIDATOR):
        env = {"PATH": "/usr/bin:/bin", "CODEX_HOME": "/definitely/not/codex-home", **env_extra}
        cmd = [sys.executable, str(validator), "--repo", str(self.fx.root)]
        if mode:
            cmd += ["--layer0", mode]
        return subprocess.run(cmd, text=True, capture_output=True, check=False, env=env)

    def test_layer0_default_is_require_and_uses_vendored_creator(self):
        result = self.run_layer0(None, {})
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertNotIn("NOTICE", result.stderr)

    def test_layer0_invalid_configured_creator_fails_explicitly(self):
        for mode in ("require", "auto"):
            with self.subTest(mode=mode):
                result = self.run_layer0(mode, {"SKILL_CREATOR_HOME": "/definitely/not/a/skill-creator"})
                self.assertEqual(1, result.returncode)
                self.assertEqual("FAIL: SKILL_CREATOR_HOME not found\n", result.stdout)

    def test_layer0_runs_quick_validate(self):
        self.fx.write_skill("media", "basic-skill", "[TODO: describe]", "Body.\n")
        result = self.run_layer0("require", {})
        self.assertEqual(1, result.returncode)
        self.assertIn("quick_validate.py:", result.stdout)

    def copy_validator_tree(self, root: Path) -> Path:
        import shutil
        shutil.copytree(REPO / "third_party" / "openai-skill-creator", root / "third_party" / "openai-skill-creator")
        (root / "scripts" / "skills").mkdir(parents=True)
        shutil.copy(VALIDATOR, root / "scripts" / "skills" / "validate_skills.py")
        return root / "scripts" / "skills" / "validate_skills.py"

    def test_layer0_tampered_vendored_copy_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            validator = self.copy_validator_tree(Path(raw))
            target = Path(raw) / "third_party/openai-skill-creator/scripts/quick_validate.py"
            target.write_text(target.read_text() + "\n# tampered\n")
            result = self.run_layer0("require", {}, validator)
            self.assertEqual(1, result.returncode)
            self.assertIn("vendored skill-creator file does not match SHA256SUMS: scripts/quick_validate.py", result.stdout)

    def test_layer0_auto_without_any_creator_passes_with_notice(self):
        with tempfile.TemporaryDirectory() as raw:
            validator = self.copy_validator_tree(Path(raw))
            import shutil
            shutil.rmtree(Path(raw) / "third_party")
            result = self.run_layer0("auto", {}, validator)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("NOTICE: Layer 0", result.stderr)
            self.assertEqual(1, self.run_layer0("require", {}, validator).returncode)


class DocumentContractTest(unittest.TestCase):
    def test_known_skill_reference_requires_literal_see_skill_form(self):
        validator = load_validator()
        repo = Path("/validation-fixture")
        document = validator.SkillDocument(
            path=repo / "skills" / "ai-engineering" / "sample-skill" / "SKILL.md",
            name="sample-skill",
            description=STRICT_DESCRIPTION,
            body="## Tool Requirements & Degradation\n\nDelegate the adjacent concern to skill future-skill.\n",
        )
        errors = []
        validator.validate_document(document, "sample-skill", {"sample-skill", "future-skill"}, set(), repo, errors)
        self.assertIn("cross-reference must use 'see skill future-skill'", "\n".join(errors))


    @unittest.skipUnless(HAS_YAML, "PyYAML required")
    def test_openai_schema_rejects_unquoted_unknown_and_invalid_optional_fields(self):
        import yaml

        validator = load_validator()
        with tempfile.TemporaryDirectory(prefix="metadata-schema-") as raw:
            repo = Path(raw)
            skill_dir = repo / "skills" / "ai-engineering" / "sample-skill"
            (skill_dir / "agents").mkdir(parents=True)
            document = validator.SkillDocument(skill_dir / "SKILL.md", "sample-skill", STRICT_DESCRIPTION,
                                               "## Tool Requirements & Degradation\n")
            digest = hashlib.sha256(STRICT_DESCRIPTION.encode("utf-8")).hexdigest()
            (skill_dir / "agents" / "openai.yaml").write_text(
                f"""# skill-description-sha256: {digest}
interface:
  display_name: Sample Skill
  short_description: "Validate a deterministic sample skill"
  default_prompt: "Use $sample-skill for validation."
  brand_color: "blue"
  icon_small: "./assets/missing.png"
  unexpected: "value"
""", encoding="utf-8")
            errors = []
            validator.validate_openai_yaml(skill_dir, document, "sample-skill", repo, yaml, errors)
            joined = "\n".join(errors)
            self.assertIn("YAML string value must be quoted", joined)
            self.assertIn("interface has unknown keys: unexpected", joined)
            self.assertIn("brand_color must be a six-digit hex color", joined)
            self.assertIn("icon_small asset does not exist", joined)

if __name__ == "__main__":
    unittest.main()
