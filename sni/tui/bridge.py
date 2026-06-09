import asyncio
from functools import lru_cache
from typing import Optional

from sni.config import Config
from sni.player import Player
from sni.providers.base import AnimeResult, Episode, Stream
from sni.providers.registry import ProviderRegistry
from sni.watch_history import WatchHistory


@lru_cache(maxsize=1)
def get_config() -> Config:
    return Config.load()


def get_provider(provider_name: str = ""):
    cfg = get_config()
    name = provider_name or cfg.default_provider
    cls = ProviderRegistry.get(name)
    if not cls:
        raise ValueError(f"Unknown provider: {name}")
    return cls()


async def search(
    query: str,
    provider_name: str = "",
    dub: bool = False,
) -> list[tuple[str, list[AnimeResult]]]:
    prov = get_provider(provider_name)
    results = await prov.search(query)
    return [(prov.name, results)]


async def get_episodes(
    anime_id: str,
    provider_name: str = "",
) -> list[Episode]:
    prov = get_provider(provider_name)
    return await prov.get_episodes(anime_id)


async def get_streams(
    episode_id: str,
    quality: str = "1080",
    dub: bool = False,
    provider_name: str = "",
) -> list[Stream]:
    prov = get_provider(provider_name)
    return await prov.get_streams(episode_id, quality, dub)


async def play_stream(stream: Stream, quality: str = "1080") -> int:
    player = Player()
    player.play(stream, quality)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, player.wait)


def get_history() -> list[dict]:
    return WatchHistory().get_continue()


def save_history(
    anime_id: str,
    anime_title: str,
    episode: int,
    provider: str,
    episode_id: str = "",
):
    wh = WatchHistory()
    wh.add_entry(
        anime_title=anime_title,
        anime_id=anime_id,
        provider=provider,
        episode_num=episode,
        episode_id=episode_id,
    )


def get_quality_options() -> list[str]:
    return ["360", "480", "720", "1080"]


def get_default_quality() -> str:
    return get_config().quality or "1080"


def get_providers() -> list[str]:
    return ProviderRegistry.list()
