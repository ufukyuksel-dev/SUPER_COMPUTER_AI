# Installing into Claude Code and Codex

`scripts/install.py` (stdlib only, Python 3.9+, macOS/Linux) links skills and roles from this checkout into the agent
homes and writes one managed block of global instructions. It never edits anything it does not own.

```sh
python3 scripts/install.py --list                 # bundles and what they contain (* = installed)
python3 scripts/install.py --dry-run              # print the plan, write nothing
python3 scripts/install.py                        # first run: all bundles; later runs: keep the selection
python3 scripts/install.py --bundle ads           # add a bundle (repeatable)
python3 scripts/install.py --remove-bundle media  # remove a bundle (items shared with other bundles stay)
python3 scripts/install.py --check                # 0 ok · 1 drift · 2 conflict · 4 blocked
python3 scripts/install.py --uninstall            # remove only what this installer owns
```

Open a **new** Claude Code / Codex session afterwards; running sessions keep their old skill list.

## Where things go

| Item | Claude Code | Codex |
|---|---|---|
| skill | `~/.claude/skills/<name>` | `~/.agents/skills/<name>` (`~/.codex/skills` only with `--codex-legacy-skills-dir`) |
| role | `~/.claude/agents/<role>.md` | `~/.codex/agents/<role>.toml` |
| instructions | block in `~/.claude/CLAUDE.md` | block in `~/.codex/AGENTS.md` |

`$CLAUDE_CONFIG_DIR` and `$CODEX_HOME` are honoured. Global instruction files may start with
`<!-- bundles: a, b -->` to be included only when one of those bundles is installed.

## Safety

- **Ownership.** Existing paths are changed only if the ownership record
  (`~/.local/state/super-computer-ai/ownership.json`) or a verified legacy installer record (AI_Developer,
  AI_SKILLS) says the installer owns them in exactly their current state. Anything else is a conflict and nothing
  is written. Text outside the managed block — for example AI_ORCHESTRATION's rules — is preserved byte for byte.
- **Journal.** Every run is a write-ahead journal (`~/.local/state/super-computer-ai/journals/`). If a run is
  interrupted, new runs are blocked until you choose:
  `python3 scripts/install.py --resume` or `python3 scripts/install.py --rollback <journal-file>`.
  Recovery never overwrites a path that changed outside the installer; it stops with a conflict instead.
- **Hand-copied skills** (e.g. an old `Mobile_UI_Review` directory) are never replaced silently. Review them with
  `python3 scripts/migrate_manual_skills.py`, then `python3 scripts/install.py --adopt-manual <skill>`; the
  directory is moved to `~/.local/state/super-computer-ai/backups/` and `--rollback` restores it.
- **No writing through symlinks.** If `~/.claude`, `~/.codex`, `~/.agents`, `~/.local` or any directory between
  them and a target is a symlink, the run stops with a conflict and writes nothing. If your client home really lives
  elsewhere (dotfiles setups), point `CLAUDE_CONFIG_DIR` / `CODEX_HOME` at it explicitly; configured roots are
  resolved and trusted.
- File and directory modes are part of the recorded state: rollback restores them, and a mode changed by hand is
  detected as a change.
- State files are private (directories `0700`, files `0600`). `--prune-state` deletes finished journals, blobs
  and backups.

## MCP servers (`--mcp`)

`--mcp` registers the MCP servers of the selected bundles (`mcp/registry.json`) in Claude Code (`~/.claude.json`,
user scope, or a project's local scope) and Codex (`~/.codex/config.toml`). The choice is remembered; `--no-mcp`
removes every entry the installer owns.

```sh
# close every Claude Code / Codex session and IDE extension first, then from a plain terminal:
python3 scripts/install.py --mcp --dry-run     # names and short hashes only, never values
python3 scripts/install.py --mcp
```

- **Clients must be closed.** Claude Code rewrites `~/.claude.json` constantly and has no lock, so the installer
  refuses (exit 4, nothing written) while a Claude Code or Codex process runs. Each entry is written with an atomic
  file swap; if another process still wrote the file in between, the run stops with a conflict and keeps both
  versions (live file = installer version, `.<file>.scai-swap-*` = the other version) for you to merge.
- **Per entry, never per file.** Only the installer's own entries change; every other byte (foreign servers, other
  settings, comments, AI_ORCHESTRATION) stays identical, and `--rollback` restores entries byte for byte.
- **Existing entries with the same name** (e.g. from an older setup) are a conflict; the message shows their
  fingerprint. After reviewing one, list it in the private `~/.config/super-computer-ai/private/migration/mcp_map.json`
  (`{"schema_version": 1, "entries": {"claude/user/<name>": {"sha256": "<fingerprint>"}}}`, add `"retire": true` to
  remove an old name) and rerun.
- **Instances.** By default each server gets one entry named after it (servers that need account-specific settings,
  like `google-ads`, get none). Account-specific instances live in the private overlay
  `~/.config/super-computer-ai/private/mcp/instances.json` — names, paths and IDs only, never secrets:

  ```json
  {"schema_version": 1, "instances": {
    "shop-ads": {"server": "google-ads", "env": {"GOOGLE_ADS_CONFIG": "~/.config/googleads/shop/config.json",
                                               "GOOGLE_ADS_CREDENTIAL_DIR": "~/.config/googleads/shop"},
                 "claude_scope": "local:~/Projects/Shop", "clients": ["claude", "codex"]}}}
  ```

  An installed instance whose definition disappears or breaks is never removed silently: remove it with
  `--remove-mcp <instance>`.
- **Launching.** Local servers start through `scripts/run_mcp.py` with a launch spec at
  `~/.local/state/super-computer-ai/mcp/instances.json`; secrets are read from
  `~/.config/super-computer-ai/credentials/<server>/.env` (must be `0600`; only the variables the registry marks
  `secret` are taken from it, other keys are ignored and named on stderr) and never appear in client configs.
  An instance's own settings always win over the shell, and for account-specific servers (e.g. `google-ads`) the
  wrapper drops inherited settings the instance does not set and every legacy alias, so an instance can never run
  with another account's exported configuration. Required settings must be present, non-empty and — for paths —
  absolute (or `~/…`).
- `--overlay DIR` and `$SCAI_HOME` move the private directory; `--python PATH` sets the interpreter written into the
  entries.

## Adding a skill

```sh
python3 scripts/new_skill.py <name> --category <category> --description "What it does. Use when ..."
python3 scripts/skills/validate_skills.py && python3 scripts/install.py
```
