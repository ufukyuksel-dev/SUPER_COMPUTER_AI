---
name: premiere-pro-mcp
description: Install, verify, troubleshoot, and operate the Adobe Premiere Pro MCP server. Use when a user wants an agent to set up Premiere MCP, connect Claude Code/Codex/Claude Desktop, control Premiere, import media, build sequences, edit timelines, apply effects, or diagnose bridge issues.
---

# Adobe Premiere Pro MCP

Use this skill when working with the Adobe Premiere Pro MCP server in SUPER_COMPUTER_AI (`mcp/servers/premiere-pro`), a hardened fork of `hetpatel-11/Adobe_Premiere_Pro_MCP` (MIT). In this fork telemetry and the npm update check are off by default and the bridge directory is private per user.

## Core Rules

- Use the MCP tools for Premiere operations; do not invent ExtendScript unless the MCP tool surface is missing the needed operation.
- Default MCP `tools/list` is a small always-on set. Call `search_tools` (BM25 query or regex pattern), then `invoke_tool` with the exact name. `PREMIERE_MCP_TOOLSET=full` lists every tool.
- Prefer read-only discovery first: `get_project_info`, `list_sequences`, `list_project_items`, `get_active_sequence`, and relevant resource reads.
- Use real imported media. If the user asks to edit with assets, verify file paths exist, import them with `import_media`, then place the imported project item IDs on a sequence.
- Keep the temp directory consistent across the MCP server and CEP panel: `~/.premiere-mcp-bridge/bridge` unless the user explicitly configured another path.
- Ask before destructive or externally visible actions: deleting clips/media, overwriting exports, closing projects, saving over important project files, or sending files elsewhere.
- For generated/demo edits, prefer creating a new clearly named sequence instead of modifying the user's active sequence.
- If a tool returns `success: false`, report the exact error and run diagnostics before retrying blindly.

## Install Workflow

If the user asks you to install or set up the MCP:

1. Check the OS. The automated installer is macOS-focused.
2. Open the server inside the SUPER_COMPUTER_AI checkout:

```bash
cd <SUPER_COMPUTER_AI>/mcp/servers/premiere-pro
```

3. On macOS, install only the CEP panel and bridge directory (this does **not** touch any MCP client config):

```bash
npm ci && npm run build
npm run setup:cep
```

   Do not use `npm run setup:mac` or `premiere-pro-mcp --install-cep` here: both rewrite the Claude Desktop MCP
   config directly, bypassing the SUPER_COMPUTER_AI installer's ownership checks and journal.

4. For non-macOS or manual client setup, run:

```bash
npm ci
npm run build
```

5. Register the MCP server. MCP client registration belongs to the SUPER_COMPUTER_AI installer: the user runs
   `python3 scripts/install.py --mcp` from a plain terminal with Claude Code and Codex closed (it refuses to write
   client configs while they run). Never edit client configs yourself. Keep an existing registration as it is; if the
   installer reports it as not owned, the user decides whether to hand it over. For reference, the entry it creates
   is equivalent to:

```text
command: node <SUPER_COMPUTER_AI>/mcp/servers/premiere-pro/dist/index.js
env: PREMIERE_TEMP_DIR=~/.premiere-mcp-bridge/bridge
```

For Codex, prefer:

```bash
codex mcp add premiere_pro --env PREMIERE_TEMP_DIR=~/.premiere-mcp-bridge/bridge -- node <SUPER_COMPUTER_AI>/mcp/servers/premiere-pro/dist/index.js
```

## Premiere Bridge Startup

After installing:

1. Restart the MCP client if it reads config only at startup.
2. Restart Premiere Pro.
3. Open `Window > Extensions > MCP Bridge (CEP)`.
4. Set `Temp Directory` to `~/.premiere-mcp-bridge/bridge`.
5. Click `Save Configuration`.
6. Click `Start Bridge`.
7. Confirm the bridge panel says Premiere is ready before running editing tools.

If Premiere is not running, you can install/build/register the MCP, but tell the user live tool verification requires Premiere and the CEP bridge panel.

## Verification

Run local checks:

```bash
npm run setup:doctor
```

If Premiere is running and the bridge is started, verify with safe read-only calls:

- `get_project_info`
- `list_sequences`
- `list_project_items`

For deeper validation in a disposable project, create a test sequence with `create_sequence_from_clips` or `create_sequence` plus a real `.sqpreset` path, then call `list_sequences` and confirm it exists. Do not call blank sequence creation without a preset because newer Premiere versions can open a native dialog that blocks CEP.

## Editing Strategy

- Start by understanding the project: project info, active sequence, existing media, tracks, markers, and selected sequence.
- Build a plan in concrete Premiere operations before changing anything.
- For rough cuts, import media first, then use `create_sequence_from_clips` so Premiere derives settings without a native dialog. Use `create_sequence` only with a real `.sqpreset`; use `duplicate_sequence` with `clearContents=true` when an existing sequence defines the intended settings.
- For product or brand spots, prefer `assemble_product_spot` or `build_brand_spot_from_mogrt_and_assets` when the user's request fits those workflows.
- For black-and-white looks, use `apply_effect` with `Black & White` rather than generic saturation-only changes.
- For timeline cuts, prefer sequence-aware tools and include `sequenceId` when available.
- Export only after confirming output path, format/preset, and overwrite behavior.

## Troubleshooting

If commands time out or report bridge errors:

1. Confirm Premiere is open.
2. Confirm `Window > Extensions > MCP Bridge (CEP)` is open and bridge is started.
3. Confirm both sides use the same temp directory.
4. Run:

```bash
npm run setup:doctor
```

5. Ask the user to click `Run Diagnostics` in the CEP panel.
6. Read `~/.premiere-mcp-bridge/bridge/premiere-mcp-diagnostics-latest.json` if it exists.
7. Remove stale command/response files only if they are clearly old and the bridge is stopped or idle.

Common fixes:

- `ENOENT` on temp directory: create `~/.premiere-mcp-bridge/bridge`, save config again, restart bridge.
- Tool succeeds in Premiere but reports failure: run `list_sequences` or the relevant list tool to confirm state before retrying.
- Empty or malformed temp directory config: set the field to the path only, not JSON or an env assignment.
