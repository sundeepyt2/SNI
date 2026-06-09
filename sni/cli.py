import asyncio
import os
import sys
from typing import Optional

import typer
from rich.prompt import Prompt

from sni import __version__
from sni.config import DEFAULT_CONFIG_PATH, Config
from sni.exceptions import ProviderError, ProviderNotFoundError
from sni.logger import setup_logger
from sni.player import Player
from sni.providers.base import AnimeResult
from sni.providers.registry import ProviderRegistry
from sni.ui import (
    display_episodes,
    display_results,
    format_anime_row,
    prompt_next_episode,
    select_episode_fzf,
    select_with_fzf,
    show_now_playing,
)
from sni.watch_history import WatchHistory
from sni.wizard import run_wizard

_IS_DUB = os.path.splitext(os.path.basename(sys.argv[0]))[0] in ("sni-d", "sni_dub")

app = typer.Typer(
    name="sni",
    help="Stream Ninja Interface - Anime CLI",
    no_args_is_help=False,
)
logger = setup_logger()


def version_callback(value: bool):
    if value:
        typer.echo(f"sni v{__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", help="Show version", callback=version_callback,
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    if debug:
        global logger
        logger = setup_logger(debug=True)
    if ctx.invoked_subcommand is None:
        asyncio.run(_interactive())


async def _search(
    query: str,
    provider_name: Optional[str] = None,
    all_providers: bool = False,
) -> list[tuple[str, list[AnimeResult]]]:
    results: list[tuple[str, list[AnimeResult]]] = []

    if all_providers:
        for pname in ProviderRegistry.list():
            provider_cls = ProviderRegistry.get(pname)
            if not provider_cls:
                continue
            try:
                provider = provider_cls()
                hits = await provider.search(query)
                results.append((pname, hits))
            except Exception as e:
                logger.exception(f"{pname} search failed for '{query}'")
                logger.warning(f"{pname} search failed: {type(e).__name__}: {e}")
    elif provider_name:
        provider_cls = ProviderRegistry.get(provider_name)
        if not provider_cls:
            typer.echo(f"Unknown provider: {provider_name}")
            return results
        try:
            provider = provider_cls()
            hits = await provider.search(query)
            results.append((provider_name, hits))
        except Exception as e:
            logger.exception(f"Search failed for '{query}' with provider '{provider_name}'")
            typer.echo(f"Search failed: {type(e).__name__}: {e}")
    else:
        cfg = Config.load()
        preferred = cfg.default_provider
        hits = await ProviderRegistry.search_all(query, preferred)
        for pname, plist in hits.items():
            if plist:
                results.append((pname, plist))

    return results


async def _interactive():
    mode = Prompt.ask("Mode", choices=["play", "watch"], default="play")
    query = Prompt.ask("Search for anime")
    if mode == "play":
        await _play(query, None, None, _IS_DUB, None, None)
    else:
        await _watch(query, None, None, _IS_DUB, None, None, False)


async def _play(
    query: str,
    provider: Optional[str],
    quality: Optional[str],
    dub: bool,
    episodes: Optional[str],
    cookie: Optional[str],
):
    cfg = Config.load()
    provider_name = provider or cfg.default_provider

    results = await _search(query, provider_name)
    if not results:
        typer.echo("No results found.")
        return

    all_anime = [a for _, hits in results for a in hits]
    selected = await select_with_fzf(all_anime, format_fn=format_anime_row)
    if not selected:
        typer.echo("No selection made.")
        return

    await _watch_anime(selected, provider_name, dub, quality, episodes, cookie)


async def _watch(
    query: Optional[str],
    provider: Optional[str],
    quality: Optional[str],
    dub: bool,
    episodes: Optional[str],
    cookie: Optional[str],
    resume: bool = False,
):
    cfg = Config.load()
    provider_name = provider or cfg.default_provider

    if resume:
        history = WatchHistory()
        entries = history.get_continue()
        if not entries:
            typer.echo("No watch history found.")
            return

        display_results(
            [AnimeResult(id=e["anime_id"], title=e["anime_title"]) for e in entries],
            provider="history",
        )
        selected_entry = await select_with_fzf(
            entries,
            format_fn=lambda e, i: f"{i + 1}. {e['anime_title']} (ep {e['last_episode']})",
        )
        if not selected_entry:
            typer.echo("No selection made.")
            return

        provider_name = selected_entry["provider"]
        selected = AnimeResult(
            id=selected_entry["anime_id"],
            title=selected_entry["anime_title"],
        )
        ep_str = str(selected_entry["last_episode"])
        await _watch_anime(selected, provider_name, dub, quality, ep_str, cookie)
        return

    if not query:
        typer.echo("Please provide a search query or use --resume.")
        return

    results = await _search(query, provider_name)
    if not results:
        typer.echo("No results found.")
        return

    all_anime = [a for _, hits in results for a in hits]
    selected = await select_with_fzf(all_anime, format_fn=format_anime_row)
    if not selected:
        typer.echo("No selection made.")
        return

    await _watch_anime(selected, provider_name, dub, quality, episodes, cookie)


@app.command()
def search(
    query: str = typer.Argument(..., help="Anime title to search"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Provider to use"),
    all_providers: bool = typer.Option(False, "--all-providers", help="Search all providers"),
):
    """Search for anime."""
    asyncio.run(_search_cmd(query, provider, all_providers))


async def _search_cmd(query: str, provider: Optional[str], all_providers: bool):
    if all_providers:
        results = await _search(query, all_providers=True)
    else:
        cfg = Config.load()
        provider_name = provider or cfg.default_provider
        results = await _search(query, provider_name=provider_name)

    if not results:
        typer.echo("No results found.")
        raise typer.Exit()

    all_anime = []
    for pname, hits in results:
        display_results(hits, provider=pname)
        all_anime.extend(hits)

    selected = await select_with_fzf(all_anime, format_fn=format_anime_row)
    if selected:
        typer.echo(f"Selected: {selected.title} (id: {selected.id})")


async def _play_episode(
    player: Player,
    prov,
    episode,
    anime_title: str,
    total_eps: int,
    quality: str,
    dub: bool,
):
    try:
        streams = await prov.get_streams(episode.id, quality, dub)
    except ProviderError as e:
        msg = str(e)
        if dub and ("dub" in msg.lower() or "server" in msg.lower()):
            typer.echo("Dub not available for this episode.")
        else:
            typer.echo(f"Stream error: {e}")
        return False

    if not streams:
        if dub:
            typer.echo("Dub not available for this episode.")
        else:
            typer.echo("No streams available.")
        return False

    stream = streams[0]
    show_now_playing(anime_title, episode.number, total_eps, stream.quality)
    try:
        player.play(stream, quality, subtitles=True)
        player.wait()
    except Exception as e:
        typer.echo(f"Playback error: {e}")
        return False
    return True


async def _watch_anime(
    selected: AnimeResult,
    provider_name: str,
    dub: bool,
    quality: str,
    episodes: Optional[str],
    cookie: Optional[str] = None,
):
    cfg = Config.load()
    q = quality or cfg.quality
    translate_dub = dub or (cfg.translation_type == "dub")

    provider_cls = ProviderRegistry.get(provider_name)
    if not provider_cls:
        raise ProviderNotFoundError(f"Unknown provider: {provider_name}")
    prov = provider_cls(cookies=cookie or "")

    ep_list = await prov.get_episodes(selected.id)
    if not ep_list:
        typer.echo("No episodes found.")
        raise typer.Exit()

    ep_list.sort(key=lambda e: e.number)

    display_episodes(ep_list, selected.title)

    if episodes:
        try:
            parts = episodes.split("-")
            start_num = int(parts[0])
            if len(parts) > 1:
                end_num = int(parts[1])
                ep_list = [e for e in ep_list if start_num <= e.number <= end_num]
            else:
                ep_list = [e for e in ep_list if e.number >= start_num]
        except (ValueError, IndexError):
            pass
    else:
        chosen = await select_episode_fzf(ep_list)
        if not chosen:
            typer.echo("No episode selected.")
            raise typer.Exit()
        start_idx = ep_list.index(chosen)
        ep_list = ep_list[start_idx:]

    player = Player(player=cfg.player, use_ipc=cfg.use_ipc)
    if not player.available:
        typer.echo(f"{cfg.player} is not installed.")
        raise typer.Exit()

    history = WatchHistory()
    current_idx = 0

    while current_idx < len(ep_list):
        ep = ep_list[current_idx]
        last_num = ep_list[-1].number
        ok = await _play_episode(player, prov, ep, selected.title, last_num, q, translate_dub)
        if not ok:
            break

        history.add_entry(
            anime_title=selected.title,
            anime_id=selected.id,
            provider=provider_name,
            episode_num=ep.number,
            episode_id=ep.id,
        )

        current_idx += 1
        if current_idx >= len(ep_list):
            typer.echo(f"[green]Finished watching {selected.title}![/green]")
            break

        action = prompt_next_episode(ep.number, ep_list[-1].number)
        if action == "q":
            break
        elif action == "p":
            current_idx = max(0, current_idx - 2)
        elif action == "s":
            chosen = await select_episode_fzf(ep_list[current_idx:])
            if chosen:
                current_idx = ep_list.index(chosen)
        elif action == "n":
            pass


@app.command()
def play(
    query: str = typer.Argument(None, help="Anime title to search and play"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Provider to use"),
    quality: Optional[str] = typer.Option(None, "--quality", "-q", help="Stream quality"),
    dub: bool = typer.Option(_IS_DUB, "--dub", "-d", help="Use dubbed version"),
    episodes: Optional[str] = typer.Option(
        None, "--episodes", "-e", help="Episode range (e.g. 1-12)",
    ),
    cookie: Optional[str] = typer.Option(
        None, "--cookie", help="Browser cookies for providers that need them (allanime)",
    ),
):
    """Search and play an anime (ani-cli like interactive flow)."""
    asyncio.run(_play(query, provider, quality, dub, episodes, cookie))


@app.command()
def watch(
    query: Optional[str] = typer.Argument(None, help="Anime title to search and watch"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Provider to use"),
    quality: Optional[str] = typer.Option(None, "--quality", "-q", help="Stream quality"),
    dub: bool = typer.Option(_IS_DUB, "--dub", "-d", help="Use dubbed version"),
    episodes: Optional[str] = typer.Option(
        None, "--episodes", "-e", help="Episode range (e.g. 1-12)",
    ),
    resume: bool = typer.Option(False, "--resume", "-r", help="Continue watching from history"),
    cookie: Optional[str] = typer.Option(
        None, "--cookie", help="Browser cookies for providers that need them (allanime)",
    ),
):
    """Watch anime with ani-cli like interactive flow. Supports continue/resume."""
    asyncio.run(_watch(query, provider, quality, dub, episodes, cookie, resume))


@app.command()
def config(
    path: bool = typer.Option(False, "--path", help="Show config path"),
    edit: bool = typer.Option(False, "--edit", help="Open config in editor"),
    interactive: bool = typer.Option(False, "--interactive", help="Interactive config wizard"),
    update: Optional[str] = typer.Option(None, "--update", help="Update config key=value"),
):
    """Manage configuration."""
    if path:
        typer.echo(str(DEFAULT_CONFIG_PATH))
        return

    if interactive:
        run_wizard(DEFAULT_CONFIG_PATH)
        return

    cfg = Config.load()
    if edit:
        import subprocess
        editor = "vim"
        subprocess.call([editor, str(DEFAULT_CONFIG_PATH)])
    elif update:
        key, _, value = update.partition("=")
        if hasattr(cfg, key):
            current = getattr(cfg, key)
            typed_val: str | int | bool = value
            if isinstance(current, bool):
                typed_val = value.lower() in ("true", "1", "yes")
            elif isinstance(current, int):
                typed_val = int(value)
            setattr(cfg, key, typed_val)
            cfg.save()
            typer.echo(f"Updated {key}={typed_val}")
        else:
            typer.echo(f"Unknown key: {key}")
    else:
        typer.echo(f"Config path: {DEFAULT_CONFIG_PATH}")


@app.command()
def provider(
    action: str = typer.Argument("list", help="Action: list, status"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Provider name"),
):
    """Manage providers."""
    if action == "list":
        typer.echo("Available providers:")
        for p in ProviderRegistry.list():
            typer.echo(f"  - {p}")
    elif action == "status":
        typer.echo("Checking provider health...")
        status = asyncio.run(ProviderRegistry.health_check_all())
        for p, ok in status.items():
            icon = "\u2713" if ok else "\u2717"
            typer.echo(f"  {icon} {p}")


@app.command()
def tui():
    """Launch the Terminal UI."""
    from sni.tui.app import SNIApp
    SNIApp().run()

if __name__ == "__main__":
    app()
