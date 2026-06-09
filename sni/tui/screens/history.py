from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label

from sni.providers.base import AnimeResult
from sni.tui.bridge import get_episodes, get_history, get_providers
from sni.tui.screens.player import PlayerOverlay


class HistoryScreen(Screen):
    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self._provider = (get_providers() or ["allanime"])[0]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Watch History", id="history-title")
        yield DataTable(id="history-table", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#history-table", DataTable)
        table.add_columns("Anime", "Episode", "Provider")
        entries = get_history()
        for e in entries:
            table.add_row(
                e.get("anime_title", "Unknown"),
                f"Episode {e.get('last_episode', '?')}",
                e.get("provider", ""),
            )

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        table = self.query_one("#history-table", DataTable)
        cursor_y = table.cursor_row
        if cursor_y is None:
            return
        entries = get_history()
        if cursor_y < len(entries):
            entry = entries[cursor_y]
            anime = AnimeResult(id=entry["anime_id"], title=entry["anime_title"])
            try:
                episodes = await get_episodes(anime.id, self._provider)
            except Exception:
                self.app.push_screen("home")
                return
            if episodes:
                ep = episodes[0]
                self.app.push_screen(
                    PlayerOverlay(anime, ep, "1080", False, self._provider, episodes)
                )

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_quit(self) -> None:
        self.app.exit()
