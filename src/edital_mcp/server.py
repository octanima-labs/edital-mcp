"""Stdio MCP server; terminal rendering is owned by the separate helper."""

from mcp.server.fastmcp import FastMCP

from .config import load
from .session import edit


def create_server(config_path: str | None = None) -> FastMCP:
    server = FastMCP("edital")

    @server.tool()
    async def edital(title: str, initial_text: str = "") -> dict[str, str | None]:
        """Collect a user answer in a new terminal window, optionally preloaded with a draft.

        Waits for acceptance or cancellation. Accepted empty/unchanged text is valid.
        Returns exact user-supplied text; does not save files or perform subsequent actions.
        Requires a configured local desktop terminal and a human-paced client timeout.
        """
        return await edit(load(config_path), title, initial_text)

    return server
