# Behavior Event Taxonomy

Observed on 2026-08-24 with Claude Code `2.1.238` and Codex CLI `0.144.0`.
This document is the allow-list behind `scripts/run_behavior_tests.py`; routing
is never inferred from response prose or from an LLM judge.

Normalized live records are `probe-claude.json` and `probe-codex.json` in this
directory. The parser unit suite reads those records directly so taxonomy drift
cannot silently become a routing pass.

## Claude Code: routing evidence supported

Probe command, exactly as recorded in `probe-claude.json`:

```text
claude -p --no-session-persistence --permission-mode plan --output-format stream-json --verbose 'Use $probe-skill. Reply exactly: PROBE-OK'
```

The command exited `0`, selected model `claude-opus-5[1m]`, invoked the
project skill, and returned `PROBE-OK`.

| Claim | Accepted event shape | Observed value |
|---|---|---|
| discovery | `type == "system"`, `subtype == "init"`, exact skill name in `skills[]` | `probe-skill` |
| explicit execution | `type == "assistant"`; a `message.content[]` block has `type == "tool_use"`, `name == "Skill"`, and `input.skill` equal to the exact skill name | `probe-skill` |
| execution corroboration | `type == "user"`, `tool_use_result.success == true`, and `tool_use_result.commandName` equals the exact skill name | `probe-skill` |
| loaded content | synthetic `type == "user"` message contains the loaded skill body and its project base directory | `.claude/skills/probe-skill` |
| final output | `type == "result"`, `subtype == "success"`, `result` contains the final response | `PROBE-OK` |

Only the first row proves `discovery`. The `Skill` `tool_use` row proves
`explicit-execution`; its tool result is retained separately under
`execution-corroboration` and can never satisfy that evidence class by itself.
Loaded content and final response text do not independently prove routing.

## Codex CLI: routing evidence unsupported

Required probe command, normalized exactly as recorded in `probe-codex.json`
with `<repo>` standing for this workspace's absolute path:

```text
codex exec --ephemeral -C <repo> -s read-only --skip-git-repo-check --json 'Use $probe-skill. Reply exactly: PROBE-OK'
```

The supported `--skip-git-repo-check` flag keeps Git initialization optional, as
required by the plan. The command exited `0`, completed a model turn, and
returned `PROBE-OK`. Its JSONL event types were:

```text
thread.started
turn.started
item.completed (agent_message only)
turn.completed (usage only)
```

No event listed available skills, loaded `probe-skill`, or recorded an explicit
skill invocation. `item.completed.item.text == "PROBE-OK"` is final behavioral
output only. The prompt itself requested that exact text, so it cannot prove
skill routing.

Codex routing evidence is therefore `unsupported`. The parser accepts no Codex
routing event shapes. Codex response text or a passing behavioral rubric is
never promoted to discovery or explicit-execution evidence.

`ACTION: ask` — revise the affected cross-platform routing acceptance criteria
with the human. Behavioral-compliance can still be measured on Codex, but it
cannot be relabeled as routing evidence.

## Headless role selection capability

This is kept separate from skill routing evidence. Claude Code `2.1.238`
exposes `--agent <agent>` and the runner uses it for `agents/claude/<role>.md`
fixtures. A successful process selected with that flag is recorded as role
selection evidence; the role-boundary behavior is still judged separately.

Codex CLI `0.144.0` exposes no top-level `--agent` selector. Its official
configuration schema nevertheless supports `developer_instructions`,
`sandbox_mode`, and `sandbox_workspace_write.network_access` for a primary
session. The runner parses a deliberately narrow checked-in
`agents/codex/<role>.toml` contract, rejects unknown or unapplied fields,
rejects TOML escapes/control syntax outside its literal-text subset, preserves
the accepted multiline instruction value exactly, injects it with `-c`,
and applies the sandbox with `-s` plus the network override. `name` and
`description` are validated identity metadata; they are not claimed as applied
session fields. Model-free `codex debug prompt-input` probes for all four roles
confirmed that their injected instructions are model-visible, with config and
instruction SHA-256 values retained by full runs.

This is `primary-session-config-overrides`, not native custom-agent discovery,
spawn, thread isolation, inheritance, or summary lifecycle; those native-agent
claims remain `UNVERIFIED`. Role subjects run in per-run temporary repository
copies, and entry type/mode/symlink target/file SHA-256 snapshots gate every
fixture's `workspace_changes` policy. The behavioral judge remains a separate
required gate. `network_access=false` controls sandboxed commands only; it does
not disable web, apps, MCP, browser, or other product capabilities. None of this
changes the `unsupported` Codex *skill event taxonomy* above.

## Judge isolation

Judge processes run in a new empty temporary directory outside the repository.
In addition, the Claude command uses `--safe-mode` to disable CLAUDE.md, skills,
plugins, hooks, MCP servers, custom commands, agents, and other customizations.
An empty cwd plus temporary `CODEX_HOME` removes global AGENTS content,
repository skills, and user custom skills, but a model-free `codex debug
prompt-input` check confirmed that Codex `0.144.0` still injects built-in system
skills. Because those cannot be disabled, Codex is not accepted as a strict
rubric judge. The runner defaults to Claude `--safe-mode` for both platforms'
subject outputs and rejects any configuration that would resolve the judge to
Codex. Codex remains fully in scope as a subject platform; only the independent
rubric judgment is delegated to the strictly isolated Claude process. This
limitation and enforcement were verified locally on 2026-08-24.
