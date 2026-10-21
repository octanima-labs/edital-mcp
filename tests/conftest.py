import sys
from pathlib import Path

import pytest

from edital_mcp.config import Config


@pytest.fixture
def config(monkeypatch: pytest.MonkeyPatch) -> Config:
    monkeypatch.setenv("DISPLAY", ":test")
    return Config((sys.executable, str(Path(__file__).with_name("fake_terminal.py")),
                   "{cwd}", "{argv}"), startup_timeout=3)
