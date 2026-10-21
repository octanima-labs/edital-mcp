import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client


def parameters(tmp_path: Path) -> StdioServerParameters:
    config = tmp_path / "config.toml"
    config.write_text("[terminal]\ncommand = " + json.dumps([
        sys.executable, str(Path(__file__).with_name("pty_terminal.py")), "{cwd}", "{argv}"]))
    return StdioServerParameters(command=sys.executable,
        args=["-m", "edital_mcp", "serve", "--config", str(config)],
        env={**os.environ, "DISPLAY": ":test", "PTY_RECORD": str(tmp_path / "helper")})


async def wait_for_file(path: Path) -> None:
    async with asyncio.timeout(8):
        while not path.exists():
            await asyncio.sleep(0.02)


async def test_protocol_cancel_stops_actual_editor(tmp_path: Path) -> None:
    async with stdio_client(parameters(tmp_path)) as (reader, writer):  # noqa: SIM117
        async with ClientSession(reader, writer) as client:
            await client.initialize()  # request id 0; next explicit request has id 1
            request = asyncio.create_task(client.send_request(
                types.ClientRequest(types.CallToolRequest(params=types.CallToolRequestParams(
                    name="edital", arguments={"title": "Cancel through MCP", "initial_text": "draft"}))),
                types.CallToolResult))
            await wait_for_file(tmp_path / "helper")
            await asyncio.sleep(0.5)
            await client.send_notification(types.ClientNotification(types.CancelledNotification(
                params=types.CancelledNotificationParams(requestId=1, reason="test cancellation"))))
            await wait_for_file(tmp_path / "helper.exit")
            assert (tmp_path / "helper.exit").read_text() == "0"
            request.cancel()
            await asyncio.gather(request, return_exceptions=True)
            assert [tool.name for tool in (await client.list_tools()).tools] == ["edital"]


@pytest.mark.parametrize("abrupt", [False, True])
async def test_server_loss_stops_actual_editor(tmp_path: Path, abrupt: bool) -> None:
    options = parameters(tmp_path)
    process = await asyncio.create_subprocess_exec(options.command, *options.args,
        env=options.env, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL)
    assert process.stdin is not None and process.stdout is not None
    try:
        process.stdin.write((json.dumps({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "lifecycle-test", "version": "1"}}}) + "\n").encode())
        await process.stdin.drain()
        await asyncio.wait_for(process.stdout.readline(), 5)
        for message in [
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                "name": "edital", "arguments": {"title": "Server loss", "initial_text": "draft"}}},
        ]:
            process.stdin.write((json.dumps(message) + "\n").encode())
        await process.stdin.drain()
        await wait_for_file(tmp_path / "helper")
        await asyncio.sleep(0.5)
        if abrupt:
            process.kill()
        else:
            process.stdin.close()
        await asyncio.wait_for(process.wait(), 5)
        await wait_for_file(tmp_path / "helper.exit")
        assert (tmp_path / "helper.exit").read_text() == "0"
        endpoint = Path((tmp_path / "helper.endpoint").read_text())
        assert not endpoint.exists()
        assert not endpoint.parent.exists()
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
