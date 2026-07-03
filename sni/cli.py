"""SNI CLI — Stream Ninja Interface v2.1

Commands:
  sni "one piece"            Search and play (sub)
  sni play "one piece"       Same as above
  sni play "one piece" -e 5  Start from episode 5
  sni play "one piece" -e 1-12  Play episodes 1 through 12
  sni-d "one piece"          Search and play (dub)
  sni search "one piece"     Search only
  sni tui                    Terminal UI mode
  sni config                 Show/set config
  sni config --interactive   Interactive config wizard
  sni history                Show watch history
  sni --version              Show version
  sni --debug play "X"       Debug mode (verbose mpv output)
"""

import asyncio
import os
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from sni import __version__
from sni.allanime import AllAnimeClient, Episode
from sni.anilist import AnimeResult, search_anime
from sni.config import DEFAULT_CONFIG_PATH, Config
from sni.exceptions import PlayerError, StreamError
from sni.player import Player
from sni.watch_history import WatchHistory

_IS_DUB = os.path.splitext(os.path.basename(sys.argv[0]))[0] in ("sni-d", "sni_dub")

app = typer.Typer(
    name="sni",
    help="Stream Ninja Interface — terminal anime streaming",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
_DEBUG = False


def _get_client() -> AllAnimeClient:
    cfg = Config.load()
    return AllAnimeClient(cf_worker_url=cfg.get_cf_worker_url())


def _select_anime(results: list[AnimeResult]) -> Optional[AnimeResult]:
    """Let user select an anime from search results using fzf or numbered list."""
    if not results:
        console.print("[red]No results found.[/red]")
        return None

    # Try fzf
    try:
        import subprocess
        lines = []
        for i, r in enumerate(results, 1):
            eps = f"{r.episodes} eps" if r.episodes else "?"
            score = f"★{r.score}" if r.score else ""
            lines.append(f"{i}. {r.title} ({eps}) {score}")
        proc = subprocess.run(
            ["fzf", "--prompt=Select anime: ", "--height=40%", "--reverse",
             "--preview-window=hidden"],
            input="\n".join(lines),
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            selected = proc.stdout.strip()
            idx = int(selected.split(".")[0]) - 1
            return results[idx]
    except (FileNotFoundError, ValueError, IndexError):
        pass

    # Fallback: rich table + numbered prompt
    table = Table(title="Search Results", show_header=True, header_style="bold cyan")
    table.add_column("#", style="cyan", width=4, justify="right")
    table.add_column("Title", style="white")
    table.add_column("Eps", style="green", width=6, justify="right")
    table.add_column("Score", style="yellow", width=6, justify="right")
    for i, r in enumerate(results, 1):
        eps = str(r.episodes) if r.episodes else "?"
        score = str(r.score) if r.score else ""
        table.add_row(str(i), r.title, eps, score)
    console.print(table)

    choice = IntPrompt.ask("Select", default=1)
    if 1 <= choice <= len(results):
        return results[choice - 1]
    return None


def _select_episode_range(episodes: list[Episode], title: str) -> tuple[int, int]:
    """Let user select an episode or range. Returns (start_idx, end_idx) inclusive."""
    if not episodes:
        return (0, 0)

    console.print(f"\n[bold green]{title}[/bold green] — {len(episodes)} episodes")
    console.print("[dim]Enter episode number (e.g. 5) or range (e.g. 1-12)[/dim]")
    choice = Prompt.ask("Episode", default="1")

    try:
        if "-" in choice:
            parts = choice.split("-")
            start_num = int(parts[0])
            end_num = int(parts[1])
        else:
            start_num = int(choice)
            end_num = start_num  # just one episode
    except ValueError:
        start_num = 1
        end_num = 1

    # Find indices
    start_idx = 0
    end_idx = len(episodes) - 1
    for i, ep in enumerate(episodes):
        if ep.number >= start_num:
            start_idx = i
            break
    for i, ep in enumerate(episodes):
        if ep.number >= end_num:
            end_idx = i
            break

    return (start_idx, end_idx)


async def _play_anime(
    anime: AnimeResult,
    start_ep: int = 1,
    end_ep: Optional[int] = None,
    dub: bool = False,
    quality: str = "1080",
):
    """Play an anime from start_ep to end_ep (or all remaining if end_ep=None)."""
    console.print(f"[dim]Searching AllAnime for: {anime.title}...[/dim]")
    client = _get_client()
    aa_results = await client.search(anime.title, limit=5)
    if not aa_results:
        console.print(f"[red]Could not find '{anime.title}' on AllAnime.[/red]")
        return

    show_id = aa_results[0]["id"]
    episodes = await client.get_episodes(show_id)
    if not episodes:
        console.print("[red]No episodes found.[/red]")
        return

    # Find start index
    start_idx = 0
    for i, ep in enumerate(episodes):
        if ep.number >= start_ep:
            start_idx = i
            break

    # Find end index
    if end_ep:
        end_idx = len(episodes) - 1
        for i, ep in enumerate(episodes):
            if ep.number >= end_ep:
                end_idx = i
                break
    else:
        end_idx = len(episodes) - 1

    ep_list = episodes[start_idx:end_idx + 1]
    total_eps = len(episodes)

    cfg = Config.load()
    player = Player(player=cfg.player, use_ipc=cfg.use_ipc, debug=_DEBUG)
    history = WatchHistory()

    for i, ep in enumerate(ep_list):
        console.print(
            f"\n[bold]Now Playing: {anime.title}[/bold] - "
            f"Episode {ep.number}/{total_eps}"
            f"{' [dim](dub)[/dim]' if dub else ''}"
        )

        try:
            stream = await client.get_streams(ep.id, quality=quality, dub=dub)
        except StreamError as e:
            console.print(f"[red]Stream error: {e}[/red]")
            continue

        if _DEBUG:
            console.print(f"[dim]Stream URL: {stream.url[:100]}...[/dim]")

        try:
            player.play(stream, quality)
            player.wait()
        except PlayerError as e:
            console.print(f"[red]{e}[/red]")
            break

        # Record in history
        history.add(anime.id, anime.title, ep.number, total_eps, dub)

        # Prompt for next episode
        if i < len(ep_list) - 1:
            next_ep = ep_list[i + 1]
            action = Prompt.ask(
                f"\nNext: episode {next_ep.number}? [Enter=next / q=quit]",
                default="",
            )
            if action.lower().startswith("q"):
                break

    console.print(f"\n[green]Finished watching {anime.title}![/green]")


@app.command()
def play(
    query: str = typer.Argument(None, help="Anime title to search"),
    episode: str = typer.Option("1", "--episode", "-e",
                                help="Episode number or range (e.g. 5 or 1-12)"),
    quality: str = typer.Option(None, "--quality", "-q",
                                help="Stream quality (360/480/720/1080)"),
    dub: bool = typer.Option(_IS_DUB, "--dub", "-d", help="Play dubbed version"),
):
    """Search and play an anime."""
    if not query:
        query = Prompt.ask("Search for anime")

    async def _run():
        console.print(f"[dim]Searching AniList for: {query}...[/dim]")
        results = await search_anime(query)
        if not results:
            console.print("[red]No results found.[/red]")
            return

        selected = _select_anime(results)
        if not selected:
            return

        # Check if user has watch history for this anime
        history = WatchHistory()
        last_ep = history.get_last_episode(selected.id, dub)
        if last_ep and last_ep < (selected.episodes or 9999):
            resume = Confirm.ask(
                f"Resume from episode {last_ep + 1}?", default=True
            )
            if resume:
                episode = str(last_ep + 1)

        cfg = Config.load()
        q = quality or cfg.quality

        # Parse episode range
        if "-" in episode:
            parts = episode.split("-")
            start_ep = int(parts[0])
            end_ep = int(parts[1])
        else:
            start_ep = int(episode)
            end_ep = None

        await _play_anime(selected, start_ep=start_ep, end_ep=end_ep,
                          dub=dub, quality=q)

    asyncio.run(_run())


@app.command()
def search(
    query: str = typer.Argument(..., help="Anime title to search"),
):
    """Search for anime (display results, don't play)."""
    async def _run():
        results = await search_anime(query)
        if not results:
            console.print("[red]No results found.[/red]")
            return

        table = Table(title=f"Search Results for '{query}'", show_header=True,
                      header_style="bold cyan")
        table.add_column("#", style="cyan", width=4, justify="right")
        table.add_column("Title", style="white")
        table.add_column("Eps", style="green", width=6, justify="right")
        table.add_column("Score", style="yellow", width=6, justify="right")
        for i, r in enumerate(results, 1):
            eps = str(r.episodes) if r.episodes else "?"
            score = str(r.score) if r.score else ""
            table.add_row(str(i), r.title, eps, score)
        console.print(table)

    asyncio.run(_run())


@app.command()
def history():
    """Show watch history."""
    wh = WatchHistory()
    entries = wh.get_continue()
    if not entries:
        console.print("[dim]No watch history yet.[/dim]")
        return

    table = Table(title="Continue Watching", show_header=True,
                  header_style="bold cyan")
    table.add_column("#", style="cyan", width=4)
    table.add_column("Title", style="white")
    table.add_column("Episode", style="green", width=10)
    table.add_column("Type", style="yellow", width=6)
    for i, e in enumerate(entries, 1):
        ep_str = f"{e['episode']}/{e['total']}" if e.get("total") else str(e["episode"])
        dub_str = "dub" if e.get("dub") else "sub"
        table.add_row(str(i), e["title"], ep_str, dub_str)
    console.print(table)


@app.command()
def tui():
    """Launch the Terminal UI."""
    from sni.tui import run_tui
    run_tui()


@app.command()
def config(
    show: bool = typer.Option(False, "--show", help="Show current config"),
    update: Optional[str] = typer.Option(None, "--update", help="Update config key=value"),
    interactive: bool = typer.Option(False, "--interactive", "-i",
                                     help="Interactive config wizard"),
    cookie_info: bool = typer.Option(False, "--cookie-info",
                                     help="Show captcha bypass info"),
):
    """Manage configuration."""
    if cookie_info:
        console.print(Panel(
            "[bold green]SNI v2.1 auto-fixes captcha.[/bold green]\n"
            "Search uses AniList (no captcha). Stream extraction uses\n"
            "AllAnime with automatic proxy.cors.sh fallback.\n\n"
            "[bold]If you STILL get errors:[/bold]\n\n"
            "[bold cyan]Option 1 — CF Worker (for blocked IPs):[/bold cyan]\n"
            "  Deploy worker code (see worker/ directory):\n"
            "    - Deno Deploy: https://dash.deno.com -> Playground -> main.ts\n"
            "    - Vercel: https://vercel.com -> api/proxy.js\n"
            "    - Cloudflare: https://dash.cloudflare.com\n"
            "  Then save:\n"
            "    sni config --update allanime_cf_worker_url='https://your-deployment'\n\n"
            "[bold yellow]Option 2 — VPN / mobile hotspot:[/bold yellow]\n"
            "  Your IP may be blocked by AllAnime's CDN. A VPN or mobile\n"
            "  hotspot gives you a different IP that isn't blocked.",
            title="Captcha bypass info",
            border_style="cyan",
        ))
        return

    if interactive:
        _run_wizard()
        return

    cfg = Config.load()
    if update:
        key, _, value = update.partition("=")
        if hasattr(cfg, key):
            current = getattr(cfg, key)
            if isinstance(current, bool):
                value = value.lower() in ("true", "1", "yes")
            elif isinstance(current, int):
                value = int(value)
            setattr(cfg, key, value)
            cfg.save()
            console.print(f"[green]Updated {key}={value}[/green]")
        else:
            console.print(f"[red]Unknown key: {key}[/red]")
            console.print("Available: player, quality, use_ipc, allanime_cf_worker_url, selector, icons")
    else:
        console.print(f"[bold]Config path:[/bold] {DEFAULT_CONFIG_PATH}")
        console.print(f"  [cyan]player:[/cyan]     {cfg.player}")
        console.print(f"  [cyan]quality:[/cyan]    {cfg.quality}")
        console.print(f"  [cyan]use_ipc:[/cyan]    {cfg.use_ipc}")
        console.print(f"  [cyan]cf_worker:[/cyan]  {cfg.get_cf_worker_url() or '(not set)'}")
        console.print(f"  [cyan]selector:[/cyan]   {cfg.selector}")


def _run_wizard():
    """Interactive config wizard."""
    console.print(Panel.fit("[bold]SNI Configuration Wizard[/bold]",
                            border_style="bold blue"))
    cfg = Config.load()

    cfg.quality = Prompt.ask(
        "Default quality", choices=["360", "480", "720", "1080"],
        default=cfg.quality,
    )
    cfg.player = Prompt.ask(
        "Video player", choices=["mpv", "vlc"], default=cfg.player,
    )
    cfg.use_ipc = Confirm.ask("Enable mpv IPC controls?", default=True)

    worker = Prompt.ask(
        "CF Worker URL (leave empty if none)", default=cfg.get_cf_worker_url()
    ).strip()
    cfg.allanime_cf_worker_url = worker

    cfg.save()
    console.print(f"\n[green]Config saved to {DEFAULT_CONFIG_PATH}[/green]")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show version"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug output"),
):
    global _DEBUG
    if debug:
        _DEBUG = True
    if version:
        console.print(f"sni v{__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        if ctx.args:
            play(query=ctx.args[0], episode="1", quality=None, dub=_IS_DUB)
        else:
            console.print(f"[bold]SNI v{__version__}[/bold] — Stream Ninja Interface")
            console.print(
                "Usage: sni \"one piece\"  |  sni play \"one piece\" -e 1-12  |  sni tui  |  sni --help"
            )


if __name__ == "__main__":
    app()
