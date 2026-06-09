import asyncio

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from sni.player import Player
from sni.tui.bridge import get_streams, save_history


class PlayerOverlay(ModalScreen):
    BINDINGS = [
        ("escape", "select_episode", "Episodes"),
        ("n", "next", "Next"),
        ("p", "prev", "Prev"),
        ("r", "replay", "Replay"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, anime, episode, quality, dub, provider, episodes):
        super().__init__()
        self._anime = anime
        self._episode = episode
        self._quality = quality
        self._dub = dub
        self._provider = provider
        self._episodes = episodes
        self._current_ep_index = next(
            (i for i, e in enumerate(episodes) if e.number == episode.number), 0
        )
        self._player: Player | None = None
        self._stream_task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        yield Static("", id="player-info")
        yield Label("", id="player-status")
        with Horizontal(id="player-controls"):
            yield Button("Replay (r)", id="btn-replay", variant="primary")
            yield Button("Prev (p)", id="btn-prev")
            yield Button("Next (n)", id="btn-next", variant="primary")
            yield Button("Episodes (Esc)", id="btn-select-ep")
            yield Button("Quit (q)", id="btn-quit")

    async def on_mount(self) -> None:
        await self._play_current()

    def _stop_player(self):
        if self._player and self._player.is_running():
            self._player._process.terminate()
            try:
                self._player._process.wait(timeout=3)
            except Exception:
                self._player._process.kill()
                self._player._process.wait()
            self._player = None
        self._stream_task = None

    async def _play_current(self) -> None:
        self._stop_player()

        ep = self._episodes[self._current_ep_index]
        info = self.query_one("#player-info", Static)
        info.update(
            f"[bold]{self._anime.title}[/bold]\n"
            f"Episode {ep.number}/{len(self._episodes)} [{self._quality}]"
        )
        status = self.query_one("#player-status", Label)
        status.update("Loading stream...")
        try:
            streams = await get_streams(
                ep.id, self._quality, self._dub, self._provider
            )
            if not streams:
                status.update("No streams available.")
                return
            status.update("Launching mpv...")
            save_history(
                anime_id=self._anime.id,
                anime_title=self._anime.title,
                episode=ep.number,
                provider=self._provider,
                episode_id=ep.id,
            )
            self._player = Player()
            self._player.play(streams[0], self._quality)
            loop = asyncio.get_running_loop()
            returncode = await loop.run_in_executor(None, self._player.wait)
            status.update(f"mpv exited (code {returncode})")
        except Exception as e:
            status.update(f"Error: {e}")

    async def action_next(self) -> None:
        if self._current_ep_index < len(self._episodes) - 1:
            self._current_ep_index += 1
            await self._play_current()

    async def action_prev(self) -> None:
        if self._current_ep_index > 0:
            self._current_ep_index -= 1
            await self._play_current()

    async def action_replay(self) -> None:
        await self._play_current()

    def action_select_episode(self) -> None:
        self._stop_player()
        self.app.pop_screen()

    def action_quit(self) -> None:
        self._stop_player()
        self.app.exit()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-replay":
            await self.action_replay()
        elif event.button.id == "btn-next":
            await self.action_next()
        elif event.button.id == "btn-prev":
            await self.action_prev()
        elif event.button.id == "btn-select-ep":
            self.action_select_episode()
        elif event.button.id == "btn-quit":
            self.action_quit()
