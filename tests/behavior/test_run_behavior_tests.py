import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


REPO = Path(__file__).resolve().parents[2]
RUNNER_PATH = REPO / "scripts" / "run_behavior_tests.py"
SPEC = importlib.util.spec_from_file_location("run_behavior_tests", RUNNER_PATH)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


def make_config(repo=REPO):
    return runner.RunnerConfig(
        repo=Path(repo),
        profile="smoke",
        timeout_s=300,
        concurrency=2,
        infra_retries=1,
        max_runs=100,
        codex_bin="codex",
        claude_bin="claude",
        codex_model=None,
        claude_model=None,
        judge_platform="claude",
        judge_model=None,
    )


def make_fixture_payload(**overrides):
    payload = {
        "id": "sample-p1",
        "platforms": ["codex", "claude"],
        "lang": "en",
        "prompt": "Do the bounded task.",
        "repeats": 3,
        "pass_threshold": 2,
        "timeout_s": 300,
        "expect": {
            "evidence_required": ["behavioral-compliance"],
            "must": ["states the result"],
            "must_not": ["fabricates evidence"],
        },
    }
    payload.update(overrides)
    return payload


class FixtureTests(unittest.TestCase):
    def test_real_fixture_tree_and_profiles_parse(self):
        fixtures = runner.load_fixtures(
            REPO / "tests" / "behavior" / "fixtures", 300
        )
        self.assertEqual(96, len(fixtures))

        smoke = runner.select_fixtures(fixtures, "smoke", [])
        self.assertEqual(28, len(smoke))
        specs = runner.build_run_specs(smoke, "smoke", runner.PLATFORMS)
        self.assertEqual(56, len(specs))
        self.assertTrue(all(spec.repeat == 1 for spec in specs))
        self.assertTrue(all(spec.threshold_in_profile == 1 for spec in specs))

        full = runner.select_fixtures(fixtures, "full", [])
        full_specs = runner.build_run_specs(full, "full", runner.PLATFORMS)
        self.assertEqual(576, len(full_specs))

    def test_composite_and_negative_schema_extensions(self):
        fixtures = {
            item.fixture_id: item
            for item in runner.load_fixtures(
                REPO / "tests" / "behavior" / "fixtures", 300
            )
        }
        composite = fixtures["composite-model-research"]
        self.assertEqual(
            ("model-selection-hf", "ai-research"), composite.expected_skills
        )
        self.assertEqual(composite.expected_skills, composite.discovery_skills)

        negative = fixtures["ai-research-n1"]
        self.assertEqual("codebase-local", negative.route_label)
        self.assertEqual((), negative.expected_skills)
        self.assertEqual(("ai-research",), negative.discovery_skills)
        self.assertEqual(("ai-research",), negative.prohibited_skills)

        role = fixtures["role-researcher"]
        self.assertEqual("researcher", role.agent_role)
        self.assertEqual("forbidden", role.workspace_change_policy)

    def test_routing_claim_without_event_class_is_rejected(self):
        payload = make_fixture_payload()
        payload["expect"]["skill_invoked"] = "ai-research"
        with self.assertRaisesRegex(runner.HarnessError, "no routing evidence"):
            runner.parse_fixture(payload, Path("bad.json"), 300)

    def test_default_smoke_requires_both_p1_and_n1(self):
        payload = make_fixture_payload()
        fixture = runner.parse_fixture(payload, Path("sample-p1.json"), 300)
        with self.assertRaisesRegex(runner.HarnessError, r"exactly p1\+n1"):
            runner.select_fixtures([fixture], "smoke", [])
        self.assertEqual(
            [fixture], runner.select_fixtures([fixture], "smoke", ["sample-p1"])
        )

    def test_cli_defaults_to_claude_judge_and_rejects_codex_judging(self):
        parser = runner.build_parser()
        defaults = parser.parse_args(["--repo", str(REPO), "--dry-run"])
        self.assertEqual("claude", defaults.judge_platform)

        unsafe = parser.parse_args(
            [
                "--repo",
                str(REPO),
                "--platform",
                "codex",
                "--judge-platform",
                "same",
                "--dry-run",
            ]
        )
        with self.assertRaisesRegex(runner.HarnessError, "strict input isolation"):
            runner.run(unsafe)


class EventTaxonomyTests(unittest.TestCase):
    def setUp(self):
        self.events = [
            {
                "type": "system",
                "subtype": "init",
                "skills": ["probe-skill", "ai-research"],
                "model": "claude-test",
            },
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Skill",
                            "input": {"skill": "probe-skill"},
                        }
                    ]
                },
            },
            {
                "type": "user",
                "tool_use_result": {
                    "success": True,
                    "commandName": "probe-skill",
                },
            },
            {"type": "result", "result": "PROBE-OK"},
        ]

    def test_claude_discovery_and_explicit_execution_are_separate(self):
        evidence = runner.classify_routing_events(
            "claude", self.events, ["probe-skill"]
        )
        skill = evidence["skills"]["probe-skill"]
        self.assertEqual(1, len(skill["discovery"]))
        self.assertEqual(1, len(skill["explicit-execution"]))
        self.assertEqual(1, len(skill["execution-corroboration"]))
        self.assertEqual("PROBE-OK", runner.extract_final_output("claude", self.events))

    def test_claude_tool_result_alone_is_not_explicit_execution(self):
        events = [
            {
                "type": "system",
                "subtype": "init",
                "skills": ["probe-skill"],
            },
            {
                "type": "user",
                "tool_use_result": {
                    "success": True,
                    "commandName": "probe-skill",
                },
            },
        ]

        evidence = runner.classify_routing_events(
            "claude", events, ["probe-skill"]
        )
        skill = evidence["skills"]["probe-skill"]
        self.assertFalse(skill["explicit-execution"])
        self.assertEqual(1, len(skill["execution-corroboration"]))
        result = runner._routing_class_result(
            "explicit-execution",
            evidence,
            ["probe-skill"],
            required=True,
        )
        self.assertEqual("fail", result["status"])

    def test_checked_in_live_probe_matches_parser_taxonomy(self):
        taxonomy = (
            REPO / "tests" / "behavior" / "results" / "event-taxonomy.md"
        ).read_text(encoding="utf-8")
        claude_probe = json.loads(
            (REPO / "tests" / "behavior" / "results" / "probe-claude.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(0, claude_probe["exit_code"])
        self.assertIn(claude_probe["command"], taxonomy)
        evidence = runner.classify_routing_events(
            "claude", claude_probe["events"], ["probe-skill"]
        )
        self.assertTrue(evidence["skills"]["probe-skill"]["discovery"])
        self.assertTrue(evidence["skills"]["probe-skill"]["explicit-execution"])
        self.assertEqual(
            "PROBE-OK",
            runner.extract_final_output("claude", claude_probe["events"]),
        )

        codex_probe = json.loads(
            (REPO / "tests" / "behavior" / "results" / "probe-codex.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(0, codex_probe["exit_code"])
        self.assertIn(codex_probe["command"], taxonomy)
        self.assertFalse(codex_probe["infrastructure_error"])
        codex_evidence = runner.classify_routing_events(
            "codex", codex_probe["events"], ["probe-skill"]
        )
        self.assertFalse(codex_evidence["skills"]["probe-skill"]["discovery"])
        self.assertFalse(
            codex_evidence["skills"]["probe-skill"]["explicit-execution"]
        )
        self.assertEqual(
            "PROBE-OK", runner.extract_final_output("codex", codex_probe["events"])
        )
        self.assertEqual("unsupported", runner.ROUTING_TAXONOMY_STATUS["codex"])

    def test_prose_never_counts_as_routing_evidence(self):
        events = [
            {"type": "system", "subtype": "init", "skills": []},
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": "I invoked Skill ai-research"}
                    ]
                },
            },
        ]
        evidence = runner.classify_routing_events("claude", events, ["ai-research"])
        self.assertFalse(evidence["skills"]["ai-research"]["discovery"])
        self.assertFalse(evidence["skills"]["ai-research"]["explicit-execution"])

    def test_codex_remains_unsupported_even_if_prose_mentions_skill(self):
        evidence = runner.classify_routing_events(
            "codex",
            [
                {
                    "type": "item.completed",
                    "item": {
                        "type": "agent_message",
                        "text": "I used probe-skill",
                    },
                }
            ],
            ["probe-skill"],
        )
        self.assertEqual("unsupported", evidence["taxonomy_status"])
        self.assertFalse(evidence["skills"]["probe-skill"]["discovery"])
        self.assertFalse(evidence["skills"]["probe-skill"]["explicit-execution"])

    def test_negative_explicit_execution_requires_absence(self):
        routing = runner.classify_routing_events(
            "claude", self.events, ["ai-research"]
        )
        result = runner._routing_class_result(
            "explicit-execution",
            routing,
            ["ai-research"],
            required=True,
            expect_absence=True,
        )
        self.assertEqual("pass", result["status"])

        invoked = list(self.events)
        invoked.append(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Skill",
                            "input": {"skill": "ai-research"},
                        }
                    ]
                },
            }
        )
        routing = runner.classify_routing_events("claude", invoked, ["ai-research"])
        result = runner._routing_class_result(
            "explicit-execution",
            routing,
            ["ai-research"],
            required=True,
            expect_absence=True,
        )
        self.assertEqual("fail", result["status"])


class CommandAndJudgeTests(unittest.TestCase):
    def test_subject_commands_use_required_headless_modes(self):
        config = make_config()
        codex = runner.subject_command("codex", config, "prompt")
        self.assertEqual(
            [
                "codex",
                "exec",
                "--ephemeral",
                "-C",
                str(REPO),
                "-s",
                "read-only",
                "--skip-git-repo-check",
                "--json",
                "prompt",
            ],
            codex,
        )
        claude = runner.subject_command(
            "claude", config, "prompt", agent_role="researcher"
        )
        self.assertIn("--no-session-persistence", claude)
        self.assertIn("plan", claude)
        self.assertIn("stream-json", claude)
        self.assertEqual(["--agent", "researcher"], claude[-3:-1])

    def test_judge_commands_disable_user_and_project_customizations(self):
        config = make_config()
        judge_dir = Path("/tmp/isolated-judge")
        schema_path = Path("/tmp/isolated-judge-schema.json")
        schema = {"type": "array"}

        codex, codex_cwd = runner.judge_command(
            "codex", config, "prompt", judge_dir, schema_path, schema
        )
        self.assertIn("--ignore-user-config", codex)
        self.assertIn("--ignore-rules", codex)
        self.assertEqual(["--disable", "shell_tool"], codex[5:7])
        self.assertIn("multi_agent", codex)
        self.assertIn('web_search="disabled"', codex)
        self.assertEqual(judge_dir, codex_cwd)

        claude, claude_cwd = runner.judge_command(
            "claude", config, "prompt", judge_dir, None, schema
        )
        self.assertIn("--safe-mode", claude)
        self.assertEqual(judge_dir, claude_cwd)

        inherited = runner.dataclasses.replace(config, codex_model="gpt-test")
        codex, _ = runner.judge_command(
            "codex", inherited, "prompt", judge_dir, schema_path, schema
        )
        self.assertEqual(["--model", "gpt-test"], codex[-3:-1])

    def test_successful_subject_requires_actual_model_provenance(self):
        fixture = runner.parse_fixture(
            make_fixture_payload(), Path("sample.json"), 300
        )
        spec = runner.RunSpec(1, fixture, "codex", 1, 1, 1)
        process = {
            "command": ["codex"],
            "cwd": str(REPO),
            "timeout_s": 10,
            "timed_out": False,
            "duration_s": 0.1,
            "stdout": json.dumps(
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": "answer"},
                }
            )
            + "\n",
            "stderr": "",
            "exit_code": 0,
        }
        with mock.patch.object(runner, "_run_process", return_value=process):
            with self.assertRaisesRegex(
                runner.InfrastructureError, "did not identify the model"
            ):
                runner.run_subject(spec, make_config(), 10)

            configured = runner.dataclasses.replace(
                make_config(), codex_model="gpt-test"
            )
            observed = runner.run_subject(spec, configured, 10)
        self.assertEqual("gpt-test", observed["observed_model"])

    @unittest.skipUnless(shutil.which("codex"), "Codex CLI is not installed")
    def test_codex_judge_feature_overrides_parse_in_real_cli(self):
        with tempfile.TemporaryDirectory(
            prefix="codex-config-probe-home-"
        ) as home_raw, tempfile.TemporaryDirectory(
            prefix="codex-config-probe-cwd-"
        ) as cwd_raw:
            env = os.environ.copy()
            env["CODEX_HOME"] = home_raw
            completed = subprocess.run(
                [
                    "codex",
                    "debug",
                    "prompt-input",
                    "--disable",
                    "shell_tool",
                    "--disable",
                    "multi_agent",
                    "-c",
                    'web_search="disabled"',
                    "JUDGE-CONFIG-PROBE",
                ],
                cwd=cwd_raw,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("JUDGE-CONFIG-PROBE", completed.stdout)

    def test_codex_judge_is_rejected_before_a_model_call(self):
        fixture = runner.parse_fixture(
            make_fixture_payload(), Path("sample.json"), 300
        )
        spec = runner.RunSpec(1, fixture, "codex", 1, 1, 1)
        config = runner.dataclasses.replace(
            make_config(), codex_model="gpt-test", judge_platform="same"
        )
        with mock.patch.object(runner, "_run_process") as process:
            with self.assertRaisesRegex(
                runner.InfrastructureError, "built-in system skills"
            ):
                runner.run_judge(spec, config, "answer", 10)
        process.assert_not_called()

    def test_codex_role_config_layer_applies_checked_in_controls(self):
        expected = {
            "researcher": ("read-only", None),
            "architect": ("read-only", None),
            "implementer": ("workspace-write", False),
            "evaluator": ("workspace-write", False),
        }
        for role_name, (sandbox_mode, network_access) in expected.items():
            with self.subTest(role=role_name):
                role = runner.load_codex_role_config(REPO, role_name)
                command = runner.subject_command(
                    "codex",
                    make_config(),
                    "prompt",
                    agent_role=role_name,
                )
                self.assertEqual(sandbox_mode, role.sandbox_mode)
                self.assertEqual(network_access, role.network_access)
                self.assertTrue(role.developer_instructions.endswith("\n"))
                self.assertEqual(64, len(role.source_sha256))
                self.assertEqual(
                    runner.hashlib.sha256(role.source.read_bytes()).hexdigest(),
                    role.source_sha256,
                )
                self.assertEqual(sandbox_mode, command[command.index("-s") + 1])
                self.assertIn("--skip-git-repo-check", command)
                self.assertIn(
                    "developer_instructions="
                    + json.dumps(role.developer_instructions, ensure_ascii=False),
                    command,
                )
                network_override = (
                    "sandbox_workspace_write.network_access=false"
                )
                self.assertEqual(network_access is False, network_override in command)

        payload = make_fixture_payload(agent_role="researcher")
        payload["expect"]["workspace_changes"] = "forbidden"
        fixture = runner.parse_fixture(payload, Path("role.json"), 300)
        spec = runner.RunSpec(1, fixture, "codex", 1, 1, 1)
        evidence = runner.role_evidence(
            spec,
            successful_subject=True,
            application_evidence=runner.role_application_evidence(
                "codex", REPO, "researcher"
            ),
            workspace_evidence={"status": "pass", "changes": []},
            repo=REPO,
        )
        self.assertEqual("pass", evidence["status"])
        self.assertEqual(
            "primary-session-config-overrides",
            evidence["application_evidence"]["mechanism"],
        )
        weak = runner.role_evidence(
            spec,
            successful_subject=True,
            application_evidence={
                "mechanism": "primary-session-config-overrides"
            },
            workspace_evidence={"status": "pass", "changes": []},
            repo=REPO,
        )
        self.assertEqual("infrastructure-error", weak["status"])

    def test_codex_role_config_fails_closed_on_incomplete_workspace_policy(self):
        with tempfile.TemporaryDirectory(prefix="codex-role-config-") as repo_raw:
            role_dir = Path(repo_raw) / "agents" / "codex"
            role_dir.mkdir(parents=True)
            (role_dir / "implementer.toml").write_text(
                '\n'.join(
                    [
                        'name = "implementer"',
                        'description = "test role"',
                        'sandbox_mode = "workspace-write"',
                        'developer_instructions = """',
                        'Do the bounded implementation.',
                        '"""',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                runner.HarnessError, "must define sandbox network_access"
            ):
                runner.load_codex_role_config(Path(repo_raw), "implementer")

    def test_codex_role_config_rejects_unapplied_fields(self):
        with tempfile.TemporaryDirectory(prefix="codex-role-drift-") as repo_raw:
            role_dir = Path(repo_raw) / "agents" / "codex"
            role_dir.mkdir(parents=True)
            source = (REPO / "agents" / "codex" / "researcher.toml").read_text(
                encoding="utf-8"
            )
            (role_dir / "researcher.toml").write_text(
                source + 'model = "ignored-model"\n', encoding="utf-8"
            )
            with self.assertRaisesRegex(runner.HarnessError, "narrow role schema"):
                runner.load_codex_role_config(Path(repo_raw), "researcher")

    def test_codex_role_config_rejects_invalid_multiline_escape(self):
        with tempfile.TemporaryDirectory(prefix="codex-role-escape-") as repo_raw:
            role_dir = Path(repo_raw) / "agents" / "codex"
            role_dir.mkdir(parents=True)
            source = (REPO / "agents" / "codex" / "researcher.toml").read_text(
                encoding="utf-8"
            )
            source = source.replace(
                "Report conflicts and unknowns explicitly.",
                "Invalid TOML escape: \\q",
            )
            (role_dir / "researcher.toml").write_text(source, encoding="utf-8")
            with self.assertRaisesRegex(runner.HarnessError, "must not contain TOML"):
                runner.load_codex_role_config(Path(repo_raw), "researcher")

    def test_codex_role_config_rejects_single_line_escape_outside_subset(self):
        with tempfile.TemporaryDirectory(prefix="codex-role-basic-escape-") as repo_raw:
            role_dir = Path(repo_raw) / "agents" / "codex"
            role_dir.mkdir(parents=True)
            source = (REPO / "agents" / "codex" / "researcher.toml").read_text(
                encoding="utf-8"
            ).replace(
                'description = "Read-only evidence researcher for current facts and unfamiliar domains."',
                'description = "invalid \\/ escape"',
            )
            (role_dir / "researcher.toml").write_text(source, encoding="utf-8")
            with self.assertRaisesRegex(runner.HarnessError, "literal text only"):
                runner.load_codex_role_config(Path(repo_raw), "researcher")

    def test_codex_role_config_rejects_inline_multiline_delimiter(self):
        with tempfile.TemporaryDirectory(prefix="codex-role-delimiter-") as repo_raw:
            role_dir = Path(repo_raw) / "agents" / "codex"
            role_dir.mkdir(parents=True)
            source = (REPO / "agents" / "codex" / "researcher.toml").read_text(
                encoding="utf-8"
            ).replace(
                "Report conflicts and unknowns explicitly.",
                'Invalid inline delimiter: one """ two',
            )
            (role_dir / "researcher.toml").write_text(source, encoding="utf-8")
            with self.assertRaisesRegex(runner.HarnessError, "inline multiline"):
                runner.load_codex_role_config(Path(repo_raw), "researcher")

    def test_codex_role_config_rejects_privilege_escalation(self):
        with tempfile.TemporaryDirectory(prefix="codex-role-policy-") as repo_raw:
            role_dir = Path(repo_raw) / "agents" / "codex"
            role_dir.mkdir(parents=True)
            source = (REPO / "agents" / "codex" / "implementer.toml").read_text(
                encoding="utf-8"
            ).replace("network_access = false", "network_access = true")
            (role_dir / "implementer.toml").write_text(source, encoding="utf-8")
            with self.assertRaisesRegex(runner.HarnessError, "immutable implementer"):
                runner.load_codex_role_config(Path(repo_raw), "implementer")

    @unittest.skipUnless(shutil.which("codex"), "Codex CLI is not installed")
    def test_codex_role_instructions_reach_real_cli_prompt_layer(self):
        with tempfile.TemporaryDirectory(
            prefix="codex-role-probe-home-"
        ) as home_raw, tempfile.TemporaryDirectory(
            prefix="codex-role-probe-cwd-"
        ) as cwd_raw:
            env = os.environ.copy()
            env["CODEX_HOME"] = home_raw
            for role_name in runner.AGENT_ROLES:
                with self.subTest(role=role_name):
                    role = runner.load_codex_role_config(REPO, role_name)
                    command = [
                        "codex",
                        "debug",
                        "prompt-input",
                        "-c",
                        "developer_instructions="
                        + json.dumps(role.developer_instructions, ensure_ascii=False),
                        "-c",
                        "sandbox_mode=" + json.dumps(role.sandbox_mode),
                    ]
                    if role.network_access is not None:
                        command.extend(
                            [
                                "-c",
                                "sandbox_workspace_write.network_access={}".format(
                                    "true" if role.network_access else "false"
                                ),
                            ]
                        )
                    command.append("ROLE-CONFIG-PROBE-{}".format(role_name))
                    completed = subprocess.run(
                        command,
                        cwd=cwd_raw,
                        env=env,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                    )
                    self.assertEqual(0, completed.returncode, completed.stderr)
                    marker = role.developer_instructions.strip().split(". ", 1)[0]
                    self.assertIn(marker, completed.stdout)
                    self.assertIn(
                        "sandbox_mode` is `{}`".format(role.sandbox_mode),
                        completed.stdout,
                    )
                    if role.network_access is False:
                        self.assertIn("Network access is restricted", completed.stdout)
                    self.assertIn(
                        "ROLE-CONFIG-PROBE-{}".format(role_name), completed.stdout
                    )

    def test_judge_prompt_contains_only_rubric_and_test_output_payload(self):
        payload = make_fixture_payload()
        payload["id"] = "secret-fixture-id"
        payload["prompt"] = "SECRET SUBJECT PROMPT"
        fixture = runner.parse_fixture(payload, Path("fixture.json"), 300)
        prompt = runner.judge_prompt(fixture, "VISIBLE TEST OUTPUT")
        self.assertNotIn("secret-fixture-id", prompt)
        self.assertNotIn("SECRET SUBJECT PROMPT", prompt)
        self.assertIn("VISIBLE TEST OUTPUT", prompt)
        self.assertIn("must: states the result", prompt)

    def test_judge_schema_and_parser_require_exact_rubric_coverage(self):
        items = [
            {"item": "must: a", "criterion_type": "must"},
            {"item": "must_not: b", "criterion_type": "must_not"},
        ]
        schema = runner.judge_schema(items)
        self.assertEqual("array", schema["type"])
        self.assertEqual(2, schema["minItems"])
        valid = [
            {"item": "must: a", "verdict": "pass", "evidence": "line 1"},
            {
                "item": "must_not: b",
                "verdict": "fail",
                "evidence": "line 2",
            },
        ]
        ok, _ = runner.validate_judge_payload(
            valid, ["must: a", "must_not: b"]
        )
        self.assertTrue(ok)
        ok, reason = runner.validate_judge_payload(
            valid[:1], ["must: a", "must_not: b"]
        )
        self.assertFalse(ok)
        self.assertIn("expected 2", reason)


class RetryAndBudgetTests(unittest.TestCase):
    def test_role_workspace_rejects_source_symlink_escape_before_subject(self):
        payload = make_fixture_payload(agent_role="implementer")
        payload["expect"]["workspace_changes"] = "forbidden"
        fixture = runner.parse_fixture(payload, Path("role.json"), 300)
        spec = runner.RunSpec(1, fixture, "codex", 1, 1, 1)
        with tempfile.TemporaryDirectory(prefix="role-symlink-source-") as raw:
            parent = Path(raw)
            repo = parent / "repo"
            repo.mkdir()
            outside = parent / "outside.txt"
            outside.write_text("original", encoding="utf-8")
            (repo / "escape").symlink_to(outside)
            with mock.patch.object(runner, "run_subject") as run_subject:
                with self.assertRaisesRegex(
                    runner.InfrastructureError, "escaping or unresolvable symlinks"
                ):
                    runner.run_subject_in_isolated_role_workspace(
                        spec, make_config(repo), lambda: 10
                    )
            run_subject.assert_not_called()
            self.assertEqual("original", outside.read_text(encoding="utf-8"))

    def test_role_workspace_post_snapshot_rejects_new_escaping_symlink(self):
        with tempfile.TemporaryDirectory(prefix="role-symlink-post-") as raw:
            parent = Path(raw)
            repo = parent / "repo"
            repo.mkdir()
            outside = parent / "outside.txt"
            outside.write_text("original", encoding="utf-8")
            before = runner.workspace_snapshot(repo)
            (repo / "escape").symlink_to(outside)
            evidence = runner.role_workspace_evidence(repo, before, "allowed")
        self.assertEqual("fail", evidence["status"])
        self.assertEqual(1, evidence["escaping_symlink_count"])
        self.assertEqual("escape", evidence["escaping_symlinks"][0]["path"])

    def test_role_run_isolates_workspace_and_gates_forbidden_mutations(self):
        payload = make_fixture_payload(agent_role="implementer")
        payload["expect"]["workspace_changes"] = "forbidden"
        fixture = runner.parse_fixture(payload, Path("role.json"), 300)
        spec = runner.RunSpec(1, fixture, "codex", 1, 1, 1)
        subject = {
            "stdout": '{}\n',
            "stderr": "",
            "events": [
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": "answer"},
                }
            ],
            "final_output": "answer",
            "observed_model": "test-model",
            "role_application": runner.role_application_evidence(
                "codex", REPO, "implementer"
            ),
        }
        judge = {
            "status": "pass",
            "parsed": [
                {
                    "item": "must: states the result",
                    "verdict": "pass",
                    "evidence": "answer",
                },
                {
                    "item": "must_not: fabricates evidence",
                    "verdict": "pass",
                    "evidence": "no fabrication",
                },
            ],
        }

        def mutate_isolated_repo(_spec, isolated_config, _timeout):
            self.assertNotEqual(REPO, isolated_config.repo)
            (isolated_config.repo / "role-mutation.txt").write_text(
                "mutation", encoding="utf-8"
            )
            return dict(subject)

        with mock.patch.object(
            runner, "run_subject", side_effect=mutate_isolated_repo
        ), mock.patch.object(runner, "run_judge", return_value=judge):
            record = runner.execute_run(spec, make_config())

        self.assertFalse((REPO / "role-mutation.txt").exists())
        self.assertEqual("fail", record["role_evidence"]["status"])
        workspace = record["role_evidence"]["workspace_evidence"]
        self.assertEqual("forbidden", workspace["policy"])
        self.assertEqual(1, workspace["change_count"])
        self.assertEqual("role-mutation.txt", workspace["changes"][0]["path"])
        self.assertEqual("fail", record["overall_status"])

    def test_subject_and_judge_share_one_logical_run_deadline(self):
        fixture = runner.parse_fixture(
            make_fixture_payload(), Path("sample.json"), 300
        )
        spec = runner.RunSpec(1, fixture, "claude", 1, 1, 1)
        subject = {
            "stdout": '{}\n',
            "stderr": "",
            "events": [{"type": "result", "result": "answer"}],
            "final_output": "answer",
            "observed_model": "test-model",
        }
        judge = {
            "status": "pass",
            "parsed": [
                {
                    "item": "must: states the result",
                    "verdict": "pass",
                    "evidence": "answer",
                },
                {
                    "item": "must_not: fabricates evidence",
                    "verdict": "pass",
                    "evidence": "no fabrication",
                },
            ],
        }
        with mock.patch.object(
            runner.time, "monotonic", side_effect=[100.0, 101.0, 250.0]
        ), mock.patch.object(
            runner, "run_subject", return_value=subject
        ) as run_subject, mock.patch.object(
            runner, "run_judge", return_value=judge
        ) as run_judge:
            record = runner.execute_run(spec, make_config())

        self.assertEqual(300, record["logical_timeout_s"])
        self.assertEqual(299.0, run_subject.call_args.args[2])
        self.assertEqual(150.0, run_judge.call_args.args[3])

    def test_role_copy_time_is_deducted_before_subject_timeout(self):
        payload = make_fixture_payload(agent_role="implementer")
        payload["expect"]["workspace_changes"] = "forbidden"
        fixture = runner.parse_fixture(payload, Path("role.json"), 300)
        spec = runner.RunSpec(1, fixture, "codex", 1, 1, 1)
        subject = {
            "stdout": '{}\n',
            "stderr": "",
            "events": [
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": "answer"},
                }
            ],
            "final_output": "answer",
            "observed_model": "test-model",
            "role_application": runner.role_application_evidence(
                "codex", REPO, "implementer"
            ),
        }
        judge = {"status": "pass", "parsed": []}
        with mock.patch.object(
            runner.time, "monotonic", side_effect=[100.0, 140.0, 200.0]
        ), mock.patch.object(
            runner, "run_subject", return_value=subject
        ) as run_subject, mock.patch.object(
            runner, "run_judge", return_value=judge
        ) as run_judge:
            record = runner.execute_run(spec, make_config())

        self.assertEqual(260.0, run_subject.call_args.args[2])
        self.assertEqual(200.0, run_judge.call_args.args[3])
        self.assertEqual("pass", record["overall_status"])

    def test_one_infrastructure_retry_but_no_rubric_retry(self):
        fixture = runner.parse_fixture(
            make_fixture_payload(), Path("sample.json"), 300
        )
        spec = runner.RunSpec(1, fixture, "claude", 1, 1, 1)
        subject = {
            "stdout": '{}\n',
            "stderr": "",
            "events": [{"type": "result", "result": "answer"}],
            "final_output": "answer",
            "observed_model": "test-model",
        }
        judge = {
            "status": "fail",
            "parsed": [
                {
                    "item": "must: states the result",
                    "verdict": "fail",
                    "evidence": "missing",
                }
            ],
        }
        with mock.patch.object(
            runner,
            "run_subject",
            side_effect=[runner.InfrastructureError("transient"), subject],
        ) as run_subject, mock.patch.object(
            runner, "run_judge", return_value=judge
        ) as run_judge:
            record = runner.execute_run(spec, make_config())
        self.assertEqual(2, run_subject.call_count)
        self.assertEqual(1, run_judge.call_count)
        self.assertEqual(2, len(record["attempts"]))
        self.assertEqual("fail", record["overall_status"])

    def test_max_runs_plan_reports_every_deferred_run(self):
        fixture = runner.parse_fixture(
            make_fixture_payload(), Path("sample.json"), 300
        )
        specs = runner.build_run_specs([fixture], "full", runner.PLATFORMS)
        plan = runner._public_run_plan(specs, 2)
        self.assertEqual(6, plan["planned_runs"])
        self.assertEqual(2, plan["scheduled_runs"])
        self.assertEqual(4, plan["deferred_runs"])
        self.assertTrue(
            all(item["reason"] == "max-runs budget exhausted" for item in plan["deferred"])
        )

    def test_full_profile_requires_explicit_approval_before_fixture_io(self):
        parser = runner.build_parser()
        args = parser.parse_args(
            [
                "--repo",
                str(REPO),
                "--fixtures",
                str(REPO / "does-not-exist"),
                "--profile",
                "full",
                "--dry-run",
            ]
        )
        with self.assertRaisesRegex(runner.HarnessError, "explicit human approval"):
            runner.run(args)

    def test_fake_cli_exercises_subject_judge_and_result_record_end_to_end(self):
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            repo = temp / "repo"
            fixtures_dir = repo / "tests" / "behavior" / "fixtures"
            fixtures_dir.mkdir(parents=True)
            fixture = make_fixture_payload()
            fixture.update(
                {
                    "id": "probe-skill-p1",
                    "platforms": ["claude"],
                    "prompt": "Use probe-skill.",
                    "repeats": 1,
                    "pass_threshold": 1,
                    "expect": {
                        "skill_invoked": "probe-skill",
                        "evidence_required": [
                            "discovery",
                            "explicit-execution",
                            "behavioral-compliance",
                        ],
                        "must": ["responds exactly PROBE-OK"],
                        "must_not": [],
                    },
                }
            )
            (fixtures_dir / "probe-skill-p1.json").write_text(
                json.dumps(fixture), encoding="utf-8"
            )

            fake_cli = temp / "fake-claude"
            fake_cli.write_text(
                """#!/usr/bin/env python3
import json
import sys

if "--version" in sys.argv:
    print("fake-claude 1.0")
elif "--json-schema" in sys.argv:
    judged = [{
        "item": "must: responds exactly PROBE-OK",
        "verdict": "pass",
        "evidence": "output is exactly PROBE-OK"
    }]
    print(json.dumps({
        "type": "result", "result": json.dumps(judged), "model": "fake-model"
    }))
else:
    print(json.dumps({
        "type": "system", "subtype": "init",
        "skills": ["probe-skill"], "model": "fake-model"
    }))
    print(json.dumps({
        "type": "assistant",
        "message": {"content": [{
            "type": "tool_use", "name": "Skill",
            "input": {"skill": "probe-skill"}
        }]}
    }))
    print(json.dumps({"type": "result", "result": "PROBE-OK"}))
""",
                encoding="utf-8",
            )
            fake_cli.chmod(0o755)
            # install preflight: the probe skill is installed from this (temporary) checkout
            skill_dir = repo / "skills" / "test" / "probe-skill"
            skill_dir.mkdir(parents=True)
            (repo / "skills" / "manifest.json").write_text(
                json.dumps({"schema_version": 2, "skills": {"probe-skill": {"category": "test"}}}),
                encoding="utf-8",
            )
            fake_home = temp / "home"
            (fake_home / ".claude" / "skills").mkdir(parents=True)
            (fake_home / ".claude" / "skills" / "probe-skill").symlink_to(skill_dir)
            home_env = mock.patch.dict(
                os.environ, {"HOME": str(fake_home), "CLAUDE_CONFIG_DIR": str(fake_home / ".claude")}
            )
            result_path = temp / "result.json"
            args = runner.build_parser().parse_args(
                [
                    "--repo",
                    str(repo),
                    "--fixtures",
                    str(fixtures_dir),
                    "--fixture",
                    "probe-skill-p1",
                    "--platform",
                    "claude",
                    "--claude-bin",
                    str(fake_cli),
                    "--max-runs",
                    "1",
                    "--infra-retries",
                    "0",
                    "--results",
                    str(result_path),
                ]
            )
            with home_env:
                exit_code, payload, written = runner.run(args)

            self.assertEqual(0, exit_code)
            self.assertEqual("ok", payload["install_preflight"]["status"])
            self.assertEqual(result_path.resolve(), written)
            self.assertTrue(result_path.is_file())
            record = payload["records"][0]
            self.assertEqual("pass", record["overall_status"])
            self.assertEqual(
                {"pass"},
                {item["status"] for item in record["evidence_classes"].values()},
            )
            self.assertEqual("fake-model", record["model"])
            judge_cwd = Path(record["judge"]["isolated_cwd"])
            self.assertNotEqual(
                os.path.commonpath([str(repo.resolve()), str(judge_cwd)]),
                str(repo.resolve()),
            )
            self.assertTrue(record["judge"]["repo_outside_cwd"])
            self.assertEqual("fake-claude 1.0", payload["cli_versions"]["claude"]["stdout"])


if __name__ == "__main__":
    unittest.main()


class WorkspaceSnapshotLocalDirTests(unittest.TestCase):
    def test_mutation_inside_venv_is_detected_by_default_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("print('x')\n")
            before = runner.workspace_snapshot(root)
            venv = root / ".venv"
            venv.mkdir()
            (venv / "mutation.txt").write_text("agent wrote here\n")
            after = runner.workspace_snapshot(root)
            changes = runner.workspace_diff(before, after)
            changed_paths = {item["path"] for item in changes}
            self.assertIn(".venv/mutation.txt", changed_paths)

    def test_preflight_ignores_venv_symlinks_but_default_scan_reports_them(self):
        with tempfile.TemporaryDirectory() as temp_name, tempfile.TemporaryDirectory() as outside:
            root = Path(temp_name)
            venv_bin = root / ".venv" / "bin"
            venv_bin.mkdir(parents=True)
            (venv_bin / "python3").symlink_to(Path(outside) / "python3")
            # source-repo preflight: .venv symlink to system python is NOT an escape
            self.assertEqual(
                [], runner.escaping_workspace_symlinks(root, ignore_local=True)
            )
            # default (isolated-workspace) scan still sees and reports it
            default_escapes = runner.escaping_workspace_symlinks(root)
            self.assertEqual(
                [".venv/bin/python3"], [e["path"] for e in default_escapes]
            )
