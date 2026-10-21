import math
import sys
from pathlib import Path

import pytest

from edital_mcp.config import Config, load


@pytest.mark.parametrize("command", [(), ("x", "{argv}"), ("x", "{argv}", "{cwd}", "{cwd}"),
                                     ("x", "prefix{argv}", "{cwd}"), ("{cwd}", "{argv}")])
def test_reject_template(command: tuple[str, ...]) -> None:
    with pytest.raises(ValueError):
        Config(command)


@pytest.mark.parametrize("timeout", [0, -1, math.nan, math.inf, True])
def test_reject_timeout(timeout: float) -> None:
    with pytest.raises(ValueError):
        Config(("x", "{cwd}", "{argv}"), timeout)


def test_argv_preserves_boundaries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISPLAY", ":test")
    cwd = tmp_path / "directory with spaces"
    cwd.mkdir()
    conf = Config((sys.executable, "{cwd}", "{argv}"))
    assert conf.launch_argv(["/helper with spaces/python", "argument with spaces"], cwd) == [
        sys.executable, str(cwd), "/helper with spaces/python", "argument with spaces"]


def test_desktop_and_executable_preflight(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    with pytest.raises(ValueError, match="DISPLAY"):
        Config((sys.executable, "{cwd}", "{argv}")).launch_argv(["helper"], tmp_path)
    monkeypatch.setenv("DISPLAY", ":test")
    with pytest.raises(ValueError, match="unavailable"):
        Config(("nonexistent-edital-test-terminal", "{cwd}", "{argv}")).launch_argv([], tmp_path)


def test_configuration_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    default = tmp_path / "edital-mcp" / "config.toml"
    default.parent.mkdir()
    template = 'command = ["python", "{cwd}", "{argv}"]\n'
    default.write_text("[terminal]\n" + template)
    assert load().startup_timeout == 15
    explicit = tmp_path / "skillsmith.toml"
    explicit.write_text('[unrelated]\nx = true\n[terminal]\n' + template
                        + "[session]\nstartup_timeout = 30\n")
    monkeypatch.setenv("EDITAL_MCP_CONFIG", str(explicit))
    assert load().startup_timeout == 30
    assert load(str(default)).startup_timeout == 15
    with pytest.raises(ValueError, match="Cannot use"):
        load(str(tmp_path / "missing"))
    explicit.write_text("not TOML or draft text")
    with pytest.raises(ValueError, match="Cannot use") as failure:
        load()
    assert "draft text" not in str(failure.value)
