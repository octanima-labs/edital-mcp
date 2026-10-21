# edital-mcp

A local MCP server that collects a multiline answer in a new terminal window.
Requires Python 3.11+, Edital 0.3.x, and a local Linux desktop with a terminal emulator.

## Installation

Install from the public Git repository:

```sh
pipx install git+https://github.com/octanima-labs/edital-mcp.git
```

For a local development checkout:

```sh
pipx install /absolute/path/to/edital-mcp
```

The package owns its Edital dependency; no standalone Edital installation is required.
Start the stdio server with `edital-mcp serve`. `edital-mcp --help` is non-interactive.
No PyPI distribution is currently published; use the Git source or a local checkout.

## Terminal configuration

Create `~/.config/edital-mcp/config.toml` (respecting `XDG_CONFIG_HOME`):

```toml
[terminal]
command = ["alacritty", "--working-directory", "{cwd}", "-e", "{argv}"]

[session]
startup_timeout = 15.0
```

Each placeholder must occur exactly once as a whole argument. Commands run directly
without shell expansion. The working directory is inherited from the MCP server.
Only initial helper startup has a deadline; established editing has no bridge deadline.

Configuration selection is `serve --config PATH`, then `EDITAL_MCP_CONFIG`, then
the default configuration above. An explicit missing or invalid file is an error.
To reuse Skillsmith settings without installing Skillsmith into this environment:

```sh
edital-mcp serve --config "$HOME/.config/skillsmith/config.toml"
```

Alternatively set `EDITAL_MCP_CONFIG` in the MCP server's environment. Only the
relevant terminal/session settings are read, so other Skillsmith settings are preserved.

## Tool contract

`edital(title, initial_text="")` waits for a user answer. F2/F3 accepts and closes;
Ctrl+Q cancels (with confirmation when edited); Escape dismisses dialogs/search.

Acceptance returns `{"outcome":"accepted","text":"exact answer"}`. Empty and
unchanged answers are valid. Cancellation returns `{"outcome":"cancelled","text":null}`.
Whitespace, comments, Unicode, trailing newlines, and uniform LF/CRLF are preserved.
Mixed line endings and bare carriage returns are rejected.

The tool collects an answer; it does not save a project file, execute content, or
commit. It does not restore or cache standalone Edital documents. Launch failure,
lost helper connections, and unexpected window closure are tool errors, not user
cancellation. Errors and routine logs exclude draft and abandoned answer content.

Each call owns a private local socket and independent editor window. Client
cancellation and server disconnection set Edital's public cancellation event,
discard the pending buffer, and clean up the session. MCP stdout remains isolated
from terminal rendering. Concurrent calls do not share answers or lifetimes.

## Verification

```sh
uv run --extra dev python -m pytest
uv run --extra dev ruff check .
uv run --extra dev mypy src tests
uv run --extra dev python -m build
```

Agent-specific timeout setup and live verification are tracked in the coordinating
Skillsmith OpenSpec change. MCP progress notifications do not override client deadlines.
