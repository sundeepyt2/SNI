from typing import List
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from sni.exceptions import ProviderError
from sni.providers.base import AnimeResult, Episode, Provider, Stream
from sni.providers.cache import cache
from sni.providers.extractors.vixcloud import VixcloudExtractor
from sni.providers.registry import ProviderRegistry


class AnimepaheProvider(Provider):
    name = "animepahe"
    domain = "animepahe.ch"
    supports_sub = True
    supports_dub = False

    BASE_URL = "https://animepahe.ch"
    API_URL = "https://animepahe.ch/api"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    async def _get_json(self, url: str) -> dict:
        async with httpx.AsyncClient(
            headers={"User-Agent": self.USER_AGENT},
            follow_redirects=True,
            timeout=30,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()

    async def search(self, query: str) -> List[AnimeResult]:
        cache_key = f"animepahe:search:{query.lower()}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        url = f"{self.API_URL}?m=search&q={quote(query)}"
        data = await self._get_json(url)
        results = []
        for item in data.get("data", []):
            results.append(AnimeResult(
                id=str(item.get("id", "")),
                title=item.get("title", "Unknown"),
                year=item.get("year"),
                score=item.get("score"),
                episodes=item.get("episodes"),
                image=item.get("poster"),
            ))

        cache.set(cache_key, results, ttl=120)
        return results

    async def get_episodes(self, anime_id: str) -> List[Episode]:
        cache_key = f"animepahe:episodes:{anime_id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        episodes = []
        page = 1
        async with httpx.AsyncClient(
            headers={"User-Agent": self.USER_AGENT},
            follow_redirects=True,
            timeout=30,
        ) as client:
            while True:
                url = f"{self.API_URL}?m=episode&id={anime_id}&page={page}"
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                for item in data.get("data", []):
                    ep_num = item.get("episode", 0)
                    ep_id = item.get("id", "")
                    title = item.get("title", "")
                    image = item.get("image") or item.get("snapshot")
                    episodes.append(Episode(
                        id=str(ep_id),
                        number=int(ep_num),
                        title=title,
                        image=image,
                    ))
                if not data.get("next_page_url"):
                    break
                page += 1

        cache.set(cache_key, episodes, ttl=300)
        return episodes

    async def get_streams(
        self, episode_id: str, quality: str = "1080", dub: bool = False
    ) -> List[Stream]:
        cache_key = f"animepahe:streams:{episode_id}:{quality}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        async with httpx.AsyncClient(
            headers={"User-Agent": self.USER_AGENT},
            follow_redirects=True,
            timeout=30,
        ) as client:
            url = f"{self.BASE_URL}/play/{episode_id}"
            resp = await client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            iframe = soup.select_one("iframe#player")
            if not iframe:
                raise ProviderError("No player iframe found on animepahe page")
            embed_url = iframe.get("src", "")
            if embed_url.startswith("//"):
                embed_url = "https:" + embed_url

        streams = await VixcloudExtractor.extract(embed_url, quality)
        cache.set(cache_key, streams, ttl=600)
        return streams


ProviderRegistry.register(AnimepaheProvider)
