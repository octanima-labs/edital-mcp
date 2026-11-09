import os
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest
from edital import EditResult, TuiEditor

from edital_mcp.cli import main
from edital_mcp.config import configure, load


@pytest.fixture
def destination(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("EDITAL_MCP_CONFIG", raising=False)
    return tmp_path / "edital-mcp" / "config.toml"


@pytest.mark.parametrize("terminal", ["alacritty", "kitty", "gnome-terminal", "konsole"])
def test_create_selects_one_example(
    destination: Path, monkeypatch: pytest.MonkeyPatch, terminal: str,
) -> None:
    def accept(self: TuiEditor, text: str, **kwargs: Any) -> EditResult:
        assert not destination.exists()
        assert text.count("\ncommand = ") == 1
        return EditResult("accepted", text)

    monkeypatch.setattr(TuiEditor, "edit", accept)
    monkeypatch.setenv("TERM", "unmatched")
    assert main(["conf", "-t", terminal]) == 0
    assert load().command[0] == terminal
    assert load().startup_timeout == 15.0


def test_environment_terminal_and_reset_backup(
    destination: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination.parent.mkdir()
    original = b"malformed configuration to recover\r\n"
    destination.write_bytes(original)
    monkeypatch.setenv("TERM", "kitty")
    assert main(["conf", "--reset"]) == 0
    assert load().command[0] == "kitty"
    backups = list(destination.parent.glob("*.toml.bkp"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == original


def test_explicit_terminal_overrides_environment(
    destination: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TERM", "kitty")
    assert main(["conf", "-r", "--term", "alacritty"]) == 0
    assert load().command[0] == "alacritty"
    assert not list(destination.parent.glob("*.bkp"))


@pytest.mark.parametrize("terminal", ["xterm-256color", "bash", "", 'kitty"\ncommand = []'])
def test_unknown_terminal_leaves_examples_commented(
    destination: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
    terminal: str,
) -> None:
    monkeypatch.setenv("TERM", "kitty")
    configure(reset=True, term=terminal)
    assert tomllib.loads(destination.read_text())["terminal"] == {}
    assert "No matching terminal example" in capsys.readouterr().out


@pytest.mark.parametrize("existing", [False, True])
def test_cancellation_preserves_destination(
    destination: Path, monkeypatch: pytest.MonkeyPatch, existing: bool,
) -> None:
    original = "invalid TOML to repair\n"
    if existing:
        destination.parent.mkdir()
        destination.write_text(original)

    def cancel(self: TuiEditor, text: str, **kwargs: Any) -> EditResult:
        if existing:
            assert text == original
        else:
            assert 'command = ["kitty"' in text
        return EditResult("cancelled")

    monkeypatch.setattr(TuiEditor, "edit", cancel)
    configure(term="kitty")
    assert destination.exists() == existing
    if existing:
        assert destination.read_text() == original
    assert not list(destination.parent.glob("*.bkp"))


def test_edit_preserves_unrelated_settings_and_ignores_term(
    destination: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination.parent.mkdir()
    original = '# User comment\n[unrelated]\nvalue = 42\n'
    destination.write_text(original)

    def accept(self: TuiEditor, text: str, **kwargs: Any) -> EditResult:
        assert text == original
        return EditResult("accepted", text)

    monkeypatch.setattr(TuiEditor, "edit", accept)
    configure(term="kitty")
    assert destination.read_text() == original


def test_conf_uses_environment_path(
    destination: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    alternate = tmp_path / "alternate.toml"
    monkeypatch.setenv("EDITAL_MCP_CONFIG", str(alternate))
    configure(reset=True, term="kitty")
    assert alternate.is_file()
    assert not destination.exists()
    assert load().command[0] == "kitty"


@pytest.mark.parametrize("existing", [False, True])
def test_serve_rejects_configuration_before_mcp_connects(
    destination: Path, existing: bool,
) -> None:
    if existing:
        destination.parent.mkdir()
        destination.write_text("secret invalid content")
    result = subprocess.run(
        [sys.executable, "-m", "edital_mcp", "serve"],
        input="", capture_output=True, text=True, timeout=15, env=os.environ.copy(), check=False,
    )
    assert result.returncode == 1
    assert result.stdout == ""
    assert "secret invalid content" not in result.stderr
    assert "Traceback" not in result.stderr
    assert str(destination) in result.stderr
    assert ("Cannot use" if existing else "Configuration file missing") in result.stderr
    if not existing:
        assert "edital-mcp conf" in result.stderr


def test_conf_reports_editor_failure(
    destination: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(self: TuiEditor, text: str, **kwargs: Any) -> EditResult:
        error = RuntimeError("sensitive editor content")
        error.add_note("Accepted editor text retained at: /recovery/config.toml")
        raise error

    monkeypatch.setattr(TuiEditor, "edit", fail)
    assert main(["conf", "-t", "kitty"]) == 1
    error = capsys.readouterr().err
    assert "sensitive editor content" not in error
    assert "Accepted editor text retained at: /recovery/config.toml" in error
    assert not destination.exists()
