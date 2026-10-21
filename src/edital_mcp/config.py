"""Bridge-owned configuration compatible with Skillsmith terminal templates."""

import math
import os
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_config_path


@dataclass(frozen=True)
class Config:
    command: tuple[str, ...]
    startup_timeout: float = 15.0

    def __post_init__(self) -> None:
        if not self.command or not all(isinstance(s, str) and s for s in self.command):
            raise ValueError("terminal.command must be a nonempty array of nonempty strings")
        for placeholder in ("{cwd}", "{argv}"):
            if self.command.count(placeholder) != 1:
                raise ValueError(f"terminal.command needs exactly one whole-token {placeholder}")
            if any(placeholder in s and s != placeholder for s in self.command):
                raise ValueError("terminal placeholders must occupy whole tokens")
        if self.command[0] in {"{cwd}", "{argv}"}:
            raise ValueError("terminal.command must start with a terminal executable")
        if (isinstance(self.startup_timeout, bool)
                or not isinstance(self.startup_timeout, (int, float))
                or not math.isfinite(self.startup_timeout) or self.startup_timeout <= 0):
            raise ValueError("session.startup_timeout must be a finite positive number of seconds")

    def launch_argv(self, helper: list[str], cwd: Path) -> list[str]:
        if not cwd.is_dir():
            raise ValueError("MCP server working directory no longer exists")
        if not shutil.which(self.command[0]):
            raise ValueError(f"terminal executable is unavailable: {self.command[0]}")
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            raise ValueError("new-window editing requires DISPLAY or WAYLAND_DISPLAY")
        argv: list[str] = []
        for token in self.command:
            argv.extend(helper if token == "{argv}" else [str(cwd) if token == "{cwd}" else token])
        return argv


def load(path: str | None = None) -> Config:
    selected = path if path is not None else os.environ.get("EDITAL_MCP_CONFIG")
    source = Path(selected).expanduser() if selected else user_config_path("edital-mcp") / "config.toml"
    try:
        with source.open("rb") as stream:
            data = tomllib.load(stream)
        terminal = data.get("terminal", {})
        session = data.get("session", {})
        if not isinstance(terminal, dict) or not isinstance(session, dict):
            raise ValueError("terminal and session must be TOML tables")  # noqa: TRY004
        command = terminal.get("command")
        if not isinstance(command, list):
            raise ValueError("terminal.command must be an array; configure a new-window launcher")  # noqa: TRY004
        return Config(tuple(command), session.get("startup_timeout", 15.0))
    except (OSError, ValueError) as exc:
        # Do not echo arbitrary file contents from TOML parsing errors.
        raise ValueError(f"Cannot use {source}: configure a valid terminal.command and session.startup_timeout") from exc
