"""SNI TUI — simple terminal UI using Textual.

Provides a visual interface for searching and playing anime.
If Textual is not installed, falls back to the CLI.
"""

import asyncio

from rich.console import Console
from rich.prompt import Prompt

from sni.allanime import AllAnimeClient
from sni.anilist import search_anime
from sni.config import Config
from sni.player import Player

console = Console()


def run_tui():
    """Run the TUI. Falls back to interactive CLI if Textual isn't available."""
    try:
        from textual.app import App, ComposeResult
        from textual.reactive import reactive
        from textual.widgets import Input, Label, ListItem, ListView, Static
        _TEXTUAL_AVAILABLE = True
    except ImportError:
        _TEXTUAL_AVAILABLE = False

    if not _TEXTUAL_AVAILABLE:
        return _run_cli_fallback()

    class SNIApp(App):
        CSS = """
        Screen { align: center middle; }
        #search-box { width: 80%; margin: 1; }
        #results { width: 80%; height: 70%; }
        .title { text-align: center; padding: 1; }
        """

        results = reactive([])
        anilist_results = reactive([])

        def compose(self) -> ComposeResult:
            yield Static("SNI — Stream Ninja Interface", classes="title")
            yield Input(id="search-box", placeholder="Search for anime...")
            yield ListView(id="results")

        def on_input_submitted(self, event: Input.Submitted):
            if event.input.id == "search-box":
                self.run_worker(self.do_search(event.value))

        async def do_search(self, query: str):
            lv = self.query_one("#results", ListView)
            lv.clear()
            lv.append(ListItem(Label(f"Searching for '{query}'...")))
            results = await search_anime(query)
            self.anilist_results = results
            lv.clear()
            if not results:
                lv.append(ListItem(Label("No results found.")))
                return
            for r in results:
                eps = f"{r.episodes} eps" if r.episodes else "?"
                lv.append(ListItem(Label(f"{r.title} ({eps})")))

        def on_list_view_selected(self, event: ListView.Selected):
            idx = event.list_view.index
            if idx is not None and idx < len(self.anilist_results):
                self.run_worker(self.play_anime(self.anilist_results[idx]))

        async def play_anime(self, anime):
            self.exit()
            console.print(f"\n[bold green]Playing: {anime.title}[/bold green]")
            cfg = Config.load()
            client = AllAnimeClient(cf_worker_url=cfg.get_cf_worker_url())

            # Find on AllAnime
            results = await client.search(anime.title, limit=5)
            if not results:
                console.print("[red]Not found on AllAnime.[/red]")
                return

            show_id = results[0]["id"]
            episodes = await client.get_episodes(show_id)
            if not episodes:
                console.print("[red]No episodes found.[/red]")
                return

            console.print(f"[dim]{len(episodes)} episodes available. Starting from episode 1.[/dim]")

            player = Player(player=cfg.player, use_ipc=cfg.use_ipc)
            for ep in episodes:
                console.print(f"\n[bold]Now Playing: {anime.title} - Episode {ep.number}/{len(episodes)}[/bold]")
                try:
                    stream = await client.get_streams(ep.id, quality=cfg.quality)
                    player.play(stream, cfg.quality)
                    player.wait()
                except Exception as e:
                    console.print(f"[red]{e}[/red]")
                    break

                from rich.prompt import Prompt
                action = Prompt.ask("Next episode? [Enter=next / q=quit]", default="")
                if action.lower().startswith("q"):
                    break

    SNIApp().run()


def _run_cli_fallback():
    """Interactive CLI fallback when Textual is not installed."""
    console.print("[bold]SNI — Stream Ninja Interface[/bold]\n")

    query = Prompt.ask("Search for anime")
    if not query:
        return

    async def _run():
        results = await search_anime(query)
        if not results:
            console.print("[red]No results found.[/red]")
            return

        for i, r in enumerate(results, 1):
            eps = f"{r.episodes} eps" if r.episodes else "?"
            console.print(f"  {i}. {r.title} ({eps})")

        choice = Prompt.ask("\nSelect", default="1")
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(results):
                anime = results[idx]
                console.print(f"\n[bold green]Playing: {anime.title}[/bold green]")

                cfg = Config.load()
                client = AllAnimeClient(cf_worker_url=cfg.get_cf_worker_url())
                aa_results = await client.search(anime.title, limit=5)
                if not aa_results:
                    console.print("[red]Not found on AllAnime.[/red]")
                    return

                show_id = aa_results[0]["id"]
                episodes = await client.get_episodes(show_id)
                if not episodes:
                    console.print("[red]No episodes found.[/red]")
                    return

                player = Player(player=cfg.player, use_ipc=cfg.use_ipc)
                for ep in episodes:
                    console.print(f"\n[bold]Now Playing: {anime.title} - Episode {ep.number}/{len(episodes)}[/bold]")
                    try:
                        stream = await client.get_streams(ep.id, quality=cfg.quality)
                        player.play(stream, cfg.quality)
                        player.wait()
                    except Exception as e:
                        console.print(f"[red]{e}[/red]")
                        break

                    action = Prompt.ask("Next episode? [Enter=next / q=quit]", default="")
                    if action.lower().startswith("q"):
                        break
        except (ValueError, IndexError):
            console.print("[red]Invalid selection.[/red]")

    asyncio.run(_run())
