# mcp

- `servers/<name>/` — MCP servers whose code lives here. Each is a self-contained project (own README, `.env.example`, tests, lockfile).
- `remote/<name>/` — hosted MCP servers we only configure (README + auth helper if needed).
- `registry.json` — the single catalog of servers (generic definitions: transport, build, launch, env schema,
  auth, skills, bundles). No instances, account data or secret values; `python3 scripts/install.py --mcp`
  generates client entries from it (see `docs/installing.md`). Checked by `tests/mcp/test_registry.py`.

| Server | Kind | Auth / secrets | Bundle |
|---|---|---|---|
| `premiere-pro` | local (Node) | none | video-editing |
| `google-ads` | local (Python/uv) | credential dir + account config (`GOOGLE_ADS_*`) | ads |
| `jev` (+ `jev-chrome`) | local (Python/uv) | `TYPESAFE_API_KEY` in `~/.config/super-computer-ai/credentials/jev/.env` | browser |
| `adb` | local (Kotlin/JDK 21) | none | mobile |
| `meta-ads` | remote (`mcp.facebook.com/ads`) | System User token file, `remote/meta-ads/auth_headers.py` | ads |
| `tiktok-ads` | remote (TikTok for Business) | client OAuth login, nothing stored here | ads |

### `registry.json` fields

| Field | Meaning |
|---|---|
| `kind` | `local` (code in `mcp/servers/<name>`) or `remote` (hosted; `mcp/remote/<name>` holds the README and any helper) |
| `transport` | `stdio` (local) or `http` (remote) |
| `path`, `runtime`, `build` | where a local server lives, what it needs, how to build it (`build` runs in `path`) |
| `launch` | `command` (resolved on `PATH` at install time) and `args`; the installer replaces `{path}` with the server's absolute path and `{client}` with `claude` or `codex` — nothing else is rewritten |
| `variants` | extra client entries of the same server with other `args` (e.g. `jev-chrome`) |
| `env` | variables the server reads: `required`, `secret` (never written to any client config, registry or overlay; lives in `~/.config/super-computer-ai/credentials/<server>/`), `kind: path`, `default` |
| `legacy_env`, `legacy_names` | deprecated variable names still read, and old client entry names |
| `auth` | remote servers: `oauth` (the client's login flow) or `headers_helper` (a local command printing JSON headers; `argument` describes its token-file argument) |
| `prerequisites`, `docs` | what must exist on the machine; the remote server's README |
| `skills`, `bundles` | the agent workflow for the server and the installer bundles it belongs to |
| `external` (top level) | servers used alongside but not shipped or configured here |

Instances (one client entry each — e.g. one `google-ads` entry per account) never live in this repository; they come
from the private overlay (`~/.config/super-computer-ai/private/mcp/instances.json`) or default to one per server.

Secrets are never stored here. See `SECURITY.md`.
