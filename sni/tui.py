"""SNI TUI — beautiful terminal UI using Textual.

Full-featured interface with:
- Home screen with search bar + continue watching
- Search results with rich display
- Episode list with selection
- Player overlay with controls
- Help screen with keybindings

If Textual is not installed, falls back to interactive CLI.
"""

import asyncio

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from sni.allanime import AllAnimeClient
from sni.anilist import AnimeResult, search_anime
from sni.config import Config
from sni.player import Player
from sni.watch_history import WatchHistory

console = Console()


def run_tui():
    """Run the TUI. Falls back to interactive CLI if Textual isn't available."""
    try:
        from textual.app import App, ComposeResult
        from textual.binding import Binding
        from textual.containers import Container
        from textual.reactive import reactive
        from textual.screen import ModalScreen
        from textual.widgets import (
            Footer,
            Header,
            Input,
            ListItem,
            ListView,
            Static,
        )
    except ImportError:
        console.print("[yellow]Textual not installed. Using interactive CLI mode.[/yellow]")
        console.print("[dim]Install with: pip install textual[/dim]\n")
        return _run_cli_fallback()

    class SearchScreen(Container):
        """Search + results screen."""
        results = reactive([])

        def compose(self) -> ComposeResult:
            yield Static(
                "[bold cyan]SNI — Stream Ninja Interface[/bold cyan]\n"
                "[dim]Search for anime, select, and play.[/dim]\n",
                id="title",
            )
            yield Input(id="search", placeholder="Type anime name and press Enter...")
            yield ListView(id="results")

        def on_input_submitted(self, event: Input.Submitted):
            if event.input.id == "search":
                self.run_worker(self.do_search(event.value))

        async def do_search(self, query: str):
            lv = self.query_one("#results", ListView)
            lv.clear()
            lv.append(ListItem(Static(f"[dim]Searching for '{query}'...[/dim]")))
            results = await search_anime(query, limit=20)
            self.results = results
            lv.clear()
            if not results:
                lv.append(ListItem(Static("[red]No results found.[/red]")))
                return
            for r in results:
                eps = f"{r.episodes} eps" if r.episodes else "?"
                score = f" ★{r.score}" if r.score else ""
                lv.append(ListItem(Static(f"  {r.title} [green]({eps})[/green][yellow]{score}[/yellow]")))

        def on_list_view_selected(self, event: ListView.Selected):
            if self.results:
                idx = event.list_view.index
                if idx is not None and 0 <= idx < len(self.results):
                    self.app.push_screen(EpisodeScreen(self.results[idx]))

    class EpisodeScreen(Container):
        """Episode list screen for a selected anime."""

        def __init__(self, anime: AnimeResult):
            super().__init__()
            self.anime = anime
            self.episodes = []
            self.client = None

        def compose(self) -> ComposeResult:
            yield Static(
                f"[bold green]{self.anime.title}[/bold green]\n"
                f"[dim]Episodes: {self.anime.episodes or '?'} | "
                f"Score: {self.anime.score or 'N/A'}[/dim]\n",
                id="anime-title",
            )
            yield Static("[dim]Loading episodes...[/dim]", id="ep-info")
            yield Input(id="ep-input", placeholder="Episode number (e.g. 5) or range (1-12)")
            yield ListView(id="ep-list")

        def on_mount(self):
            self.run_worker(self.load_episodes)

        async def load_episodes(self):
            cfg = Config.load()
            self.client = AllAnimeClient(cf_worker_url=cfg.get_cf_worker_url())
            aa_results = await self.client.search(self.anime.title, limit=5)
            if not aa_results:
                self.query_one("#ep-info", Static).update("[red]Not found on AllAnime.[/red]")
                return

            show_id = aa_results[0]["id"]
            self.episodes = await self.client.get_episodes(show_id)
            if not self.episodes:
                self.query_one("#ep-info", Static).update("[red]No episodes found.[/red]")
                return

            self.query_one("#ep-info", Static).update(
                f"[green]{len(self.episodes)} episodes available.[/green] "
                f"[dim]Enter episode number or select from list.[/dim]"
            )

            lv = self.query_one("#ep-list", ListView)
            for ep in self.episodes[:50]:  # show first 50
                lv.append(ListItem(Static(f"  Episode {ep.number}")))

        def on_input_submitted(self, event: Input.Submitted):
            if event.input.id == "ep-input":
                self.play_from_input(event.value)

        def on_list_view_selected(self, event: ListView.Selected):
            if self.episodes and event.list_view.index is not None:
                idx = event.list_view.index
                if 0 <= idx < len(self.episodes):
                    self.run_worker(self.play_episode(idx))

        def play_from_input(self, value: str):
            try:
                if "-" in value:
                    parts = value.split("-")
                    start = int(parts[0])
                    end = int(parts[1])
                else:
                    start = int(value)
                    end = start
            except ValueError:
                start = 1
                end = 1

            start_idx = 0
            for i, ep in enumerate(self.episodes):
                if ep.number >= start:
                    start_idx = i
                    break
            self.run_worker(self.play_range(start_idx, end))

        async def play_range(self, start_idx: int, end_ep: int):
            cfg = Config.load()
            player = Player(player=cfg.player, use_ipc=cfg.use_ipc)
            history = WatchHistory()

            ep_list = self.episodes[start_idx:]
            for i, ep in enumerate(ep_list):
                if ep.number > end_ep:
                    break

                self.app.push_screen(PlayerOverlay(
                    self.anime, ep.number, len(self.episodes), cfg.quality
                ))

                try:
                    stream = await self.client.get_streams(
                        ep.id, quality=cfg.quality
                    )
                    player.play(stream, cfg.quality)
                    player.wait()
                except Exception as e:
                    console.print(f"[red]{e}[/red]")

                self.app.pop_screen()  # remove player overlay

                history.add(self.anime.id, self.anime.title, ep.number,
                           len(self.episodes))

                if i < len(ep_list) - 1 and ep.number < end_ep:
                    continue  # auto-next for ranges

    class PlayerOverlay(ModalScreen):
        """Player overlay with controls."""

        BINDINGS = [
            Binding("escape", "dismiss", "Back"),
            Binding("n", "next", "Next"),
            Binding("p", "prev", "Prev"),
            Binding("r", "replay", "Replay"),
            Binding("q", "quit", "Quit"),
        ]

        def __init__(self, anime, ep_num, total, quality):
            super().__init__()
            self.anime = anime
            self.ep_num = ep_num
            self.total = total
            self.quality = quality

        def compose(self) -> ComposeResult:
            yield Container(
                Static(f"[bold]{self.anime.title}[/bold]", id="p-title"),
                Static(f"Episode {self.ep_num}/{self.total} [{self.quality}]",
                       id="p-status"),
                Static("[dim]n=next  p=prev  r=replay  q=quit  esc=back[/dim]",
                       id="p-help"),
                id="player-overlay",
            )

        def action_next(self): pass
        def action_prev(self): pass
        def action_replay(self): pass
        def action_quit(self):
            from sni.player import Player
            p = Player()
            p.quit()
            self.dismiss()

    class SNIApp(App):
        """SNI Terminal UI Application."""
        CSS = """
        Screen { background: $surface; }
        #title { padding: 1 2; text-align: center; }
        #search { margin: 0 2; }
        #results { margin: 1 2; border: solid $primary; height: 1fr; }
        #anime-title { padding: 1 2; }
        #ep-info { padding: 0 2; }
        #ep-input { margin: 0 2; }
        #ep-list { margin: 1 2; border: solid $primary; height: 1fr; }
        #player-overlay {
            align: center middle;
            width: 60%; height: auto;
            padding: 2; border: solid $accent;
            background: $panel;
        }
        #p-title { text-align: center; padding: 1; }
        #p-status { text-align: center; padding: 1; }
        #p-help { text-align: center; padding: 1; color: $text-muted; }
        Footer { background: $primary; }
        """
        BINDINGS = [
            Binding("q", "quit", "Quit"),
            Binding("h", "show_history", "History"),
            Binding("?", "help", "Help"),
        ]
        TITLE = "SNI"
        SUB_TITLE = "Stream Ninja Interface"

        def compose(self) -> ComposeResult:
            yield Header()
            yield SearchScreen()
            yield Footer()

        def action_show_history(self):
            wh = WatchHistory()
            entries = wh.get_continue()
            if not entries:
                self.notify("No watch history yet", timeout=2)
                return
            # Show history as a simple notification
            lines = [f"{e['title']} - ep {e['episode']}" for e in entries[:5]]
            self.notify("\n".join(lines), title="Continue Watching", timeout=5)

        def action_help(self):
            self.notify(
                "Type to search, Enter to select.\n"
                "n=next  p=prev  r=replay  q=quit\n"
                "h=history  esc=back",
                title="Help", timeout=5
            )

    SNIApp().run()


def _run_cli_fallback():
    """Interactive CLI fallback when Textual is not installed."""
    console.print(Panel.fit(
        "[bold cyan]SNI — Stream Ninja Interface[/bold cyan]",
        border_style="bold blue",
    ))

    query = Prompt.ask("\nSearch for anime")
    if not query:
        return

    async def _run():
        results = await search_anime(query, limit=15)
        if not results:
            console.print("[red]No results found.[/red]")
            return

        table = Table(title="Search Results", show_header=True,
                      header_style="bold cyan")
        table.add_column("#", style="cyan", width=4)
        table.add_column("Title", style="white")
        table.add_column("Eps", style="green", width=6)
        table.add_column("Score", style="yellow", width=6)
        for i, r in enumerate(results, 1):
            eps = str(r.episodes) if r.episodes else "?"
            score = str(r.score) if r.score else ""
            table.add_row(str(i), r.title, eps, score)
        console.print(table)

        choice = Prompt.ask("\nSelect", default="1")
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(results):
                anime = results[idx]
                console.print(f"\n[bold green]{anime.title}[/bold green]")
                console.print(f"[dim]Episodes: {anime.episodes or '?'} | "
                              f"Score: {anime.score or 'N/A'}[/dim]")

                ep_choice = Prompt.ask(
                    "Episode (number or range like 1-12)", default="1"
                )

                cfg = Config.load()
                client = AllAnimeClient(cf_worker_url=cfg.get_cf_worker_url())
                aa_results = await client.search(anime.title, limit=5)
                if not aa_results:
                    console.print("[red]Not found on AllAnime.[/red]")
                    return

                episodes = await client.get_episodes(aa_results[0]["id"])
                if not episodes:
                    console.print("[red]No episodes found.[/red]")
                    return

                # Parse range
                if "-" in ep_choice:
                    parts = ep_choice.split("-")
                    start_ep = int(parts[0])
                    end_ep = int(parts[1])
                else:
                    start_ep = int(ep_choice)
                    end_ep = start_ep

                player = Player(player=cfg.player, use_ipc=cfg.use_ipc)
                history = WatchHistory()

                for ep in episodes:
                    if ep.number < start_ep:
                        continue
                    if ep.number > end_ep:
                        break

                    console.print(
                        f"\n[bold]Now Playing: {anime.title}[/bold] - "
                        f"Episode {ep.number}/{len(episodes)}"
                    )
                    try:
                        stream = await client.get_streams(
                            ep.id, quality=cfg.quality
                        )
                        player.play(stream, cfg.quality)
                        player.wait()
                    except Exception as e:
                        console.print(f"[red]{e}[/red]")
                        break

                    history.add(anime.id, anime.title, ep.number, len(episodes))

                    action = Prompt.ask(
                        "Next episode? [Enter=next / q=quit]", default=""
                    )
                    if action.lower().startswith("q"):
                        break

                console.print(f"\n[green]Finished watching {anime.title}![/green]")
        except (ValueError, IndexError):
            console.print("[red]Invalid selection.[/red]")

    asyncio.run(_run())
