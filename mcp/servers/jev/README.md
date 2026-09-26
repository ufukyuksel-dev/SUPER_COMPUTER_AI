# jev MCP

"Jev picks, Chrome clicks": a browser-control MCP server where TypeSafe **Jev** (System One) chooses which on-page
element to act on and Playwright/Chrome executes it; the calling agent may take over single steps when Jev is unsure.
Python 3.12, `mcp` 2.2.0, Playwright 1.63, `typesafe-sdk` 0.7.1. Agent workflow: skill `jev-browser` (bundle `browser`).

> Imported into SUPER_COMPUTER_AI from the private `JevAI` project (2026-09): product code and tests only. Design
> notes, benchmarks, spike scripts, run logs, browser profiles and the `.env` file were not imported.

## Run and test

```sh
cd mcp/servers/jev
uv sync --locked
uv run playwright install chromium      # once, for the test suite
uv run --locked pytest -q               # hermetic: live Jev tests are skipped without an explicit key
uv run --locked jev-mcp --profile mcp   # stdio MCP (own Chrome window)
uv run --locked jev-mcp --backend extension   # drive the user's Chrome via the Playwright MCP extension
```

Options: `--profile <name>` (separate persistent Chrome profile), `--headless`, `--backend own|extension`,
`--jev-first`. Register `jev` and `jev-chrome` with `python3 scripts/install.py --mcp` (close Claude Code and Codex first; see `docs/installing.md`).

## Secrets and state — never in the repository

| What | Where (override) |
|---|---|
| `TYPESAFE_API_KEY`, `PLAYWRIGHT_MCP_EXTENSION_TOKEN` | `~/.config/super-computer-ai/credentials/jev/.env` (`JEV_ENV_FILE`); read only if the file exists, exported values win |
| Chrome profiles (`chrome-profile-<name>`, cookies and sessions), task/run/takeover logs | `~/.local/state/super-computer-ai/jev` (`JEV_STATE_DIR`), created with mode 0700 |

See `.env.example`. The test suite sets a throwaway `JEV_STATE_DIR` and loads no secrets unless you opt in
(`JEV_ENV_FILE=… pytest` or an exported `TYPESAFE_API_KEY`); the live Jev tests make paid API calls.
