import asyncio
import os
import sys
from pathlib import Path

import pytest

from edital_mcp.config import Config
from edital_mcp.session import edit


@pytest.fixture
def real_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    monkeypatch.setenv("DISPLAY", ":test")
    monkeypatch.setenv("PTY_RECORD", str(tmp_path / "helper"))
    return Config((sys.executable, str(Path(__file__).with_name("pty_terminal.py")),
                   "{cwd}", "{argv}"), 5)


@pytest.mark.parametrize(("keys", "initial", "expected"), [
    ("1b4f51", "unchanged\n", {"outcome": "accepted", "text": "unchanged\n"}),
    ("1b4f51", "", {"outcome": "accepted", "text": ""}),
    ("68656c6c6f/1b4f51", "", {"outcome": "accepted", "text": "hello"}),
    ("11", "draft", {"outcome": "cancelled", "text": None}),
])
async def test_actual_editing(
    real_config: Config, monkeypatch: pytest.MonkeyPatch, keys: str,
    initial: str, expected: dict[str, str | None],
) -> None:
    monkeypatch.setenv("PTY_KEYS", keys)
    assert await asyncio.wait_for(edit(real_config, "Actual editor", initial), 8) == expected


async def test_actual_editor_cancel_cleanup(
    real_config: Config, tmp_path: Path,
) -> None:
    request = asyncio.create_task(edit(real_config, "Cancel from client", "abandoned"))
    record = tmp_path / "helper"
    for _ in range(100):
        if record.exists():
            break
        await asyncio.sleep(0.02)
    pid = int(record.read_text())
    await asyncio.sleep(0.5)
    request.cancel()
    with pytest.raises(asyncio.CancelledError):
        await request
    for _ in range(100):
        if record.with_suffix(".exit").exists():
            break
        await asyncio.sleep(0.02)
    assert record.with_suffix(".exit").read_text() == "0"
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
