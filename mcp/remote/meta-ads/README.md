# meta-ads (remote MCP)

Meta's official, hosted Ads MCP server at `https://mcp.facebook.com/ads`. We ship no server code — only
`auth_headers.py`, a headers helper that turns a Meta **System User access token** stored in a private file into an
`Authorization` header. Agent workflow: skill `meta-ads-management` (bundle `ads`).

## Credential

1. In Meta Business Manager create (or reuse) a System User, assign it only the ad accounts, pages and apps it
   should manage, and generate a token with the ads permissions you need.
2. Store the token — nothing else — in a file only you can read:

   ```sh
   install -d -m 700 ~/.config/super-computer-ai/credentials/meta-ads
   ( umask 077 && pbpaste > ~/.config/super-computer-ai/credentials/meta-ads/system-user-token.txt )
   ```

The helper refuses a file that group/others can read or write, a non-regular file, and anything that does not look
like a Meta token; its error message never contains the token. Its stdout *is* the credential — never log it.
Use a different file per account/instance and pass its path as the helper's argument.

## Register

`python3 scripts/install.py --mcp` (close Claude Code and Codex first; see `docs/installing.md`) writes these entries from `mcp/registry.json` (default instance: the token file below;
other files/accounts: overlay instances with `helper_args`). By hand, under
`mcpServers` in `~/.claude.json` (user scope) or a project's `.mcp.json`:

```json
"meta-ads": {
  "type": "http",
  "url": "https://mcp.facebook.com/ads",
  "headersHelper": "python3 <repo>/mcp/remote/meta-ads/auth_headers.py"
}
```

```toml
# ~/.codex/config.toml
[mcp_servers.meta-ads]
url = "https://mcp.facebook.com/ads"
http_headers_helper = "python3 <repo>/mcp/remote/meta-ads/auth_headers.py"
# optional: expose only the tools you use, e.g.
enabled_tools = [
  "ads_get_ad_accounts", "ads_get_ad_entities", "ads_get_field_context", "ads_account_get_activity_logs",
  "ads_get_ad_account_pages", "ads_get_pages_for_business", "ads_get_ig_accounts", "ads_get_creatives",
  "ads_get_ad_preview", "ads_create_campaign", "ads_create_ad_set", "ads_create_ad", "ads_create_creative",
  "ads_update_entity", "ads_activate_entity", "ads_creative_update", "ads_creative_upload_media",
  "ads_creative_upload_local_image", "ads_finalize_local_ad_image_upload", "ads_get_ad_images",
  "ads_get_ad_videos", "ads_get_creative_ads", "ads_get_errors", "ads_get_user_pages",
  "ads_get_help_article"
]
```

Append a token-file path to the helper command for a non-default file. Claude Code runs the helper through a shell
(10 s timeout) on every connection and again after a 401/403; for project/local-scope servers it runs only after you
trust the folder and strips credential-like environment variables — which is why the path is an argument.

## Rotate

Generate a new System User token, overwrite the file (same mode), reconnect the server (`/mcp` in Claude Code;
restart Codex). No client configuration changes.

## References

- [Meta Ads MCP server overview](https://developers.facebook.com/documentation/ads-commerce/ads-ai-connectors/ads-mcp-server/ads-mcp-server-overview)
- [Claude Code: MCP headers helper](https://code.claude.com/docs/en/mcp), [Codex config reference](https://learn.chatgpt.com/docs/config-file/config-reference) (checked 2026-09-25 with Claude Code 2.1.282 and codex-cli 0.155.1)
