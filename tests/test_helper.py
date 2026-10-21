import socket
from pathlib import Path
from threading import Event, Thread
from typing import Any

import pytest
from edital import EditResult, edit_text

from edital_mcp import helper
from edital_mcp.protocol import encode, receive_sync


def test_public_edital_precancel() -> None:
    event = Event()
    event.set()
    assert edit_text("draft", cancel_event=event) == EditResult("cancelled")


@pytest.mark.parametrize("disconnect", [False, True])
def test_helper_transport_loss_and_exact_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, disconnect: bool,
) -> None:
    endpoint = str(tmp_path / "s")
    observed: list[dict[str, Any]] = []
    with socket.socket(socket.AF_UNIX) as server:
        server.bind(endpoint)
        server.listen()

        def server_side() -> None:
            connection, _ = server.accept()
            with connection:
                assert receive_sync(connection)["type"] == "hello"
                connection.sendall(encode({"type": "initial", "title": "Title", "text": " λ\r\n"}))
                if disconnect:
                    connection.shutdown(socket.SHUT_WR)
                    assert connection.recv(1) == b""
                else:
                    observed.append(receive_sync(connection))

        def fake_edit(text: str, *, title: str, cancel_event: Event) -> EditResult:
            assert text == " λ\r\n" and title == "Title"
            if disconnect:
                assert cancel_event.wait(2)
                return EditResult("cancelled")
            return EditResult("accepted", text)

        monkeypatch.setattr(helper, "edit_text", fake_edit)
        worker = Thread(target=server_side)
        worker.start()
        assert helper.run(endpoint) == 0
        worker.join(timeout=3)
        assert not worker.is_alive()
    if not disconnect:
        assert observed == [{"version": 1, "type": "result", "outcome": "accepted", "text": " λ\r\n"}]
