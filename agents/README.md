# agents

Agent roles. Keep Claude and Codex role boundaries equivalent even when file formats differ.

- `claude/<role>.md` — Claude Code subagents
- `codex/<role>.toml` — Codex agents (narrow schema; see `tests/behavior/results/event-taxonomy.md`)
- `manifest.json` — every role with its `platforms` and install `bundles`

| Role | Purpose | Bundle |
|---|---|---|
| `researcher` | primary-source evidence, no architecture decisions | `ai-engineering` |
| `architect` | architecture, plan, acceptance criteria from approved requirements | `ai-engineering` |
| `implementer` | executes an approved plan with the named specialist skills | `ai-engineering` |
| `evaluator` | exercises a deliverable against criteria, reports unverified claims | `ai-engineering` |
| `dataset-curator` | rights-clean, leakage-safe datasets with quality gates | `ai-engineering` |

`python3 scripts/skills/validate_skills.py` checks that manifest and files agree.
