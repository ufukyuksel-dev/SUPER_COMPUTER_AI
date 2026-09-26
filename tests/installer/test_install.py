"""Acceptance tests for scripts/install.py (plan §4.4, §8.3 a–k, §16 bundle tests 1–5).

Every test builds a small fixture repository (a copy of install.py plus minimal manifests) and an isolated HOME,
so the real installation is never touched. Fault injection uses SCAI_TEST_MODE=1 + SCAI_FAULT=<point>.
"""
import fcntl
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INSTALLER = REPO / "scripts" / "install.py"
BEGIN = "<!-- super-computer-ai:managed:begin -->"
LEGACY_BEGIN = "<!-- ai-developer:managed:begin -->"
LEGACY_END = "<!-- ai-developer:managed:end -->"
AI_ORCH_TEXT = "# AI Orchestration — Claude Instructions\n\nForeign rules that must never change.\n\n"


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def build_repo(root: Path) -> Path:
    repo = root / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy(INSTALLER, repo / "scripts" / "install.py")
    shutil.copy(INSTALLER.with_name("scai_mcp.py"), repo / "scripts" / "scai_mcp.py")
    skills = {
        "alpha-skill": {"category": "cat-a", "status": "active", "profile": "basic",
                        "platforms": ["claude", "codex"], "bundles": ["one"]},
        "shared-skill": {"category": "cat-a", "status": "active", "profile": "basic",
                         "platforms": ["claude", "codex"], "bundles": ["one", "two"]},
        "beta-skill": {"category": "cat-b", "status": "active", "profile": "basic",
                       "platforms": ["claude"], "bundles": ["two"]},
    }
    write(repo / "skills" / "manifest.json", json.dumps({"schema_version": 2, "skills": skills}))
    for name, entry in skills.items():
        write(repo / "skills" / entry["category"] / name / "SKILL.md", f"---\nname: {name}\ndescription: x\n---\n")
    write(repo / "agents" / "manifest.json", json.dumps(
        {"schema_version": 1, "roles": {"researcher": {"platforms": ["claude", "codex"], "bundles": ["one"]}}}))
    write(repo / "agents" / "claude" / "researcher.md", "claude role\n")
    write(repo / "agents" / "codex" / "researcher.toml", "codex role\n")
    write(repo / "instructions" / "global" / "10-home.md", "## Home rule\n\nAlways here.\n")
    write(repo / "instructions" / "global" / "30-one.md", "<!-- bundles: one -->\n## Bundle one rule\n")
    write(repo / "scripts" / "migration" / "source_map.json", json.dumps({"schema_version": 1, "sources": {
        "AI_Developer": {"skills": {"from": ".agents/skills/{name}", "to": "x", "names": ["alpha-skill"]},
                         "roles": {"claude": {"from": ".claude/agents/{name}.md"},
                                   "codex": {"from": ".codex/agents/{name}.toml"}, "names": ["researcher"]}},
        "AI_SKILLS": {"skills": {"names": {"beta-skill": "cat-b", "shared-skill": "cat-a"}}},
        "manual-copies": {"skills": {
            "alpha-skill": {"to": "x", "source": "~/.claude/skills/alpha-skill"},
            "shared-skill": {"to": "x", "sources": ["~/.claude/skills/Shared_Copy", "~/.codex/skills/Shared_Copy"]},
        }},
        "GoogleAds": {"skills": {}},
    }}))
    return repo


def snapshot(home: Path) -> dict:
    """Managed-target view of HOME (the installer's private state directory excluded).

    The HOME path itself is replaced by <HOME> in link targets and file contents so snapshots of different
    scratch HOMEs are comparable.
    """
    result = {}
    state = home / ".local" / "state"
    markers = {str(home).encode(), os.path.realpath(home).encode()}
    for path in sorted(home.rglob("*")):
        if state in path.parents or path in (state, state.parent):
            continue  # the installer's audit state (and its .local parent) is outside the comparison
        rel = path.relative_to(home).as_posix()
        if path.is_symlink():
            target = os.readlink(path).encode()
            for marker in markers:
                target = target.replace(marker, b"<HOME>")
            result[rel] = ("link", target.decode())
        elif path.is_file():
            data = path.read_bytes()
            for marker in markers:
                data = data.replace(marker, b"<HOME>")
            result[rel] = ("file", hashlib.sha256(data).hexdigest(), oct(stat.S_IMODE(path.lstat().st_mode)))
        elif path.is_dir():
            result[rel] = ("dir",)
    return result


def inventory(repo: Path) -> dict:
    out = {}
    for path in sorted(repo.rglob("*")):
        rel = path.relative_to(repo).as_posix()
        st = path.lstat()
        if path.is_symlink():
            out[rel] = ("link", os.readlink(path), stat.S_IMODE(st.st_mode))
        elif path.is_file():
            out[rel] = ("file", hashlib.sha256(path.read_bytes()).hexdigest(), stat.S_IMODE(st.st_mode))
        else:
            out[rel] = ("dir", stat.S_IMODE(st.st_mode))
    return out


class InstallerTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="scai-install-")
        root = Path(self._tmp.name)
        self.repo = build_repo(root)
        self.home = root / "home"
        self.home.mkdir()
        self.legacy_repo = root / "AI_Developer"
        self.skills_repo = root / "AI_SKILLS"

    def tearDown(self):
        self._tmp.cleanup()

    def run_install(self, *args, fault=None, check=None):
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_CONFIG_DIR", "CODEX_HOME")}
        if fault:
            env.update({"SCAI_TEST_MODE": "1", "SCAI_FAULT": fault})
        result = subprocess.run([sys.executable, str(self.repo / "scripts" / "install.py"), "--home", str(self.home),
                                 *args], text=True, capture_output=True, env=env, check=False)
        if check is not None:
            self.assertEqual(check, result.returncode, result.stdout + result.stderr)
        return result

    def link_target(self, rel):
        return os.readlink(self.home / rel)

    def src(self, category, name):
        return str((self.repo / "skills" / category / name).resolve())

    def journals(self):
        d = self.home / ".local" / "state" / "super-computer-ai" / "journals"
        return sorted(d.glob("journal-*.json")) if d.is_dir() else []

    def seed_ai_orch(self):
        """Foreign content the installer must preserve (AI_ORCHESTRATION stand-in, plan §8.3 k)."""
        write(self.home / ".claude" / "CLAUDE.md", AI_ORCH_TEXT)
        write(self.home / ".codex" / "AGENTS.md", AI_ORCH_TEXT)
        foreign = self.home / "Projects" / "AI_ORCHESTRATION" / "skills" / "adding-an-mcp-tool"
        foreign.mkdir(parents=True)
        (self.home / ".claude" / "skills").mkdir(parents=True, exist_ok=True)
        os.symlink(foreign, self.home / ".claude" / "skills" / "adding-an-mcp-tool")

    def seed_legacy(self):
        """Fake AI_Developer + AI_SKILLS installations with their ownership records and managed block."""
        h = self.home
        (self.legacy_repo / ".agents" / "skills" / "alpha-skill").mkdir(parents=True, exist_ok=True)
        write(self.legacy_repo / ".claude" / "agents" / "researcher.md", "old\n")
        write(self.legacy_repo / ".codex" / "agents" / "researcher.toml", "old\n")
        links = {
            h / ".claude/skills/alpha-skill": self.legacy_repo / ".agents/skills/alpha-skill",
            h / ".agents/skills/alpha-skill": self.legacy_repo / ".agents/skills/alpha-skill",
            h / ".claude/agents/researcher.md": self.legacy_repo / ".claude/agents/researcher.md",
            h / ".codex/agents/researcher.toml": self.legacy_repo / ".codex/agents/researcher.toml",
        }
        for link, target in links.items():
            link.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(target, link)
        block = f"{LEGACY_BEGIN}\n## Global AI Engineering Skill System\n- old\n{LEGACY_END}\n"
        for rel in (".claude/CLAUDE.md", ".codex/AGENTS.md"):
            write(h / rel, AI_ORCH_TEXT + block + "\n## Trailing foreign section\n")
        write(h / ".agents" / "ai-developer-install.json", json.dumps({
            "schema_version": 1, "repo_root": str(self.legacy_repo),
            "links": [str(p) for p in links], "instruction_files": [str(h / ".claude/CLAUDE.md"),
                                                                     str(h / ".codex/AGENTS.md")]}))
        (self.skills_repo / "beta-skill").mkdir(parents=True, exist_ok=True)
        (self.skills_repo / "shared-skill").mkdir(parents=True, exist_ok=True)
        as_links = {
            h / ".claude/skills/beta-skill": self.skills_repo / "beta-skill",
            h / ".claude/skills/shared-skill": self.skills_repo / "shared-skill",
            h / ".codex/skills/shared-skill": self.skills_repo / "shared-skill",
        }
        for link, target in as_links.items():
            link.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(target, link)
        write(h / ".ai-skills-install.json", json.dumps({str(k): str(v) for k, v in as_links.items()}))


class FreshInstallTest(InstallerTestCase):
    def test_a_first_install_then_check_is_clean(self):
        self.run_install(check=0)
        self.assertEqual(self.src("cat-a", "alpha-skill"), self.link_target(".claude/skills/alpha-skill"))
        self.assertEqual(self.src("cat-a", "alpha-skill"), self.link_target(".agents/skills/alpha-skill"))
        self.assertEqual(self.src("cat-b", "beta-skill"), self.link_target(".claude/skills/beta-skill"))
        self.assertFalse((self.home / ".agents/skills/beta-skill").exists(), "beta-skill is claude-only")
        self.assertFalse((self.home / ".codex/skills").exists(), "legacy codex dir is opt-in")
        self.assertTrue(self.link_target(".claude/agents/researcher.md").endswith("agents/claude/researcher.md"))
        claude_md = (self.home / ".claude/CLAUDE.md").read_text()
        self.assertIn(BEGIN, claude_md)
        self.assertIn("## Home rule", claude_md)
        self.assertIn("## Bundle one rule", claude_md)
        self.run_install("--check", check=0)

    def test_b_second_install_changes_nothing(self):
        self.run_install(check=0)
        before, journals = snapshot(self.home), self.journals()
        result = self.run_install(check=0)
        self.assertIn("already up to date", result.stdout)
        self.assertEqual(before, snapshot(self.home))
        self.assertEqual(journals, self.journals())

    def test_state_permissions_are_private(self):
        self.run_install(check=0)
        state = self.home / ".local" / "state" / "super-computer-ai"
        for path in [state, *state.rglob("*")]:
            mode = stat.S_IMODE(path.lstat().st_mode)
            if path.is_dir():
                self.assertEqual(0o700, mode, path)
            else:
                self.assertEqual(0o600, mode, path)

    def test_i_checkout_is_never_modified(self):
        write(self.repo / "output" / "ignored-work.txt", "pipeline output\n")
        before = inventory(self.repo)
        self.run_install(check=0)
        self.run_install("--bundle", "two", check=0)
        self.run_install("--uninstall", check=0)
        self.assertEqual(before, inventory(self.repo))

    def test_foreign_file_at_target_is_conflict_with_zero_writes(self):
        write(self.home / ".claude/skills/alpha-skill", "user file\n")
        before = snapshot(self.home)
        result = self.run_install(check=2)
        self.assertIn("not owned by this installer", result.stdout)
        self.assertEqual(before, snapshot(self.home))
        self.assertEqual([], self.journals())

    def test_hand_edited_managed_block_is_conflict(self):
        self.run_install(check=0)
        path = self.home / ".claude/CLAUDE.md"
        path.write_text(path.read_text().replace("Always here.", "Edited by hand."))
        before = snapshot(self.home)
        result = self.run_install("--bundle", "two", check=2)
        self.assertIn("differs from the recorded version", result.stdout)
        self.assertEqual(before, snapshot(self.home))

    def test_check_reports_drift(self):
        self.run_install(check=0)
        os.unlink(self.home / ".claude/skills/alpha-skill")
        result = self.run_install("--check", check=1)
        self.assertIn("DRIFT", result.stdout)
        self.run_install(check=0)
        self.run_install("--check", check=0)

    def test_g_uninstall_removes_only_owned_items(self):
        self.seed_ai_orch()
        foreign_before = {k: v for k, v in snapshot(self.home).items()}
        self.run_install(check=0)
        write(self.home / ".claude/skills/user-skill/SKILL.md", "mine\n")
        self.run_install("--uninstall", check=0)
        after = snapshot(self.home)
        self.assertEqual(hashlib.sha256(b"mine\n").hexdigest(), after[".claude/skills/user-skill/SKILL.md"][1])
        del after[".claude/skills/user-skill/SKILL.md"]
        del after[".claude/skills/user-skill"]
        for rel in list(after):
            if rel not in foreign_before and after[rel][0] == "dir":
                del after[rel]  # parent directories created by the install may remain
        self.assertEqual(foreign_before, after)


class RedirectionAndModeTest(InstallerTestCase):
    def outside(self):
        target = Path(self._tmp.name) / "outside"
        target.mkdir(exist_ok=True)
        return target

    def test_symlinked_client_root_is_conflict_and_nothing_is_written_anywhere(self):
        outside = self.outside()
        os.symlink(outside, self.home / ".claude")
        before_home, before_out = snapshot(self.home), snapshot(outside)
        result = self.run_install(check=2)
        self.assertIn("is a symlink (redirected path", result.stdout)
        self.assertEqual(before_home, snapshot(self.home))
        self.assertEqual(before_out, snapshot(outside))
        self.assertFalse((self.home / ".local").exists())

    def test_symlinked_intermediate_directory_is_conflict(self):
        outside = self.outside()
        (self.home / ".claude").mkdir()
        os.symlink(outside, self.home / ".claude" / "skills")
        before_out = snapshot(outside)
        result = self.run_install(check=2)
        self.assertIn(".claude/skills is a symlink", result.stdout)
        self.assertEqual(before_out, snapshot(outside))

    def test_symlinked_state_directory_is_refused(self):
        outside = self.outside()
        os.symlink(outside, self.home / ".local")
        result = self.run_install(check=2)
        self.assertIn("redirected path", result.stdout)
        self.assertEqual({}, snapshot(outside))

    def test_explicitly_configured_client_root_is_allowed(self):
        configured = self.outside()
        alias = Path(self._tmp.name) / "claude-alias"
        os.symlink(configured, alias)
        env = {k: v for k, v in os.environ.items() if k != "CODEX_HOME"}
        env.update({"HOME": str(self.home), "CLAUDE_CONFIG_DIR": str(alias)})
        result = subprocess.run([sys.executable, str(self.repo / "scripts" / "install.py")], text=True,
                                capture_output=True, env=env, check=False)
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertTrue(os.path.lexists(configured / "skills" / "alpha-skill"))
        self.assertFalse((self.home / ".claude").exists())

    def test_file_modes_survive_install_and_rollback(self):
        for rel, mode in ((".claude/CLAUDE.md", 0o644), (".codex/AGENTS.md", 0o640)):
            path = write(self.home / rel, AI_ORCH_TEXT)
            os.chmod(path, mode)
        before = snapshot(self.home)
        self.run_install(check=0)
        self.assertEqual(0o644, stat.S_IMODE((self.home / ".claude/CLAUDE.md").stat().st_mode))
        self.assertEqual(0o640, stat.S_IMODE((self.home / ".codex/AGENTS.md").stat().st_mode))
        self.run_install("--rollback", self.journals()[-1].name, check=0)
        self.assertEqual(before, snapshot(self.home))

    def test_new_instruction_file_and_directories_get_standard_modes(self):
        self.run_install(check=0)
        self.assertEqual(0o644, stat.S_IMODE((self.home / ".claude/CLAUDE.md").stat().st_mode))
        self.assertEqual(0o755, stat.S_IMODE((self.home / ".claude/skills").stat().st_mode))

    def test_mode_change_after_install_is_detected_by_rollback(self):
        self.run_install(check=0)
        os.chmod(self.home / ".claude/CLAUDE.md", 0o600)
        result = self.run_install("--rollback", self.journals()[-1].name, check=2)
        self.assertIn("CLAUDE.md", result.stdout)


class LegacyAdoptionTest(InstallerTestCase):
    def test_c_adopts_legacy_installers_and_preserves_foreign_content(self):
        self.seed_legacy()
        self.seed_ai_orch_links_only()
        self.run_install(check=0)
        h = self.home
        self.assertEqual(self.src("cat-a", "alpha-skill"), self.link_target(".claude/skills/alpha-skill"))
        self.assertEqual(self.src("cat-a", "alpha-skill"), self.link_target(".agents/skills/alpha-skill"))
        self.assertEqual(self.src("cat-b", "beta-skill"), self.link_target(".claude/skills/beta-skill"))
        self.assertFalse(os.path.lexists(h / ".codex/skills/shared-skill"), "AI_SKILLS codex-dir link removed")
        text = (h / ".claude/CLAUDE.md").read_text()
        self.assertTrue(text.startswith(AI_ORCH_TEXT))
        self.assertNotIn(LEGACY_BEGIN, text)
        self.assertIn(BEGIN, text)
        self.assertTrue(text.rstrip().endswith("## Trailing foreign section"))
        self.assertFalse((h / ".agents/ai-developer-install.json").exists())
        self.assertFalse((h / ".ai-skills-install.json").exists())
        self.assertEqual(1, len(list((h / ".agents").glob("ai-developer-install.json.migrated-*"))))
        self.assertEqual(1, len(list(h.glob(".ai-skills-install.json.migrated-*"))))
        self.assertEqual(str(self.foreign_target), os.readlink(h / ".claude/skills/adding-an-mcp-tool"))
        self.run_install("--check", check=0)

    def seed_ai_orch_links_only(self):
        self.foreign_target = self.home / "Projects" / "AI_ORCHESTRATION" / "skills" / "adding-an-mcp-tool"
        self.foreign_target.mkdir(parents=True)
        os.symlink(self.foreign_target, self.home / ".claude" / "skills" / "adding-an-mcp-tool")

    def test_d_legacy_link_with_changed_target_is_conflict_with_zero_writes(self):
        self.seed_legacy()
        link = self.home / ".claude/skills/alpha-skill"
        os.unlink(link)
        os.symlink(self.home / "somewhere-else", link)
        before = snapshot(self.home)
        result = self.run_install(check=2)
        self.assertIn(".claude/skills/alpha-skill", result.stdout)
        self.assertIn("Nothing was written", result.stdout)
        self.assertEqual(before, snapshot(self.home))
        self.assertEqual([], self.journals())

    def test_changed_legacy_codex_link_blocks_record_retirement(self):
        self.seed_legacy()
        link = self.home / ".codex/skills/shared-skill"
        os.unlink(link)
        os.symlink(self.home / "user-choice", link)
        before = snapshot(self.home)
        result = self.run_install(check=2)
        self.assertIn("refusing to retire the legacy record", result.stdout)
        self.assertEqual(before, snapshot(self.home))
        self.assertTrue((self.home / ".ai-skills-install.json").exists())
        self.assertEqual([], self.journals())

    def test_legacy_items_outside_selection_are_refused(self):
        self.seed_legacy()
        before = snapshot(self.home)
        result = self.run_install("--bundle", "one", check=2)
        self.assertIn("beta-skill", result.stdout)
        self.assertEqual(before, snapshot(self.home))

    def test_k_rollback_of_adoption_restores_everything_byte_for_byte(self):
        self.seed_legacy()
        self.seed_ai_orch_links_only()
        before = snapshot(self.home)
        self.run_install(check=0)
        journal = self.journals()[-1].name
        self.run_install("--rollback", journal, check=0)
        self.assertEqual(before, snapshot(self.home))

    def seed_manual(self):
        d = self.home / ".claude/skills/alpha-skill"
        write(d / "SKILL.md", "hand copy\n")
        write(d / "references/notes.md", "notes\n")
        os.chmod(d, 0o755)
        os.chmod(d / "SKILL.md", 0o644)
        os.chmod(d / "references/notes.md", 0o640)
        return d

    def backup_tree(self):
        root = self.home / ".local/state/super-computer-ai/backups"
        return [p for p in root.rglob("*")]

    def test_backup_storage_is_private_and_rollback_restores_original_modes(self):
        manual = self.seed_manual()
        before = snapshot(self.home)
        self.run_install("--adopt-manual", "alpha-skill", check=0)
        items = self.backup_tree()
        self.assertTrue(items)
        for item in items:
            mode = stat.S_IMODE(item.lstat().st_mode)
            self.assertEqual(0o700 if item.is_dir() else 0o600, mode, item)
        self.run_install("--rollback", self.journals()[-1].name, check=0)
        self.assertEqual(before, snapshot(self.home))
        self.assertEqual(0o755, stat.S_IMODE(manual.stat().st_mode))
        self.assertEqual(0o644, stat.S_IMODE((manual / "SKILL.md").stat().st_mode))
        self.assertEqual(0o640, stat.S_IMODE((manual / "references/notes.md").stat().st_mode))

    def simulate_old_journal(self):
        """Mimic a journal written before backup storage was privatized (no manifest, original modes)."""
        journal_path = self.journals()[-1]
        data = json.loads(journal_path.read_text())
        for step in data["steps"]:
            step.pop("backup_privatized", None)
            if step.get("backup_modes"):
                backup = Path(step["backup"])
                for rel, mode in step.pop("backup_modes").items():
                    os.chmod(backup if rel == "." else backup / rel, mode)
        journal_path.write_text(json.dumps(data))
        return journal_path

    def test_backups_from_older_journals_are_hardened_safely(self):
        manual = self.seed_manual()
        before = snapshot(self.home)
        self.run_install("--adopt-manual", "alpha-skill", check=0)
        journal = self.simulate_old_journal()
        self.assertTrue(any(stat.S_IMODE(p.lstat().st_mode) == 0o644 for p in self.backup_tree()))
        result = self.run_install(check=0)
        self.assertIn("Secured backup storage", result.stdout)
        for item in self.backup_tree():
            self.assertEqual(0o700 if item.is_dir() else 0o600, stat.S_IMODE(item.lstat().st_mode), item)
        self.assertIn("backup_modes", json.dumps(json.loads(journal.read_text())))
        self.run_install("--rollback", journal.name, check=0)
        self.assertEqual(before, snapshot(self.home))
        self.assertEqual(0o640, stat.S_IMODE((manual / "references/notes.md").stat().st_mode))

    def test_tampered_old_backup_is_not_touched(self):
        self.seed_manual()
        self.run_install("--adopt-manual", "alpha-skill", check=0)
        self.simulate_old_journal()
        note = next(p for p in self.backup_tree() if p.name == "notes.md")
        note.write_text("changed after backup\n")
        modes = {p: stat.S_IMODE(p.lstat().st_mode) for p in self.backup_tree()}
        result = self.run_install(check=2)
        self.assertIn("backup differs from the journaled original", result.stdout)
        self.assertEqual(modes, {p: stat.S_IMODE(p.lstat().st_mode) for p in self.backup_tree()})

    def assert_backups_private(self):
        for item in self.backup_tree():
            self.assertEqual(0o700 if item.is_dir() else 0o600, stat.S_IMODE(item.lstat().st_mode), item)

    def journal_steps(self, journal):
        return [st for st in json.loads(journal.read_text())["steps"] if st.get("backup")]

    def test_hardening_interrupted_after_manifest_is_completed_later(self):
        manual = self.seed_manual()
        before = snapshot(self.home)
        self.run_install("--adopt-manual", "alpha-skill", check=0)
        journal = self.simulate_old_journal()
        self.assertEqual(99, self.run_install(fault="harden:after-manifest").returncode)
        step = self.journal_steps(journal)[0]
        self.assertIn("backup_modes", step)
        self.assertNotIn("backup_privatized", step)
        self.assertTrue(any(stat.S_IMODE(p.lstat().st_mode) == 0o640 for p in self.backup_tree()))
        result = self.run_install(check=0)
        self.assertIn("Secured backup storage", result.stdout)
        self.assert_backups_private()
        self.assertTrue(self.journal_steps(journal)[0]["backup_privatized"])
        self.run_install("--rollback", journal.name, check=0)
        self.assertEqual(before, snapshot(self.home))
        self.assertEqual(0o640, stat.S_IMODE((manual / "references/notes.md").stat().st_mode))

    def test_hardening_interrupted_mid_chmod_is_completed_later(self):
        manual = self.seed_manual()
        before = snapshot(self.home)
        self.run_install("--adopt-manual", "alpha-skill", check=0)
        journal = self.simulate_old_journal()
        self.assertEqual(99, self.run_install(fault="privatize:partial").returncode)
        modes = {stat.S_IMODE(p.lstat().st_mode) for p in self.backup_tree()}
        self.assertTrue(modes & {0o600, 0o700} and modes & {0o644, 0o640, 0o755}, modes)  # really partial
        self.run_install(check=0)
        self.assert_backups_private()
        self.run_install("--rollback", journal.name, check=0)
        self.assertEqual(before, snapshot(self.home))
        self.assertEqual(0o755, stat.S_IMODE(manual.stat().st_mode))

    def test_content_change_after_interrupted_hardening_is_conflict(self):
        self.seed_manual()
        self.run_install("--adopt-manual", "alpha-skill", check=0)
        self.simulate_old_journal()
        self.assertEqual(99, self.run_install(fault="privatize:partial").returncode)
        note = next(p for p in self.backup_tree() if p.name == "notes.md")
        note.write_text("changed after backup\n")
        modes = {p: stat.S_IMODE(p.lstat().st_mode) for p in self.backup_tree()}
        result = self.run_install(check=2)
        self.assertIn("backup differs from the journaled original", result.stdout)
        self.assertEqual(modes, {p: stat.S_IMODE(p.lstat().st_mode) for p in self.backup_tree()})

    def test_adoption_interrupted_mid_privatize_resumes_and_rolls_back(self):
        manual = self.seed_manual()
        before = snapshot(self.home)
        self.assertEqual(99, self.run_install("--adopt-manual", "alpha-skill", fault="privatize:partial").returncode)
        self.run_install("--resume", check=0)
        self.assert_backups_private()
        self.assertTrue(all(st.get("backup_privatized") for st in self.journal_steps(self.journals()[-1])))
        self.run_install("--rollback", self.journals()[-1].name, check=0)
        self.assertEqual(before, snapshot(self.home))
        self.assertEqual(0o640, stat.S_IMODE((manual / "references/notes.md").stat().st_mode))

    def test_manual_copy_requires_opt_in_and_is_backed_up(self):
        write(self.home / ".claude/skills/alpha-skill/SKILL.md", "hand copy\n")
        write(self.home / ".claude/skills/Shared_Copy/SKILL.md", "hand copy 2\n")
        before = snapshot(self.home)
        result = self.run_install(check=2)
        self.assertIn(".claude/skills/alpha-skill", result.stdout)
        self.assertEqual(before, snapshot(self.home))
        result = self.run_install("--adopt-manual", "alpha-skill", "--adopt-manual", "shared-skill", check=0)
        self.assertEqual(self.src("cat-a", "alpha-skill"), self.link_target(".claude/skills/alpha-skill"))
        self.assertFalse((self.home / ".claude/skills/Shared_Copy").exists())
        backups = self.home / ".local/state/super-computer-ai/backups"
        self.assertEqual(2, len([p for p in backups.rglob("SKILL.md")]))
        self.run_install("--rollback", self.journals()[-1].name, check=0)
        self.assertEqual(before, snapshot(self.home))


class JournalRecoveryTest(InstallerTestCase):
    POINTS = ("after-intent", "after-apply", "after-done")

    def fresh(self, label):
        """A new, freshly seeded HOME (legacy installers + foreign content) for one scenario."""
        self.home = Path(self._tmp.name) / f"home-{label}"
        self.home.mkdir()
        self.seed_legacy()
        return self.home

    @staticmethod
    def normalize(snap):
        return {k.split(".migrated-")[0]: v for k, v in snap.items()}

    def step_count(self):
        return len(json.loads(self.journals()[-1].read_text())["steps"])

    def reference(self):
        self.fresh("reference-initial")
        initial = snapshot(self.home)
        self.run_install(check=0)
        return initial, self.normalize(snapshot(self.home)), self.step_count()

    def test_e_e4_every_install_fault_point_resumes_to_clean_result(self):
        _, expected, steps = self.reference()
        self.assertGreater(steps, 8)
        for step in range(steps):
            for point in self.POINTS:
                with self.subTest(step=step, point=point):
                    self.fresh(f"resume-{step}-{point}")
                    self.assertEqual(99, self.run_install(fault=f"{step}:{point}").returncode)
                    blocked = self.run_install()
                    self.assertEqual(4, blocked.returncode, blocked.stdout)
                    self.run_install("--resume", check=0)
                    self.assertEqual(expected, self.normalize(snapshot(self.home)))
                    self.run_install("--check", check=0)

    def test_e4_every_install_fault_point_rolls_back_directly_to_initial_state(self):
        initial, _, steps = self.reference()
        for step in range(steps):
            for point in self.POINTS:
                with self.subTest(step=step, point=point):
                    self.fresh(f"rollback-{step}-{point}")
                    self.assertEqual(99, self.run_install(fault=f"{step}:{point}").returncode)
                    self.run_install("--rollback", self.journals()[-1].name, check=0)
                    self.assertEqual(initial, snapshot(self.home))

    def test_e4_rollback_interrupted_at_every_point_can_be_finished(self):
        initial, _, steps = self.reference()
        for step in range(steps):
            for point in self.POINTS:
                with self.subTest(step=step, point=point):
                    self.fresh(f"rb-{step}-{point}")
                    self.run_install(check=0)
                    journal = self.journals()[-1].name
                    result = self.run_install("--rollback", journal, fault=f"rb:{step}:{point}")
                    self.assertEqual(99, result.returncode, result.stdout)
                    resume = self.run_install("--resume")
                    self.assertEqual(4, resume.returncode, "resume must refuse a started rollback")
                    self.run_install("--rollback", journal, check=0)
                    self.assertEqual(initial, snapshot(self.home))

    def test_e2_user_change_after_interruption_is_never_overwritten(self):
        plan = self.run_install("--dry-run", check=0)
        links = [i for i, line in enumerate(self._steps_from_probe()) if line == "link"]
        first_link, later_link = links[0], links[-1]
        self.assertEqual(99, self.run_install(fault=f"{first_link}:after-done").returncode)
        journal = json.loads(self.journals()[-1].read_text())
        later = journal["steps"][later_link]["target"]
        done = journal["steps"][first_link]["target"]
        self.assertEqual("done", journal["steps"][first_link]["state"])
        self.assertEqual("planned", journal["steps"][later_link]["state"])
        # a later (not yet applied) target gets user content -> resume must stop and preserve it
        write(Path(later), "user content\n")
        result = self.run_install("--resume", check=2)
        self.assertIn("changed outside the installer", result.stdout)  # first affected step (dir or link)
        self.assertEqual("user content\n", Path(later).read_text())
        # an applied target is changed by the user -> rollback must stop and preserve it
        os.unlink(done)
        write(Path(done), "user replaced link\n")
        self.run_install("--rollback", self.journals()[-1].name, check=2)
        self.assertEqual("user replaced link\n", Path(done).read_text())
        self.assertEqual("user content\n", Path(later).read_text())

    def _steps_from_probe(self):
        """Step types ('link', 'dir', 'file', ...) of a full install of this HOME, computed on a scratch copy."""
        home = self.home
        self.home = Path(self._tmp.name) / "probe-steps"
        self.home.mkdir()
        self.run_install(check=0)
        types = [step["after"]["type"] for step in json.loads(self.journals()[-1].read_text())["steps"]]
        self.home = home
        return types

    def test_e3_concurrent_run_is_blocked_with_zero_writes(self):
        state = self.home / ".local/state/super-computer-ai"
        state.mkdir(parents=True, mode=0o700)
        fd = os.open(str(state / "install.lock"), os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            before = snapshot(self.home)
            result = self.run_install(check=4)
            self.assertIn("lock", result.stdout)
            self.assertEqual(before, snapshot(self.home))
        finally:
            os.close(fd)

    def test_f_rollback_restores_managed_targets_and_keeps_audit_state(self):
        self.seed_ai_orch()
        before = snapshot(self.home)
        self.run_install(check=0)
        self.run_install("--rollback", self.journals()[-1].name, check=0)
        self.assertEqual(before, snapshot(self.home))
        data = json.loads(self.journals()[-1].read_text())
        self.assertEqual("rolled_back", data["status"])  # journal kept for audit


class BundleTest(InstallerTestCase):
    def installed_skills(self):
        d = self.home / ".claude" / "skills"
        return sorted(p.name for p in d.iterdir()) if d.is_dir() else []

    def test_1_bundles_accumulate(self):
        self.run_install("--bundle", "one", check=0)
        self.assertEqual(["alpha-skill", "shared-skill"], self.installed_skills())
        self.run_install("--bundle", "two", check=0)
        self.assertEqual(["alpha-skill", "beta-skill", "shared-skill"], self.installed_skills())

    def test_2_removing_a_bundle_keeps_shared_items(self):
        self.run_install("--bundle", "one", "--bundle", "two", check=0)
        self.run_install("--remove-bundle", "one", check=0)
        self.assertEqual(["beta-skill", "shared-skill"], self.installed_skills())
        self.assertFalse(os.path.lexists(self.home / ".claude/agents/researcher.md"))
        self.assertNotIn("Bundle one rule", (self.home / ".claude/CLAUDE.md").read_text())

    def test_3_rerun_without_bundle_keeps_selection(self):
        self.run_install("--bundle", "two", check=0)
        before = snapshot(self.home)
        self.run_install(check=0)
        self.assertEqual(before, snapshot(self.home))
        record = json.loads((self.home / ".local/state/super-computer-ai/ownership.json").read_text())
        self.assertEqual(["two"], record["selected_bundles"])
        self.assertFalse(record["select_all"])

    def test_4_roles_follow_their_bundle(self):
        self.run_install("--bundle", "two", check=0)
        self.assertFalse(os.path.lexists(self.home / ".claude/agents/researcher.md"))
        self.run_install("--bundle", "one", check=0)
        self.assertTrue(os.path.lexists(self.home / ".claude/agents/researcher.md"))
        self.assertTrue(os.path.lexists(self.home / ".codex/agents/researcher.toml"))

    def test_5_rollback_of_bundle_removal_restores_selection(self):
        self.run_install("--bundle", "one", "--bundle", "two", check=0)
        before = snapshot(self.home)
        record_path = self.home / ".local/state/super-computer-ai/ownership.json"
        record_before = record_path.read_text()
        self.run_install("--remove-bundle", "two", check=0)
        self.run_install("--rollback", self.journals()[-1].name, check=0)
        self.assertEqual(before, snapshot(self.home))
        self.assertEqual(record_before, record_path.read_text())

    def add_bundle_to_repo(self, name="three"):
        manifest = self.repo / "skills" / "manifest.json"
        data = json.loads(manifest.read_text())
        data["skills"]["gamma-skill"] = {"category": "cat-c", "status": "active", "profile": "basic",
                                         "platforms": ["claude"], "bundles": [name]}
        manifest.write_text(json.dumps(data))
        write(self.repo / "skills/cat-c/gamma-skill/SKILL.md", "---\nname: gamma-skill\ndescription: x\n---\n")

    def test_default_all_selection_picks_up_bundles_added_later(self):
        self.run_install(check=0)
        self.add_bundle_to_repo()
        self.run_install("--check", check=1)
        self.run_install(check=0)
        self.assertIn("gamma-skill", self.installed_skills())

    def test_explicit_selection_does_not_grow_and_removal_ends_all(self):
        self.run_install("--bundle", "one", check=0)
        self.add_bundle_to_repo()
        self.run_install("--check", check=0)
        self.assertNotIn("gamma-skill", self.installed_skills())
        self.run_install("--bundle", "all", check=0)
        self.assertIn("gamma-skill", self.installed_skills())
        self.run_install("--remove-bundle", "two", check=0)
        self.add_bundle_to_repo("four")
        self.run_install("--check", check=1)  # gamma moved to 'four': no longer selected -> removal pending
        record = json.loads((self.home / ".local/state/super-computer-ai/ownership.json").read_text())
        self.assertFalse(record["select_all"])

    def test_record_only_change_is_journaled(self):
        self.run_install("--bundle", "one", "--bundle", "two", check=0)  # every bundle, but as an explicit list
        before_links, journals = snapshot(self.home), len(self.journals())
        result = self.run_install("--bundle", "all", check=0)
        self.assertIn("Applied 1 step(s)", result.stdout)
        self.assertEqual(journals + 1, len(self.journals()))
        self.assertEqual(before_links, snapshot(self.home))
        record = json.loads((self.home / ".local/state/super-computer-ai/ownership.json").read_text())
        self.assertTrue(record["select_all"])
        self.add_bundle_to_repo()
        self.run_install(check=0)
        self.assertIn("gamma-skill", self.installed_skills())
        # and the record-only step is reversible like any other
        self.run_install("--rollback", self.journals()[-2].name, check=2)  # later journal changed state since

    def test_unknown_bundle_is_an_error(self):
        result = self.run_install("--bundle", "nope", check=3)
        self.assertIn("unknown bundle", result.stdout)

    def test_codex_legacy_dir_is_opt_in(self):
        self.run_install("--codex-legacy-skills-dir", check=0)
        self.assertTrue(os.path.lexists(self.home / ".codex/skills/alpha-skill"))
        self.run_install(check=0)  # option is remembered
        self.assertTrue(os.path.lexists(self.home / ".codex/skills/alpha-skill"))


if __name__ == "__main__":
    unittest.main()
