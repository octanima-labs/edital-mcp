import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_stdio_sdk_roundtrip(tmp_path: Path) -> None:
    terminal = str(Path(__file__).with_name("fake_terminal.py"))
    config = tmp_path / "config.toml"
    config.write_text("[terminal]\ncommand = " + json.dumps(
        [sys.executable, terminal, "{cwd}", "{argv}"]))
    parameters = StdioServerParameters(command=sys.executable,
        args=["-m", "edital_mcp", "serve", "--config", str(config)],
        env={**os.environ, "DISPLAY": ":test"})
    async with stdio_client(parameters) as (reader, writer):  # noqa: SIM117 - session uses opened streams
        async with ClientSession(reader, writer) as client:
            await client.initialize()
            tools = await client.list_tools()
            assert [tool.name for tool in tools.tools] == ["edital"]
            assert tools.tools[0].inputSchema["required"] == ["title"]
            for mode, expected in [("accept", " exact\n"), ("empty", ""), ("cancel", None)]:
                answer = await client.call_tool("edital", {"title": mode, "initial_text": " exact\n"})
                assert not answer.isError
                assert answer.structuredContent == {
                    "outcome": "cancelled" if mode == "cancel" else "accepted", "text": expected}
            failure = await client.call_tool("edital", {"title": "disconnect", "initial_text": "secret"})
            assert failure.isError
            assert "secret" not in str(failure.content)
