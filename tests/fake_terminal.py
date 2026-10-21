"""Subprocess fixture: behaves like a terminal-side helper without opening a UI."""

import os
import socket
import sys
import time

from edital_mcp.protocol import encode, receive_sync


def main() -> None:
    if os.environ.get("FAKE_TERMINAL_FAIL"):
        raise SystemExit(7)
    if os.environ.get("FAKE_TERMINAL_DETACH"):
        child = os.fork()
        if child:
            os._exit(0)
    if os.environ.get("FAKE_TERMINAL_NO_CONNECT"):
        return
    endpoint = sys.argv[-1]
    with socket.socket(socket.AF_UNIX) as connection:
        connection.connect(endpoint)
        connection.sendall(encode({"type": "hello"}))
        initial = receive_sync(connection)
        mode = initial["title"]
        if mode == "disconnect":
            return
        if mode == "wait":
            connection.recv(1)
            return
        if mode == "invalid":
            connection.sendall(encode({"type": "result", "outcome": "accepted", "text": None}))
            return
        if mode == "error":
            connection.sendall(encode({"type": "error"}))
            return
        if mode == "race":
            time.sleep(0.1)
        text = "" if mode == "empty" else initial["text"]
        outcome = "cancelled" if mode == "cancel" else "accepted"
        connection.sendall(encode({"type": "result", "outcome": outcome,
                                   "text": None if outcome == "cancelled" else text}))


if __name__ == "__main__":
    main()
