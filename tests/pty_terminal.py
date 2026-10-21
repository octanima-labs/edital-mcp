"""Run the actual helper in a pseudo-terminal; this is not a live desktop check."""

import os
import select
import subprocess
import sys
import termios
import time
from pathlib import Path


def main() -> None:
    master, slave = os.openpty()
    termios.tcsetwinsize(slave, (24, 80))
    process = subprocess.Popen(sys.argv[2:], stdin=slave, stdout=slave, stderr=slave,
                               env={**os.environ, "TERM": "xterm-256color"})
    os.close(slave)
    record = Path(os.environ["PTY_RECORD"])
    record.write_text(str(process.pid))
    record.with_suffix(".endpoint").write_text(sys.argv[-1])
    started = time.monotonic()
    sent = False
    try:
        while process.poll() is None:
            if not sent and time.monotonic() - started > 1:
                keys = os.environ.get("PTY_KEYS", "")
                if keys:
                    chunks = keys.split("/")
                    for chunk in chunks:
                        os.write(master, bytes.fromhex(chunk))
                        time.sleep(0.15)
                sent = True
            if time.monotonic() - started > 10:
                process.kill()
                raise RuntimeError("helper test timed out")
            ready, _, _ = select.select([master], [], [], 0.05)
            if ready:
                try:
                    os.read(master, 65536)
                except OSError:
                    break
        code = process.wait(timeout=3)
        record.with_suffix(".exit").write_text(str(code))
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)


if __name__ == "__main__":
    main()
