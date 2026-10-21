"""Versioned, length-prefixed JSON messages, without document logging."""

import asyncio
import json
import socket
import struct
from typing import Any

VERSION = 1
MAX_MESSAGE = 64 * 1024 * 1024


def encode(message: dict[str, Any]) -> bytes:
    payload = json.dumps({"version": VERSION, **message}, ensure_ascii=True).encode("utf-8")
    if len(payload) > MAX_MESSAGE:
        raise ValueError("editor message exceeds the 64 MiB transport limit")
    return struct.pack("!I", len(payload)) + payload


def decode(payload: bytes) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("invalid editor protocol message") from exc
    if not isinstance(value, dict) or value.get("version") != VERSION:
        raise ValueError("unsupported editor protocol version")
    return value


def size(header: bytes) -> int:
    length = struct.unpack("!I", header)[0]
    if not 0 < length <= MAX_MESSAGE:
        raise ValueError("invalid editor protocol message length")
    return length


async def receive(reader: asyncio.StreamReader) -> dict[str, Any]:
    return decode(await reader.readexactly(size(await reader.readexactly(4))))


def exact(sock: socket.socket, count: int) -> bytes:
    result = bytearray()
    while len(result) < count:
        part = sock.recv(count - len(result))
        if not part:
            raise ConnectionError("editor connection closed")
        result.extend(part)
    return bytes(result)


def receive_sync(sock: socket.socket) -> dict[str, Any]:
    return decode(exact(sock, size(exact(sock, 4))))


def result(value: dict[str, Any]) -> dict[str, str | None]:
    outcome, text = value.get("outcome"), value.get("text")
    if outcome == "accepted" and isinstance(text, str):
        return {"outcome": outcome, "text": text}
    if outcome == "cancelled" and text is None:
        return {"outcome": outcome, "text": None}
    raise ValueError("invalid editor outcome")
