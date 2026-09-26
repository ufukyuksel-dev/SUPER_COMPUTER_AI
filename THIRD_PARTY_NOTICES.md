# Third-Party Notices

Code in this repository that originates from third parties keeps its original license file in its own
directory. Each entry records the upstream source, the base revision and a summary of local changes.

## Imported

- `third_party/openai-skill-creator/` — OpenAI `skill-creator` scripts (`quick_validate.py`, `generate_openai_yaml.py`,
  `init_skill.py`), Apache License 2.0 (`LICENSE.txt` in that directory). Unmodified copies; provenance and checksums in
  its README and `SHA256SUMS`.

- `mcp/servers/premiere-pro/` — Adobe Premiere Pro MCP by hetpatel-11 and contributors,
  upstream `https://github.com/hetpatel-11/Adobe_Premiere_Pro_MCP`, **MIT License** (`LICENSE.md` in that directory).
  Base revision: upstream `ee31c3d` (2026-09-03). Local changes carried over from the private fork:
  `9685f2f` (private per-user bridge directory, command-file ownership checks, ExtendScript escape-hatch blocklist,
  telemetry and update check off by default, unused `ws`/`path` dependencies dropped) and `5b6281a` (never delete the
  shared bridge directory on cleanup, `validateScript` ignores string literals/comments, tests use a private temp
  dir). Changed on import: a machine-specific absolute link in `CONTRIBUTING.md` made relative; a short provenance note
  prepended to `README.md`; `.env.example` added; `scripts/install-macos.sh` gained `--skip-client-config` (install the
  CEP panel without editing MCP client config) and `package.json` a matching `setup:cep` script. Not imported: `website/`, `translations/`, `telemetry/` (Cloudflare
  backend), `marketplace-assets/`, marketplace/plugin packaging (`.agents/`, `.claude-plugin/`, `claude-plugins/`,
  `plugins/`, `.cursor/`), upstream CI (`.github/`), `.idea/`.
- `skills/media/premiere-pro-mcp/` — derived from upstream `skills/premiere-pro-mcp/SKILL.md` (same MIT license and
  authors); bridge directory, registration commands and tool-surface notes updated to this repository and fork.

## Planned (Phase 2)

- none
