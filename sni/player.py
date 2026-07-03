"""SNI player — minimal mpv wrapper.

Design principles:
- SIMPLEST possible mpv invocation: just URL + headers
- NO demuxer flags (they cause fatal errors when out of range)
- Capture stderr so we can show WHY mpv failed
- Let mpv auto-detect format (it's smart enough for MP4)
"""

import os
import platform
import shutil
import subprocess
from typing import Optional

from sni.allanime import Stream
from sni.exceptions import PlayerError


class Player:
    """Minimal mpv wrapper. Just plays the URL with the right headers."""

    IPC_SOCKET = r"\\.\pipe\sni-mpv" if platform.system() == "Windows" else "/tmp/sni-mpv.sock"

    def __init__(self, player: str = "mpv", use_ipc: bool = True, debug: bool = False):
        self.player_name = player
        self.use_ipc = use_ipc
        self.debug = debug
        self._process: Optional[subprocess.Popen] = None

    @property
    def available(self) -> bool:
        return shutil.which(self.player_name) is not None

    def play(self, stream: Stream, quality: str = "1080") -> None:
        """Launch mpv with the stream URL and headers."""
        if not self.available:
            raise PlayerError(f"{self.player_name} is not installed. Install it with:\n"
                              f"  Linux: sudo apt install mpv\n"
                              f"  macOS: brew install mpv\n"
                              f"  Windows: winget install mpv.net")

        # Clean up old IPC socket
        try:
            if os.path.exists(self.IPC_SOCKET):
                os.unlink(self.IPC_SOCKET)
        except OSError:
            pass

        # Build the SIMPLEST possible mpv command that works.
        # No demuxer flags — mpv auto-detects format.
        # No analyzeduration — it can cause fatal "out of range" errors.
        # Just URL + headers + basic cache settings.
        cmd = [
            self.player_name,
            stream.url,
            f"--title=SNI - {stream.quality}",
            "--cache=yes",
            "--cache-secs=60",
            "--demuxer-max-bytes=200M",
            "--force-seekable=yes",
        ]

        # Add HTTP headers (Referer, Origin, Authorization, etc.)
        for key, val in stream.headers.items():
            cmd.append(f"--http-header-fields={key}: {val}")

        # IPC socket for player controls (next, prev, quit)
        if self.use_ipc:
            cmd.append(f"--input-ipc-server={self.IPC_SOCKET}")

        if self.debug:
            cmd.append("--msg-level=all=v")
            cmd.append("--terminal=yes")
        else:
            cmd.append("--no-terminal")

        # Launch
        popen_kwargs = {}
        if platform.system() != "Windows":
            popen_kwargs["start_new_session"] = True

        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            **popen_kwargs,
        )

    def wait(self) -> None:
        """Wait for mpv to finish. Raises PlayerError if mpv fails."""
        if not self._process:
            return

        output_lines = []
        if self._process.stdout:
            for line in self._process.stdout:
                output_lines.append(line)
                if self.debug:
                    print(line, end="")

        self._process.wait()
        rc = self._process.returncode

        if rc != 0 and rc is not None:
            # Extract the actual error from mpv's output
            output = "".join(output_lines[-20:])
            error_lines = [
                line for line in output.splitlines()
                if "error" in line.lower() or "failed" in line.lower()
                or "403" in line or "Forbidden" in line
            ]
            error_summary = "\n".join(error_lines[-5:]) if error_lines else output.strip()[-500:]

            raise PlayerError(
                f"mpv exited with code {rc}.\n\n"
                f"mpv error output:\n{error_summary}\n\n"
                f"Common fixes:\n"
                f"  - Stream URL expired: try searching again\n"
                f"  - 403 Forbidden: your IP is blocked by the CDN. Try a VPN or configure a CF Worker:\n"
                f"    sni config --update allanime_cf_worker_url='https://your-worker.deno.dev'\n"
                f"  - Run with --debug for full output: sni --debug play \"X\""
            )

    def is_running(self) -> bool:
        if self._process is None:
            return False
        return self._process.poll() is None

    def stop(self) -> None:
        if self._process:
            self._process.terminate()
            self._process = None

    # ─── IPC controls (require mpv --input-ipc-server) ──────────────────

    def _send_ipc(self, command: str) -> bool:
        """Send a raw IPC command to mpv."""
        if not self.use_ipc:
            return False
        for _ in range(5):
            try:
                if os.path.exists(self.IPC_SOCKET):
                    with open(self.IPC_SOCKET, "w") as sock:
                        sock.write(command + "\n")
                    return True
            except OSError:
                pass
            import time
            time.sleep(0.2)
        return False

    def next_episode(self) -> None:
        self._send_ipc('playlist-next')

    def prev_episode(self) -> None:
        self._send_ipc('playlist-prev')

    def reload(self) -> None:
        self._send_ipc('reload')

    def quit(self) -> None:
        self._send_ipc('quit')
        self.stop()
