from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from sni.config import Config

console = Console()


def run_wizard(path: Path) -> Config:
    console.print(Panel.fit("SNI Configuration Wizard", border_style="bold blue"))
    console.print("Let's set up your preferences.\n")

    default_provider = Prompt.ask(
        "Default provider",
        choices=["allanime", "hianime", "animepahe"],
        default="allanime",
    )
    selector = Prompt.ask(
        "Search selector",
        choices=["fzf", "builtin"],
        default="fzf",
    )
    player = Prompt.ask(
        "Video player",
        choices=["mpv", "vlc"],
        default="mpv",
    )
    quality = Prompt.ask(
        "Default quality",
        choices=["360", "480", "720", "1080"],
        default="1080",
    )
    translation = Prompt.ask(
        "Default translation",
        choices=["sub", "dub"],
        default="sub",
    )
    auto_next = Confirm.ask("Auto-play next episode?", default=True)
    use_ipc = Confirm.ask("Enable MPV IPC controls?", default=True)
    icons = Confirm.ask("Show icons in UI?", default=True)

    allanime_cookies = ""
    allanime_cf_worker_url = ""
    if default_provider == "allanime":
        console.print(
            "\n[dim]AllAnime sometimes blocks API requests with a captcha / Cloudflare wall. "
            "You can skip this and add a fix later with `sni config --cookie-info`.[/dim]"
        )
        if Confirm.ask(
            "Bypass AllAnime captcha via a Cloudflare Worker? (recommended)",
            default=False,
        ):
            allanime_cf_worker_url = Prompt.ask(
                "Paste your CF Worker URL (e.g. https://xan-proxy.you.workers.dev)",
                default="",
            ).strip()
        if Confirm.ask(
            "Also set AllAnime browser cookies? "
            "(only if Worker alone doesn't work)",
            default=False,
        ):
            allanime_cookies = Prompt.ask(
                "Paste cookie string (k1=v1; k2=v2)",
                default="",
            ).strip()

    cfg = Config(
        default_provider=default_provider,
        selector=selector,
        preview="full",
        icons=icons,
        player=player,
        quality=quality,
        translation_type=translation,
        auto_next=auto_next,
        use_ipc=use_ipc,
        allanime_cookies=allanime_cookies,
        allanime_cf_worker_url=allanime_cf_worker_url,
    )
    cfg.save(path)

    console.print(f"\n[green]Config saved to {path}[/green]")
    return cfg
