"""Request-scoped new-window interactions and deterministic cleanup."""

import asyncio
import os
import signal
import socket
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import anyio
from edital.session import line_ending

from .config import Config
from .protocol import encode, receive, result


async def edit(config: Config, title: str, initial_text: str = "") -> dict[str, str | None]:
    line_ending(initial_text)
    # Encode before launch so oversized input is diagnosed before a window is opened.
    initial = encode({"type": "initial", "title": title, "text": initial_text})
    loop = asyncio.get_running_loop()
    connected: asyncio.Future[tuple[asyncio.StreamReader, asyncio.StreamWriter, int]] = loop.create_future()
    connections: set[asyncio.StreamWriter] = set()
    claimed = False

    def connect(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        nonlocal claimed
        if claimed or connected.done():
            writer.close()
            return
        peer = writer.get_extra_info("socket")
        pid, uid, _ = struct.unpack("3i", peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if uid != os.getuid():
            writer.close()
            return
        claimed = True
        connections.add(writer)
        connected.set_result((reader, writer, pid))

    # Linux AF_UNIX paths have a small length limit; a short private /tmp directory
    # avoids user-controlled long TMPDIR values. It contains only a socket.
    with tempfile.TemporaryDirectory(prefix="edm-", dir="/tmp") as directory:
        endpoint = str(Path(directory) / "s")
        server = await asyncio.start_unix_server(connect, path=endpoint)
        os.chmod(endpoint, 0o600)
        helper = [sys.executable, "-m", "edital_mcp", "_helper", endpoint]
        writer: asyncio.StreamWriter | None = None
        reader: asyncio.StreamReader | None = None
        pid: int | None = None
        process: subprocess.Popen[bytes] | None = None
        launch_wait: asyncio.Task[int] | None = None
        accepted = False
        try:
            argv = config.launch_argv(helper, Path.cwd())
            # An asyncio subprocess transport can kill a still-running launcher when
            # the server event loop closes. Popen keeps terminal ownership separate.
            process = subprocess.Popen(  # noqa: ASYNC220 - preserve launcher ownership on loop shutdown
                argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, start_new_session=True,
            )

            async def poll_launcher() -> int:
                assert process is not None
                while (code := process.poll()) is None:
                    await asyncio.sleep(0.02)
                return code

            launch_wait = asyncio.create_task(poll_launcher())
            async with asyncio.timeout(config.startup_timeout):
                startup: list[asyncio.Future[Any]] = [connected, launch_wait]
                done, _ = await asyncio.wait(startup, return_when=asyncio.FIRST_COMPLETED)
                if launch_wait in done and launch_wait.result() != 0:
                    raise ValueError(f"terminal launcher exited {launch_wait.result()}")
                reader, writer, pid = await connected
                hello = await receive(reader)
                if hello.get("type") != "hello":
                    raise ValueError("invalid editor handshake")
                writer.write(initial)
                await writer.drain()
            message = await receive(reader)
            if message.get("type") != "result":
                raise ValueError("editor helper failed")
            answer = result(message)
            accepted = True
            return answer
        except TimeoutError as exc:
            raise ValueError("editor helper did not start within session.startup_timeout") from exc
        except (ConnectionError, asyncio.IncompleteReadError) as exc:
            raise ValueError("editor interaction interrupted before an explicit result") from exc
        except OSError as exc:
            raise ValueError("unable to launch or communicate with editor helper") from exc
        finally:
            # MCP SDK cancellation uses AnyIO scopes. Shield cleanup from repeated cancellation.
            with anyio.CancelScope(shield=True):
                server.close()
                if writer is None and connected.done() and not connected.cancelled():
                    reader, writer, pid = connected.result()
                if writer is not None:
                    try:
                        writer.write_eof()
                        if reader is not None:
                            await asyncio.wait_for(reader.read(), timeout=2)
                    except (OSError, TimeoutError):
                        if pid is not None and pid != os.getpid():
                            try:
                                os.kill(pid, signal.SIGTERM)
                            except ProcessLookupError:
                                pass
                for connection in connections:
                    connection.close()
                    try:
                        await connection.wait_closed()
                    except OSError:
                        pass
                await server.wait_closed()
                if not connected.done():
                    connected.cancel()
                if launch_wait is not None:
                    # Never terminate a potentially shared terminal-emulator daemon.
                    # Its child observes socket loss, even after launcher detachment.
                    if not launch_wait.done():
                        launch_wait.cancel()
                    await asyncio.gather(launch_wait, return_exceptions=True)
                if not accepted:
                    # No result escapes this invocation after cancellation/failure.
                    connections.clear()
