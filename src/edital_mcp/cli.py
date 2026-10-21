"""Non-interactive command dispatch; UI imports happen only in the helper."""

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="New-window Edital answers through MCP")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Run the stdio MCP server")
    serve.add_argument("--config", help="Bridge or compatible Skillsmith TOML configuration")
    helper = commands.add_parser("_helper", help="Internal terminal helper (not a user command)")
    helper.add_argument("endpoint")
    options = parser.parse_args(argv)
    if options.command == "serve":
        from .server import create_server

        create_server(options.config).run(transport="stdio")
        return 0
    try:
        from .helper import run

        return run(options.endpoint)
    except Exception:  # noqa: BLE001 - keep user content out of operational diagnostics
        print("edital-mcp: terminal helper failed", file=sys.stderr)
        return 1
