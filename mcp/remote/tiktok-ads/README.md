# tiktok-ads (remote MCP)

TikTok's official, hosted **TikTok for Business MCP server**. Endpoint (progressive-disclosure layer: a core tool set,
the rest discovered on demand): `https://business-api.tiktok.com/open_mcp/tt-ads-mcp-layer`. Agent workflow: skill
`tiktok-ads-management` (bundle `ads`).

## Authentication — OAuth, nothing stored by this repository

The server uses standard MCP OAuth: an unauthenticated request gets `401` with a `WWW-Authenticate` header that points
to its protected-resource metadata (authorization server `…/tt-ads-mcp-layer/oauth`, scope `mcp:tt4b`). Your MCP
client runs the browser consent flow with your ordinary TikTok for Business account (no developer app needed) and
keeps the token in its own credential store. The authorization lasts **30 days**; then log in again with the same
account.

## Register and log in

```sh
claude mcp add --transport http tiktok-ads https://business-api.tiktok.com/open_mcp/tt-ads-mcp-layer
claude mcp login tiktok-ads          # or /mcp inside a session
```

```toml
# ~/.codex/config.toml
[mcp_servers.tiktok-ads]
url = "https://business-api.tiktok.com/open_mcp/tt-ads-mcp-layer"
```

```sh
codex mcp login tiktok-ads
```

`python3 scripts/install.py --mcp` (close Claude Code and Codex first; see `docs/installing.md`) writes the entries from `mcp/registry.json`; logging in stays a
manual, per-client step.

## References

- [TikTok API for Business: MCP server](https://business-api.tiktok.com/portal/docs/tiktok-ads-mcp-server/v1.3)
- [About TikTok for Business MCP Server](https://ads.tiktok.com/resources/help/article/about-tiktok-for-business-mcp-server?lang=en)
- Protected-resource metadata observed 2026-09-25: `https://business-api.tiktok.com/.well-known/oauth-protected-resource/open_mcp/tt-ads-mcp-layer`
