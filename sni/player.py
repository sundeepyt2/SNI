import os
import platform
import shutil
import subprocess
import time
from typing import Optional

from sni.exceptions import StreamError
from sni.providers.base import Stream


class Player:
    IPC_SOCKET = r"\\.\pipe\sni-mpv" if platform.system() == "Windows" else "/tmp/sni-mpv.sock"

    def __init__(self, player: str = "mpv", use_ipc: bool = True, debug: bool = False):
        self.player_name = player
        self.use_ipc = use_ipc
        self.debug = debug
        self._process: Optional[subprocess.Popen] = None
        self._last_stderr: str = ""

    @property
    def available(self) -> bool:
        return shutil.which(self.player_name) is not None

    def _cleanup_socket(self):
        try:
            if os.path.exists(self.IPC_SOCKET):
                os.unlink(self.IPC_SOCKET)
        except OSError:
            pass

    def play(
        self,
        stream: Stream,
        quality: str = "1080",
        subtitles: bool = True,
    ) -> None:
        if self.player_name == "mpv":
            self._play_mpv(stream, subtitles)
        elif self.player_name == "vlc":
            self._play_vlc(stream)
        else:
            raise StreamError(f"Unsupported player: {self.player_name}")

    def _play_mpv(self, stream: Stream, subtitles: bool = True) -> None:
        if not self.available:
            raise StreamError("mpv is not installed")

        self._cleanup_socket()

        cmd = [
            "mpv",
            stream.url,
            f"--title=SNI - {stream.quality}",
            "--cache=yes",
            "--cache-secs=300",
            "--demuxer-max-bytes=500M",
            "--cache-pause=no",
            # Stream compatibility flags — fix common AllAnime playback issues
            "--ytdl=no",              # don't invoke yt-dlp for these URLs
            "--force-seekable=yes",   # allow seeking even on non-seekable streams
            "--demuxer-lavf-o=fflags=+seekable",  # lavf seekable flag
            "--stream-buffer-size=4096",  # larger read buffer
        ]

        # AllAnime stream URLs return content-type: application/octet-stream
        # and have no file extension (e.g. /sub/1?Authorization=...). mpv
        # can't auto-detect the format from that, so it exits with code 2.
        # Force the MP4 demuxer when the URL looks like an AllAnime stream.
        # This is the actual fix for the "mpv exited with code 2" issue.
        url_lower = stream.url.lower()
        if (
            "tools.fast4speed.rsvp" in url_lower
            or "/media" in url_lower
            or "fast4speed" in url_lower
            or "allanime" in url_lower
            or "allmanga" in url_lower
        ):
            cmd.append("--demuxer-lavf-format=mp4")
            cmd.append("--demuxer-lavf-probesize=32000")
            cmd.append("--demuxer-lavf-analyzeduration=2000000")

        for key, val in stream.headers.items():
            # mpv's --http-header-fields expects "Key: Value" format
            cmd.append(f"--http-header-fields={key}: {val}")

        if subtitles and stream.sub_lang:
            cmd.append(f"--sub-file={stream.sub_lang}")

        if self.use_ipc:
            cmd.append(f"--input-ipc-server={self.IPC_SOCKET}")

        cmd.append("--keep-open=no")

        if self.debug:
            # Verbose logging to terminal when --debug is on
            cmd.append("--msg-level=all=v")
            cmd.append("--terminal=yes")
        else:
            cmd.append("--terminal=no")

        popen_kwargs = {}
        if platform.system() != "Windows":
            popen_kwargs["start_new_session"] = True

        # Capture stderr so we can show WHY mpv failed (instead of just
        # "exited with code 2" with no explanation)
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            **popen_kwargs,
        )

    def _play_vlc(self, stream: Stream) -> None:
        if not self.available:
            raise StreamError("vlc is not installed")

        cmd = [
            "vlc",
            stream.url,
            "--play-and-exit",
            f"--meta-title=SNI - {stream.quality}",
        ]

        for key, val in stream.headers.items():
            cmd.append(f"--http-header-fields={key}: {val}")

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    def send_command(self, command: str) -> None:
        if not self.use_ipc or self.player_name != "mpv":
            return

        for attempt in range(5):
            try:
                if os.path.exists(self.IPC_SOCKET):
                    with open(self.IPC_SOCKET, "w") as sock:
                        sock.write(command + "\n")
                    return
            except OSError:
                pass
            time.sleep(0.3)

    def send_playlist(self, urls: list[str]) -> None:
        for url in urls:
            self.send_command(f'loadfile "{url}" append-play')

    def next_episode(self) -> None:
        self.send_command("playlist-next")

    def prev_episode(self) -> None:
        self.send_command("playlist-prev")

    def reload(self) -> None:
        self.send_command("reload")

    def toggle_auto_next(self) -> None:
        self.send_command("cycle loop-playlist")

    def stop(self) -> None:
        self.send_command("quit")
        if self._process:
            self._process.terminate()
            self._process = None

    def wait(self) -> None:
        if self._process:
            # Read output in real-time (so debug mode shows it live)
            output_lines = []
            if self._process.stdout:
                for line in self._process.stdout:
                    output_lines.append(line)
                    if self.debug:
                        print(line, end="")  # live output in debug mode
            self._process.wait()
            self._last_stderr = "".join(output_lines[-20:])  # keep last 20 lines

            if self._process.returncode != 0 and self._process.returncode is not None:
                # Include mpv's actual error output in the exception so the
                # user can see WHY it failed (not just "code 2")
                error_snippet = self._last_stderr.strip()
                if error_snippet:
                    raise StreamError(
                        f"mpv exited with code {self._process.returncode}.\n\n"
                        f"mpv output (last 20 lines):\n{error_snippet}\n\n"
                        f"Common fixes:\n"
                        f"  - The stream URL may have expired — try searching again\n"
                        f"  - Run with --debug to see full mpv output: sni --debug play \"X\"\n"
                        f"  - Try a different episode or anime\n"
                        f"  - Check your internet connection"
                    )
                else:
                    raise StreamError(
                        f"mpv exited with code {self._process.returncode}.\n\n"
                        f"No output captured. Run with --debug to see full mpv output:\n"
                        f"  sni --debug play \"X\""
                    )

    def is_running(self) -> bool:
        if self._process is None:
            return False
        return self._process.poll() is None
