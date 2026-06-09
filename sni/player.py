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

    def __init__(self, player: str = "mpv", use_ipc: bool = True):
        self.player_name = player
        self.use_ipc = use_ipc
        self._process: Optional[subprocess.Popen] = None

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
            "--no-terminal",
        ]

        for key, val in stream.headers.items():
            cmd.append(f"--http-header-fields={key}: {val}")

        if subtitles and stream.sub_lang:
            cmd.append(f"--sub-file={stream.sub_lang}")

        if self.use_ipc:
            cmd.append(f"--input-ipc-server={self.IPC_SOCKET}")

        cmd.append("--keep-open=no")

        popen_kwargs = {}
        if platform.system() != "Windows":
            popen_kwargs["start_new_session"] = True
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
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
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
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
            self._process.wait()
            if self._process.returncode != 0 and self._process.returncode is not None:
                raise StreamError(f"mpv exited with code {self._process.returncode}")

    def is_running(self) -> bool:
        if self._process is None:
            return False
        return self._process.poll() is None
