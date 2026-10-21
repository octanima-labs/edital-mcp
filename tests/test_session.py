import asyncio
from pathlib import Path

import pytest

from edital_mcp.config import Config
from edital_mcp.session import edit


@pytest.mark.parametrize("text", ["", "unchanged", "  # comment\nλ\t\n\n", "a\r\nb\r\n"])
async def test_exact_answer(config: Config, text: str) -> None:
    assert await edit(config, "accept", text) == {"outcome": "accepted", "text": text}


async def test_empty_and_cancel_are_distinct(config: Config) -> None:
    assert await edit(config, "empty", "draft") == {"outcome": "accepted", "text": ""}
    assert await edit(config, "cancel", "abandoned") == {"outcome": "cancelled", "text": None}


@pytest.mark.parametrize("text", ["a\rb", "a\r\nb\n"])
async def test_reject_line_endings_before_launch(config: Config, text: str) -> None:
    with pytest.raises(ValueError, match="line endings"):
        await edit(config, "accept", text)


@pytest.mark.parametrize("mode", ["disconnect", "invalid", "error"])
async def test_operational_error(config: Config, mode: str) -> None:
    with pytest.raises(ValueError) as failure:
        await edit(config, mode, "PRIVATE BUFFER")
    assert "PRIVATE BUFFER" not in str(failure.value)


async def test_detached_launcher(config: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_TERMINAL_DETACH", "1")
    assert (await edit(config, "accept", "detached"))["text"] == "detached"


async def test_launch_failure(config: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_TERMINAL_FAIL", "1")
    with pytest.raises(ValueError, match="launcher exited 7"):
        await edit(config, "accept")


async def test_startup_timeout(config: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_TERMINAL_NO_CONNECT", "1")
    with pytest.raises(ValueError, match="did not start"):
        await edit(Config(config.command, 0.2), "accept")


async def test_cancel_isolated_from_other_requests(config: Config) -> None:
    pending = asyncio.create_task(edit(config, "wait", "never return"))
    await asyncio.sleep(0.4)
    assert (await edit(config, "accept", "other"))["text"] == "other"
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert (await edit(config, "accept", "later"))["text"] == "later"


async def test_cleanup_and_race(config: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    import tempfile

    original = tempfile.TemporaryDirectory
    created: list[str] = []

    def tracked(*args: object, **kwargs: object) -> tempfile.TemporaryDirectory[str]:
        directory = original(prefix="edm-test-", dir="/tmp")
        created.append(directory.name)
        return directory

    monkeypatch.setattr("edital_mcp.session.tempfile.TemporaryDirectory", tracked)
    tasks = [asyncio.create_task(edit(config, "race", str(i))) for i in range(4)]
    await asyncio.sleep(0.15)
    tasks[0].cancel()
    answers = await asyncio.gather(*tasks, return_exceptions=True)
    assert isinstance(answers[0], asyncio.CancelledError)
    for i, answer in enumerate(answers[1:], 1):
        assert answer == {"outcome": "accepted", "text": str(i)}
    assert all(not Path(path).exists() for path in created)
