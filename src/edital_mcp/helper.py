"""Terminal-side editor using only Edital's public embedded API."""

import os
import socket
import stat
from pathlib import Path
from threading import Event, Thread

from edital import edit_text

from .protocol import encode, receive_sync


def run(endpoint: str) -> int:
    try:
        return _run(endpoint)
    finally:
        # Also clean request resources after abrupt server death, when its own
        # TemporaryDirectory finalizer cannot run. Never touch arbitrary paths.
        path = Path(endpoint)
        parent = path.parent
        try:
            directory = parent.lstat()
            if (parent.parent == Path("/tmp") and parent.name.startswith("edm-")
                    and stat.S_ISDIR(directory.st_mode) and directory.st_uid == os.getuid()
                    and stat.S_IMODE(directory.st_mode) == 0o700):
                if stat.S_ISSOCK(path.lstat().st_mode):
                    path.unlink()
                parent.rmdir()
        except OSError:
            pass


def _run(endpoint: str) -> int:
    cancel = Event()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.connect(endpoint)
        connection.sendall(encode({"type": "hello"}))
        initial = receive_sync(connection)
        if (initial.get("type") != "initial" or not isinstance(initial.get("title"), str)
                or not isinstance(initial.get("text"), str)):
            raise ValueError("invalid editor initialization")

        def watch() -> None:
            try:
                # The server sends no more data. EOF or unexpected input aborts editing.
                connection.recv(1)
            except OSError:
                pass
            cancel.set()

        watcher = Thread(target=watch, daemon=True)
        watcher.start()
        try:
            answer = edit_text(initial["text"], title=initial["title"], cancel_event=cancel)
            if not cancel.is_set():
                connection.sendall(encode({"type": "result", "outcome": answer.outcome,
                                           "text": answer.text}))
            return 0
        except Exception:  # noqa: BLE001 - never return exception messages containing draft text
            # Error details can include user text; send only a stable operational diagnostic.
            if not cancel.is_set():
                connection.sendall(encode({"type": "error"}))
            return 1
        finally:
            connection.shutdown(socket.SHUT_RDWR)
            watcher.join(timeout=1)
