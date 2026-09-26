"""install_preflight: paid behavior runs must exercise this checkout's skills and roles."""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("run_behavior_tests_preflight", REPO / "scripts" / "run_behavior_tests.py")
runner = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = runner
_spec.loader.exec_module(runner)


def fixture(platforms=("claude", "codex"), skills=("alpha-skill",), role=None):
    return runner.Fixture(
        fixture_id="f", source=Path("f.json"), platforms=tuple(platforms), lang="en", prompt="p", repeats=1,
        pass_threshold=1, timeout_s=60, agent_role=role, workspace_change_policy=None, route_label=None,
        expected_skills=tuple(skills), discovery_skills=tuple(skills), prohibited_skills=(),
        evidence_required=(), must=(), must_not=(),
    )


class InstallPreflightTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        t = Path(self._tmp.name)
        self.repo = t / "repo"
        self.home = t / "home"
        self.other = t / "other-checkout"
        self.skill = self.repo / "skills" / "cat" / "alpha-skill"
        self.skill.mkdir(parents=True)
        (self.repo / "skills" / "manifest.json").write_text(
            json.dumps({"schema_version": 2, "skills": {"alpha-skill": {"category": "cat"}}}))
        self.role = self.repo / "agents" / "claude" / "researcher.md"
        self.role.parent.mkdir(parents=True)
        self.role.write_text("role\n")
        (self.other / "alpha-skill").mkdir(parents=True)
        self.env = {"HOME": str(self.home)}

    def tearDown(self):
        self._tmp.cleanup()

    def link(self, rel, target):
        path = self.home / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(target)

    def install_ok(self):
        self.link(".claude/skills/alpha-skill", self.skill)
        self.link(".agents/skills/alpha-skill", self.skill)
        self.link(".claude/agents/researcher.md", self.role)

    def problems(self, fixtures=None, platforms=("claude", "codex")):
        return runner.install_preflight(self.repo, fixtures or [fixture(role="researcher")], platforms, self.env)

    def test_matching_install_passes(self):
        self.install_ok()
        self.assertEqual([], self.problems())

    def test_missing_install_is_reported(self):
        joined = "\n".join(self.problems())
        self.assertIn("claude skill alpha-skill: not installed", joined)
        self.assertIn("codex skill alpha-skill: not installed", joined)
        self.assertIn("claude role researcher: not installed", joined)

    def test_link_to_other_checkout_is_reported(self):
        self.link(".claude/skills/alpha-skill", self.other / "alpha-skill")
        self.link(".agents/skills/alpha-skill", self.skill)
        self.link(".claude/agents/researcher.md", self.role)
        problems = self.problems()
        self.assertEqual(1, len(problems), problems)
        self.assertIn("claude skill alpha-skill:", problems[0])
        self.assertIn("expected", problems[0])

    def test_stale_legacy_codex_copy_is_reported(self):
        self.install_ok()
        self.link(".codex/skills/alpha-skill", self.other / "alpha-skill")
        self.assertIn("legacy ~/.codex/skills", "\n".join(self.problems()))

    def test_broken_link_and_project_shadow_are_reported(self):
        self.install_ok()
        os.unlink(self.home / ".agents/skills/alpha-skill")
        (self.home / ".agents/skills/alpha-skill").symlink_to(self.home / "missing")
        shadow = self.repo / ".claude" / "skills"
        shadow.mkdir(parents=True)
        (shadow / "alpha-skill").symlink_to(self.other / "alpha-skill")
        joined = "\n".join(self.problems())
        self.assertIn("codex skill alpha-skill: broken link", joined)
        self.assertIn("(project shadow)", joined)

    def test_skill_not_in_manifest_is_reported(self):
        self.install_ok()
        joined = "\n".join(self.problems([fixture(skills=("ghost-skill",))]))
        self.assertIn("not in skills/manifest.json", joined)

    def test_only_selected_platforms_are_checked(self):
        self.link(".claude/skills/alpha-skill", self.skill)
        self.assertEqual([], self.problems([fixture(platforms=("claude",))], platforms=("claude",)))

    def test_claude_config_dir_and_codex_home_are_respected(self):
        alt = self.home / "alt-claude"
        (alt / "skills").mkdir(parents=True)
        (alt / "skills" / "alpha-skill").symlink_to(self.skill)
        self.env["CLAUDE_CONFIG_DIR"] = str(alt)
        self.assertEqual([], self.problems([fixture(platforms=("claude",))], platforms=("claude",)))

    def test_run_aborts_before_any_cli_call_on_mismatch(self):
        fixtures_dir = self.repo / "tests" / "behavior" / "fixtures"
        fixtures_dir.mkdir(parents=True)
        for name in ("ai-research-p1.json", "ai-research-n1.json"):  # smoke profile needs p1+n1
            (fixtures_dir / name).write_text((REPO / "tests" / "behavior" / "fixtures" / name).read_text())
        (self.repo / "skills" / "manifest.json").write_text(
            json.dumps({"schema_version": 2, "skills": {"ai-research": {"category": "cat"}}}))
        args = runner.build_parser().parse_args(
            ["--repo", str(self.repo), "--fixtures", str(fixtures_dir), "--platform", "claude",
             "--claude-bin", "/definitely/not/claude", "--max-runs", "1"])
        with mock.patch.dict(os.environ, self.env), \
                mock.patch.object(runner, "cli_version", side_effect=AssertionError("CLI must not be called")):
            with self.assertRaises(runner.HarnessError) as ctx:
                runner.run(args)
        self.assertIn("do not match this checkout", str(ctx.exception))

    def test_dry_run_reports_preflight_without_failing(self):
        fixtures_dir = self.repo / "tests" / "behavior" / "fixtures"
        fixtures_dir.mkdir(parents=True)
        for name in ("ai-research-p1.json", "ai-research-n1.json"):  # smoke profile needs p1+n1
            (fixtures_dir / name).write_text((REPO / "tests" / "behavior" / "fixtures" / name).read_text())
        args = runner.build_parser().parse_args(
            ["--repo", str(self.repo), "--fixtures", str(fixtures_dir), "--platform", "claude", "--dry-run"])
        with mock.patch.dict(os.environ, self.env):
            code, payload, _ = runner.run(args)
        self.assertEqual(0, code)
        self.assertEqual("mismatch", payload["install_preflight"]["status"])


if __name__ == "__main__":
    unittest.main()
