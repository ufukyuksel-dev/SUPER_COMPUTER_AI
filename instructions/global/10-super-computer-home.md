## SUPER_COMPUTER_AI is the single home

New skills, agent roles, instructions and MCP servers, and changes to them, are made only in the
`SUPER_COMPUTER_AI` repository:

- skill → `skills/<category>/<name>/` + `skills/manifest.json`
- agent role → `agents/claude/` and `agents/codex/`
- instruction → `instructions/`
- MCP server → `mcp/servers/<name>/` (or `mcp/remote/<name>/`) + `mcp/registry.json`

Do not hand-edit files under `~/.claude`, `~/.codex` or `~/.agents`; run `python3 scripts/install.py`.
Never commit secrets, tokens, account data or machine-specific absolute paths. Credentials go to
`~/.config/super-computer-ai/credentials/`, sensitive project values to `~/.config/super-computer-ai/private/`.
Run `python3 scripts/validate.py` after changes.

AI_ORCHESTRATION is a separate project; its server, skills and instructions stay in its own repository.
