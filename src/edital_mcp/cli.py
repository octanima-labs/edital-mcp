"""CLI dispatch; editor imports happen only for configuration or the helper."""

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="New-window Edital answers through MCP")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Run the stdio MCP server")
    serve.add_argument("--config", help="Bridge or compatible Skillsmith TOML configuration")
    conf = commands.add_parser("conf", help="Create or edit terminal configuration")
    conf.add_argument("-r", "--reset", action="store_true",
                      help="Restore the template, backing up an existing configuration")
    conf.add_argument("-t", "--term", help="Terminal example to activate on creation/reset (then TERM)")
    helper = commands.add_parser("_helper", help="Internal terminal helper (not a user command)")
    helper.add_argument("endpoint")
    options = parser.parse_args(argv)
    if options.command == "serve":
        from .server import create_server

        try:
            server = create_server(options.config)
        except ValueError as exc:
            print(f"edital-mcp: {exc}", file=sys.stderr)
            return 1
        server.run(transport="stdio")
        return 0
    if options.command == "conf":
        from .config import configure

        try:
            configure(reset=options.reset, term=options.term)
        except (OSError, ValueError, RuntimeError) as exc:
            print("edital-mcp: configuration setup failed; check file permissions and run "
                  "in an interactive terminal", file=sys.stderr)
            for note in getattr(exc, "__notes__", ()):
                print(note, file=sys.stderr)
            return 1
        return 0
    try:
        from .helper import run

        return run(options.endpoint)
    except Exception:  # noqa: BLE001 - keep user content out of operational diagnostics
        print("edital-mcp: terminal helper failed", file=sys.stderr)
        return 1
