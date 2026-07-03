"""SNI CLI — Stream Ninja Interface v2.0

Commands:
  sni "one piece"          Search and play (sub)
  sni play "one piece"     Same as above
  sni-d "one piece"        Search and play (dub)
  sni search "one piece"   Search only
  sni tui                  Terminal UI mode
  sni config               Show/set config
  sni --version            Show version
  sni --debug play "X"     Debug mode (verbose mpv output)
"""

import asyncio
import os
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from sni import __version__
from sni.allanime import AllAnimeClient, Episode
from sni.anilist import AnimeResult, search_anime
from sni.config import DEFAULT_CONFIG_PATH, Config
from sni.exceptions import PlayerError, StreamError
from sni.player import Player

# Detect if we're running as sni-d (dub mode)
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
    """Let user select an anime from search results."""
    if not results:
        console.print("[red]No results found.[/red]")
        return None

    # Try fzf first
    try:
        import subprocess
        lines = []
        for i, r in enumerate(results, 1):
            eps = f"{r.episodes} eps" if r.episodes else "?"
            score = f"{r.score}/100" if r.score else ""
            lines.append(f"{i}. {r.title} ({eps}) {score}")
        proc = subprocess.run(
            ["fzf", "--prompt=Select anime: ", "--height=40%", "--reverse"],
            input="\n".join(lines),
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            # Parse selected line number
            selected = proc.stdout.strip()
            idx = int(selected.split(".")[0]) - 1
            return results[idx]
    except (FileNotFoundError, ValueError, IndexError):
        pass

    # Fallback: numbered selection
    table = Table(title="Search Results", show_header=True)
    table.add_column("#", style="cyan", width=4)
    table.add_column("Title", style="white")
    table.add_column("Episodes", style="green", width=10)
    table.add_column("Score", style="yellow", width=8)
    for i, r in enumerate(results, 1):
        eps = str(r.episodes) if r.episodes else "?"
        score = f"{r.score}" if r.score else ""
        table.add_row(str(i), r.title, eps, score)
    console.print(table)

    from rich.prompt import IntPrompt
    choice = IntPrompt.ask("Select", default=1)
    if 1 <= choice <= len(results):
        return results[choice - 1]
    return None


def _select_episode(episodes: list[Episode], title: str) -> Optional[Episode]:
    """Let user select an episode."""
    if not episodes:
        console.print("[red]No episodes found.[/red]")
        return None

    console.print(f"\n[bold green]{title}[/bold green] — {len(episodes)} episodes available")
    from rich.prompt import Prompt
    choice = Prompt.ask(
        f"Episode (1-{len(episodes)}, or 'range' like 1-12)",
        default="1"
    )
    try:
        if "-" in choice:
            parts = choice.split("-")
            start = int(parts[0])
            # Just return the first episode in range; the play loop will continue
            idx = start - 1
        else:
            idx = int(choice) - 1
        if 0 <= idx < len(episodes):
            return episodes[idx]
    except (ValueError, IndexError):
        pass
    return episodes[0] if episodes else None


async def _find_allanime_show(title: str) -> Optional[str]:
    """Search AllAnime by title and return the best match's ID."""
    client = _get_client()
    results = await client.search(title, limit=5)
    if not results:
        return None
    # Return the first result (most relevant)
    return results[0]["id"]


async def _play_anime(anime: AnimeResult, start_ep: int = 1, dub: bool = False, quality: str = "1080"):
    """Play an anime from a specific episode."""
    # Find the show on AllAnime
    console.print(f"[dim]Searching AllAnime for: {anime.title}...[/dim]")
    show_id = await _find_allanime_show(anime.title)
    if not show_id:
        console.print(f"[red]Could not find '{anime.title}' on AllAnime.[/red]")
        return

    # Get episodes
    client = _get_client()
    episodes = await client.get_episodes(show_id)
    if not episodes:
        console.print("[red]No episodes found.[/red]")
        return

    # Find the starting episode
    start_idx = 0
    for i, ep in enumerate(episodes):
        if ep.number >= start_ep:
            start_idx = i
            break

    # Play episodes starting from start_idx
    cfg = Config.load()
    player = Player(player=cfg.player, use_ipc=cfg.use_ipc, debug=_DEBUG)

    current_idx = start_idx
    while current_idx < len(episodes):
        ep = episodes[current_idx]
        total = len(episodes)

        console.print(f"\n[bold]Now Playing: {anime.title} - Episode {ep.number}/{total}[/bold]")
        if dub:
            console.print("[dim](dub)[/dim]")

        try:
            stream = await client.get_streams(ep.id, quality=quality, dub=dub)
        except StreamError as e:
            console.print(f"[red]Stream error: {e}[/red]")
            # Try next episode
            current_idx += 1
            continue

        # Show stream info in debug mode
        if _DEBUG:
            console.print(f"[dim]Stream URL: {stream.url[:100]}...[/dim]")
            console.print(f"[dim]Headers: {stream.headers}[/dim]")

        try:
            player.play(stream, quality)
            player.wait()
        except PlayerError as e:
            console.print(f"[red]{e}[/red]")
            break

        current_idx += 1
        if current_idx < len(episodes):
            from rich.prompt import Prompt
            action = Prompt.ask(
                f"\nNext: episode {episodes[current_idx].number}? [Enter=next / q=quit]",
                default="",
            )
            if action.lower().startswith("q"):
                break


@app.command()
def play(
    query: str = typer.Argument(None, help="Anime title to search"),
    episode: int = typer.Option(1, "--episode", "-e", help="Starting episode number"),
    quality: str = typer.Option(None, "--quality", "-q", help="Stream quality (360/480/720/1080)"),
    dub: bool = typer.Option(_IS_DUB, "--dub", "-d", help="Play dubbed version"),
):
    """Search and play an anime."""
    if not query:
        from rich.prompt import Prompt
        query = Prompt.ask("Search for anime")

    async def _run():
        # Search via AniList (reliable, no captcha)
        console.print(f"[dim]Searching AniList for: {query}...[/dim]")
        results = await search_anime(query)
        if not results:
            console.print("[red]No results found.[/red]")
            return

        # Let user select
        selected = _select_anime(results)
        if not selected:
            return

        # Get quality from config if not specified
        cfg = Config.load()
        q = quality or cfg.quality

        # Play
        await _play_anime(selected, start_ep=episode, dub=dub, quality=q)

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

        table = Table(title=f"Search Results for '{query}'", show_header=True)
        table.add_column("#", style="cyan", width=4)
        table.add_column("Title", style="white")
        table.add_column("Episodes", style="green", width=10)
        table.add_column("Score", style="yellow", width=8)
        for i, r in enumerate(results, 1):
            eps = str(r.episodes) if r.episodes else "?"
            score = f"{r.score}" if r.score else ""
            table.add_row(str(i), r.title, eps, score)
        console.print(table)

    asyncio.run(_run())


@app.command()
def tui():
    """Launch the Terminal UI."""
    from sni.tui import run_tui
    run_tui()


@app.command()
def config(
    show: bool = typer.Option(False, "--show", help="Show current config"),
    update: Optional[str] = typer.Option(None, "--update", help="Update config key=value"),
    cookie_info: bool = typer.Option(False, "--cookie-info", help="Show captcha bypass info"),
):
    """Manage configuration."""
    if cookie_info:
        console.print(Panel(
            "[bold green]SNI v2.0 auto-fixes captcha.[/bold green]\n"
            "When AllAnime captcha-walls your IP, SNI automatically retries\n"
            "through proxy.cors.sh (a free public proxy). Zero setup needed.\n\n"
            "[bold]If you STILL get errors (all proxies failed):[/bold]\n\n"
            "[bold cyan]Option 1 — Browser cookies:[/bold cyan]\n"
            "  Get cookies from allmanga.to, then:\n"
            "    sni config --update allanime_cookies='cf_clearance=...;'\n\n"
            "[bold yellow]Option 2 — CF Worker (for VPN/shared IPs):[/bold yellow]\n"
            "  Deploy worker code (see worker/ directory in the repo):\n"
            "    - Deno Deploy: https://dash.deno.com -> Playground -> paste main.ts\n"
            "    - Vercel: https://vercel.com -> api/proxy.js\n"
            "    - Cloudflare Workers: https://dash.cloudflare.com\n"
            "  Then save:\n"
            "    sni config --update allanime_cf_worker_url='https://your-deployment'",
            title="AllAnime captcha bypass",
            border_style="cyan",
        ))
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
            console.print("Available keys: player, quality, use_ipc, allanime_cf_worker_url, selector, icons")
    else:
        console.print(f"[bold]Config path:[/bold] {DEFAULT_CONFIG_PATH}")
        console.print(f"  player: {cfg.player}")
        console.print(f"  quality: {cfg.quality}")
        console.print(f"  use_ipc: {cfg.use_ipc}")
        console.print(f"  cf_worker_url: {cfg.get_cf_worker_url() or '(not set)'}")
        console.print(f"  selector: {cfg.selector}")


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
        # If no subcommand, treat first arg as search query for play
        if ctx.args:
            play(query=ctx.args[0], episode=1, quality=None, dub=_IS_DUB)
        else:
            console.print(f"[bold]SNI v{__version__}[/bold] — Stream Ninja Interface")
            console.print("Usage: sni \"one piece\"  |  sni play \"one piece\"  |  sni tui  |  sni --help")


if __name__ == "__main__":
    app()
