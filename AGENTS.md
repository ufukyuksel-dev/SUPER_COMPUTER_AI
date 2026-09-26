# SUPER_COMPUTER_AI — Working Rules

This repository is the single home for AI agent skills, agent roles, instructions and MCP servers used with
Claude Code and Codex. `CLAUDE.md` imports this file; do not duplicate rules there.

## Where things go

| You are adding | Put it in | Also update |
|---|---|---|
| A skill | `skills/<category>/<skill-name>/SKILL.md` (+ `references/`, `agents/openai.yaml`) | `skills/manifest.json` |
| An agent role | `agents/claude/<role>.md` and `agents/codex/<role>.toml` | `agents/README.md` |
| An instruction | `instructions/global/` (all sessions), `instructions/pipeline/`, or `instructions/projects/` | — |
| An MCP server (our code) | `mcp/servers/<name>/` with its own README, `.env.example`, tests and lockfile | `mcp/registry.json` |
| A hosted MCP (not our code) | `mcp/remote/<name>/` (README + auth helper if needed) | `mcp/registry.json` |
| A helper tool | `tools/<name>/` | — |

Names are kebab-case. Skill names are globally unique regardless of category.

## Public-repo rules (non-negotiable)

- Never commit secrets, tokens, API keys, `.env` files, account/customer IDs, e-mail addresses, browser profiles,
  or machine-specific absolute paths (`/Users/...`, `/home/...`).
- Credentials live in `~/.config/super-computer-ai/credentials/<server>/` (dir `0700`, files `0600`).
  Sensitive project values live in `~/.config/super-computer-ai/private/`. Commit only variable names and
  `.env.example` files.
- Migrations from other repositories copy only files on an explicit, reviewed allowlist.
- Run `python3 scripts/validate.py` and `python3 scripts/skills/validate_skills.py` before every commit; CI runs
  both plus a gitleaks scan.

## Installing into Claude Code / Codex

Never hand-edit `~/.claude`, `~/.codex` or `~/.agents`. The installer (`scripts/install.py`, see `docs/installing.md`) links
skills and roles and writes the managed instruction block. Projects outside this repo's scope
(e.g. AI_ORCHESTRATION) are never touched by the installer.

## Working agreements

- Plans and design decisions are written to files; implementation follows an approved plan.
- Coder and reviewer roles are assigned per task by the human; the coder sends changes for peer review.
- Do not initialize, commit, push or rewrite Git history without explicit human approval.
- Evidence before assertions: run the deliverable, record the command and result, mark anything not
  exercised as `UNVERIFIED`.
