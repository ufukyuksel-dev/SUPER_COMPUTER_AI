"""Spec §5.5 (protocol level): start jev-mcp over stdio like Claude Code/Codex would and call the tools."""

import json

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from conftest import PROJECT_ROOT, fixture_url, needs_jev


def _payload(result):
    if getattr(result, "structured_content", None):
        return result.structured_content
    return json.loads(result.content[0].text)


@needs_jev
async def test_mcp_stdio_open_and_do():
    params = StdioServerParameters(
        command="uv",
        args=["--directory", str(PROJECT_ROOT), "run", "jev-mcp", "--profile", "mcptest", "--headless"],
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = {t.name for t in (await session.list_tools()).tools}
        assert {"jev_open", "jev_do", "jev_look", "jev_read"} <= tools
        opened = _payload(await session.call_tool("jev_open", {"url": fixture_url("index.html")}))
        assert opened["title"] == "Ana Sayfa"
        result = _payload(await session.call_tool(
            "jev_do", {"goal": "Reklam Yöneticisi sayfasına git", "max_steps": 6, "expect": "manager.html"}))
        print(result)
        assert result["reached"] is True
