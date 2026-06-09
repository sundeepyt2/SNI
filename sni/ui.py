import asyncio
import os
import shutil
from typing import List, Optional

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from sni.providers.base import AnimeResult, Episode

console = Console()


def _has_tty() -> bool:
    try:
        return os.isatty(0) and os.isatty(1)
    except OSError:
        return False


def _format_episodes(episodes) -> str:
    if episodes is None:
        return ""
    if isinstance(episodes, dict):
        return str(episodes.get("sub", ""))
    return str(episodes)


def format_anime_row(anime: AnimeResult, index: int) -> str:
    year = f"({anime.year})" if anime.year else ""
    score = f" {anime.score}" if anime.score else ""
    eps = _format_episodes(anime.episodes)
    eps_str = f" {eps}eps" if eps else ""
    parts = [f"{index + 1}. {anime.title} {year}"]
    extras = "".join(filter(None, [score, eps_str]))
    if extras:
        parts.append(f"   {extras}")
    return "\n".join(parts)


def format_episode_row(ep: Episode, index: int) -> str:
    title = f" - {ep.title}" if ep.title else ""
    return f"{index + 1}. Episode {ep.number}{title}"


def display_results(results: List[AnimeResult], provider: str = "") -> None:
    table = Table(title=f"Search Results [{provider}]" if provider else "Search Results")
    table.add_column("#", style="dim", width=4)
    table.add_column("Title", style="bold")
    table.add_column("Year", width=6)
    table.add_column("Score", width=6)
    table.add_column("Episodes", width=8)

    for i, anime in enumerate(results[:30], 1):
        score = f"{anime.score:.1f}" if anime.score else ""
        eps = _format_episodes(anime.episodes)
        table.add_row(str(i), anime.title, str(anime.year or ""), score, eps)

    console.print(table)


def display_episodes(episodes: List[Episode], anime_title: str = "") -> None:
    title = f"Episodes - {anime_title}" if anime_title else "Episodes"
    table = Table(title=title)
    table.add_column("#", style="dim", width=4)
    table.add_column("Episode", style="bold")
    if any(e.title for e in episodes):
        table.add_column("Title")

    for i, ep in enumerate(episodes, 1):
        row = [str(i), f"Episode {ep.number}"]
        if any(e.title for e in episodes):
            row.append(ep.title or "")
        table.add_row(*row)

    console.print(table)


async def select_with_fzf(items: list, format_fn=None) -> Optional[object]:
    if not shutil.which("fzf") or not _has_tty():
        return select_fallback(items, format_fn=format_fn)

    format_fn = format_fn or (lambda item, i: f"{i + 1}. {item}")
    lines = [format_fn(r, i) for i, r in enumerate(items)]
    input_str = "\n".join(lines)

    try:
        proc = await asyncio.create_subprocess_exec(
            "fzf",
            "--prompt=Select > ",
            "--height=60%",
            "--layout=reverse",
            "--border",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate(input_str.encode())
        if proc.returncode != 0 or not stdout:
            return select_fallback(items, format_fn=format_fn)
    except Exception:
        return select_fallback(items, format_fn=format_fn)

    selected_line = stdout.decode().strip()
    for i, item in enumerate(items):
        if selected_line.startswith(f"{i + 1}."):
            return item
    return None


async def select_episode_fzf(episodes: List[Episode]) -> Optional[Episode]:
    if not shutil.which("fzf") or not _has_tty():
        return select_fallback(episodes, format_fn=format_episode_row)

    lines = [format_episode_row(ep, i) for i, ep in enumerate(episodes)]
    input_str = "\n".join(lines)

    try:
        proc = await asyncio.create_subprocess_exec(
            "fzf",
            "--prompt=Select episode > ",
            "--height=60%",
            "--layout=reverse",
            "--border",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate(input_str.encode())
        if proc.returncode != 0 or not stdout:
            return select_fallback(episodes, format_fn=format_episode_row)
    except Exception:
        return select_fallback(episodes, format_fn=format_episode_row)

    selected_line = stdout.decode().strip()
    for i, ep in enumerate(episodes):
        if selected_line.startswith(f"{i + 1}."):
            return ep
    return None


def select_fallback(items: list, format_fn=None) -> Optional[object]:
    if not items:
        return None

    if len(items) == 1:
        return items[0]

    format_fn = format_fn or (lambda item, i: f"{i + 1}. {item}")
    for i, item in enumerate(items):
        print(format_fn(item, i))

    while True:
        try:
            choice = input("\nEnter number (or 'q' to quit): ").strip()
            if choice.lower() in ("q", "quit"):
                return None
            idx = int(choice) - 1
            if 0 <= idx < len(items):
                return items[idx]
            print(f"Enter a number between 1 and {len(items)}")
        except (ValueError, EOFError, KeyboardInterrupt):
            return None


def prompt_next_episode(current_ep: int, total_eps: int) -> str:
    if current_ep >= total_eps:
        console.print("[yellow]This was the last episode![/yellow]")
        return "q"

    console.print(f"\n[bold]Episode {current_ep} finished.[/bold]")
    console.print(f"  [dim]Next: Episode {current_ep + 1}/{total_eps}[/dim]")
    result = Prompt.ask(
        "What now?",
        choices=["n", "p", "s", "q"],
        default="n",
        show_choices=True,
    )
    return result


def show_now_playing(anime_title: str, ep_num: int, total_eps: int, quality: str):
    msg = "[bold green] Now Playing:[/bold green]"
    msg += f" {anime_title} - Episode {ep_num}/{total_eps} [{quality}]"
    console.print(msg)
