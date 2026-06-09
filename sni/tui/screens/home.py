from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Input, Label, ListItem, ListView, Static

from sni.tui.bridge import get_episodes, get_providers, save_history, search
from sni.tui.screens.help import HelpModal
from sni.tui.screens.player import PlayerOverlay
from sni.tui.widgets.info_box import InfoBox


class HomeScreen(Screen):
    BINDINGS = [
        ("/", "focus_input", "Search Input"),
        ("!", "focus_input", "Focus Input"),
        ("@", "focus_table", "Focus Table"),
        ("#", "focus_sub", "Focus Sub"),
        ("$", "focus_dub", "Focus Dub"),
        ("%", "focus_info", "Focus Info"),
        ("?", "toggle_help", "Help"),
        ("escape", "back_or_quit", "Back/Quit"),
        ("enter", "select", "Select"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("down", "cursor_down", "Down"),
        ("up", "cursor_up", "Up"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self._dub = False
        self._provider_index = 0
        self._providers = get_providers()
        self._provider = self._providers[0] if self._providers else "allanime"
        self._results = []
        self._episodes = []
        self._selected_anime = None
        self._search_gen = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="home-content"):
            with Vertical(id="watch-pane"):
                yield Input(placeholder="search your anime", id="search-input")
                yield Static("", id="loading-msg")
                yield DataTable(id="results-table", cursor_type="row")
                with Horizontal(id="bottom-panels"):
                    with Vertical(id="sub-panel"):
                        yield Label("Sub Episodes", classes="panel-title")
                        yield ListView(id="sub-list")
                    with Vertical(id="dub-panel"):
                        yield Label("Dub Episodes", classes="panel-title")
                        yield ListView(id="dub-list")
                    yield InfoBox(id="info-box")
        yield Footer()

    async def on_mount(self) -> None:
        table = self.query_one("#results-table", DataTable)
        table.add_columns("#", "Title", "Eps", "Score", "Rating")
        self.query_one("#search-input", Input).focus()

    def _update_border_colors(self):
        active = "#9F2B68"
        inactive = "#666666"
        focused_id = ""
        if self.focused:
            focused_id = self.focused.id or ""
        for wid in ["#search-input", "#results-table", "#sub-list", "#dub-list", "#info-box"]:
            try:
                w = self.query_one(wid)
                if w.id == focused_id:
                    w.styles.border = ("round", active)
                else:
                    w.styles.border = ("round", inactive)
            except Exception:
                pass

    def watch_focused(self, widget) -> None:
        self._update_border_colors()

    def action_focus_input(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_focus_table(self) -> None:
        self.query_one("#results-table", DataTable).focus()

    def action_focus_sub(self) -> None:
        self.query_one("#sub-list", ListView).focus()

    def action_focus_dub(self) -> None:
        self.query_one("#dub-list", ListView).focus()

    def action_focus_info(self) -> None:
        self.query_one("#info-box", InfoBox).focus()

    def action_toggle_help(self) -> None:
        self.app.push_screen(HelpModal())

    def action_back_or_quit(self) -> None:
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        else:
            self.app.exit()

    def action_quit(self) -> None:
        self.app.exit()

    async def action_select(self) -> None:
        focused = self.focused
        if not focused:
            return
        if focused.id == "results-table":
            await self._on_table_select()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input" and self._results:
            self.query_one("#results-table", DataTable).focus()
            self._update_border_colors()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "sub-list":
            await self._on_episode_select("sub")
        elif event.list_view.id == "dub-list":
            await self._on_episode_select("dub")

    def action_cursor_down(self) -> None:
        focused = self.focused
        if not focused:
            return
        if focused.id == "results-table":
            table = self.query_one("#results-table", DataTable)
            row = table.cursor_row
            if row is not None and row < len(self._results) - 1:
                table.cursor_row = row + 1
                table.scroll_cursor_visible()
        elif focused.id == "sub-list":
            lv = self.query_one("#sub-list", ListView)
            if lv.index is not None and lv.index < len(lv.children) - 1:
                lv.index = lv.index + 1
        elif focused.id == "dub-list":
            lv = self.query_one("#dub-list", ListView)
            if lv.index is not None and lv.index < len(lv.children) - 1:
                lv.index = lv.index + 1

    def action_cursor_up(self) -> None:
        focused = self.focused
        if not focused:
            return
        if focused.id == "results-table":
            table = self.query_one("#results-table", DataTable)
            row = table.cursor_row
            if row is not None and row > 0:
                table.cursor_row = row - 1
                table.scroll_cursor_visible()
        elif focused.id == "sub-list":
            lv = self.query_one("#sub-list", ListView)
            if lv.index is not None and lv.index > 0:
                lv.index = lv.index - 1
        elif focused.id == "dub-list":
            lv = self.query_one("#dub-list", ListView)
            if lv.index is not None and lv.index > 0:
                lv.index = lv.index - 1

    async def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "search-input":
            return
        self._search_gen += 1
        gen = self._search_gen
        query = event.value.strip()
        msg = self.query_one("#loading-msg", Static)
        table = self.query_one("#results-table", DataTable)
        table.clear()
        if len(query) < 2:
            msg.update("[#666666]Type at least 2 characters to search[/]")
            return
        msg.update("[#AA336A]Searching...[/]")
        try:
            results = await search(query, self._provider, self._dub)
            if gen != self._search_gen:
                return
            table.clear()
            self._results = []
            for i, (_, anime_list) in enumerate(results):
                for r in anime_list:
                    self._results.append(r)
                    score_str = f"{r.score:.1f}" if r.score else "N/A"
                    eps_str = str(r.episodes) if r.episodes else "?"
                    table.add_row(str(len(self._results)), r.title, eps_str, score_str, "")
            if self._results:
                msg.update("")
            else:
                msg.update("[#666666]No results found[/]")
        except Exception as e:
            if gen != self._search_gen:
                return
            msg.update(f"[#FF0044]Error: {e}[/]")

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        await self._on_table_select()

    async def _on_table_select(self):
        table = self.query_one("#results-table", DataTable)
        row = table.cursor_row
        if row is None or row >= len(self._results):
            return
        anime = self._results[row]
        self._selected_anime = anime
        self.query_one("#info-box", InfoBox).set_info(anime)
        try:
            episodes = await get_episodes(anime.id, self._provider)
            self._episodes = episodes
        except Exception as e:
            self.query_one("#loading-msg", Static).update(f"[#FF0044]Episodes: {e}[/]")
            return
        sub_list = self.query_one("#sub-list", ListView)
        dub_list = self.query_one("#dub-list", ListView)
        await sub_list.clear()
        await dub_list.clear()
        for ep in episodes:
            item = ListItem(Static(f"● Episode {ep.number}"))
            item._episode = ep
            await sub_list.mount(item)
            item2 = ListItem(Static(f"● Episode {ep.number}"))
            item2._episode = ep
            await dub_list.mount(item2)
        self.query_one("#sub-list", ListView).focus()
        self._update_border_colors()

    async def _on_episode_select(self, ep_type: str):
        if not self._selected_anime or not self._episodes:
            return
        lv = self.query_one(f"#{ep_type}-list", ListView)
        if lv.index is None:
            return
        children = list(lv.children)
        if lv.index >= len(children):
            return
        ep = children[lv.index]._episode
        quality = "1080"
        try:
            save_history(
                anime_id=self._selected_anime.id,
                anime_title=self._selected_anime.title,
                episode=ep.number,
                provider=self._provider,
            )
        except Exception:
            pass
        self.app.push_screen(
            PlayerOverlay(
                self._selected_anime, ep, quality, ep_type == "dub",
                self._provider, self._episodes,
            )
        )
