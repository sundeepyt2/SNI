from typing import List
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from sni.exceptions import ProviderError
from sni.providers.base import AnimeResult, Episode, Provider, Stream
from sni.providers.cache import cache
from sni.providers.extractors.megacloud import MegacloudExtractor
from sni.providers.registry import ProviderRegistry


class HiAnimeProvider(Provider):
    name = "hianime"
    domain = "hianime.to"
    supports_sub = True
    supports_dub = True

    BASE_URL = "https://hianime.to"
    AJAX_URL = "https://hianime.to/ajax"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    async def _get_soup(self, url: str) -> BeautifulSoup:
        async with httpx.AsyncClient(
            headers={"User-Agent": self.USER_AGENT},
            follow_redirects=True,
            timeout=30,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")

    async def _ajax(self, url: str) -> dict:
        async with httpx.AsyncClient(
            headers={
                "User-Agent": self.USER_AGENT,
                "X-Requested-With": "XMLHttpRequest",
            },
            follow_redirects=True,
            timeout=30,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()

    async def search(self, query: str) -> List[AnimeResult]:
        cache_key = f"hianime:search:{query.lower()}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        url = f"{self.BASE_URL}/search?keyword={quote(query)}"
        soup = await self._get_soup(url)
        results = []

        for item in soup.select(".film-item"):
            link = item.select_one("a")
            if not link:
                continue
            anime_id = link.get("href", "").strip("/")
            title_el = item.select_one(".film-name")
            title = title_el.text.strip() if title_el else "Unknown"
            year_el = item.select_one(".fdi-item")
            year = None
            if year_el:
                try:
                    year = int(year_el.text.strip())
                except ValueError:
                    pass
            img = link.select_one("img")
            image = img.get("data-src") or img.get("src") if img else None

            results.append(AnimeResult(
                id=anime_id,
                title=title,
                year=year,
                image=image,
            ))

        cache.set(cache_key, results, ttl=120)
        return results

    async def get_episodes(self, anime_id: str) -> List[Episode]:
        cache_key = f"hianime:episodes:{anime_id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        ep_start = 0
        episodes = []
        async with httpx.AsyncClient(
            headers={"User-Agent": self.USER_AGENT},
            follow_redirects=True,
            timeout=30,
        ) as client:
            while True:
                url = f"{self.AJAX_URL}/v2/episode/list/{anime_id}?epStart={ep_start}"
                resp = await client.get(url, headers={"X-Requested-With": "XMLHttpRequest"})
                resp.raise_for_status()
                data = resp.json()
                html = data.get("html", "")
                if not html:
                    break
                soup = BeautifulSoup(html, "html.parser")
                for item in soup.select(".ep-item"):
                    ep_id = item.get("data-id")
                    ep_num = int(item.get("data-number", 0))
                    title = item.get("data-title", "")
                    img = item.select_one("img")
                    image = img.get("data-src") or img.get("src") if img else None
                    episodes.append(Episode(id=ep_id, number=ep_num, title=title, image=image))
                total = data.get("total", 0)
                if len(episodes) >= total:
                    break
                ep_start += len(episodes) or 50

        cache.set(cache_key, episodes, ttl=300)
        return episodes

    async def get_servers(self, episode_id: str) -> dict:
        url = f"{self.AJAX_URL}/v2/episode/servers?episodeId={episode_id}"
        data = await self._ajax(url)
        servers = {}
        html = data.get("html", "")
        soup = BeautifulSoup(html, "html.parser")
        for item in soup.select(".server-item"):
            type_ = item.get("data-type")
            server_id = item.get("data-id")
            if type_ and server_id:
                servers[type_] = server_id
        return servers

    async def get_streams(
        self, episode_id: str, quality: str = "1080", dub: bool = False
    ) -> List[Stream]:
        cache_key = f"hianime:streams:{episode_id}:{quality}:{dub}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        servers = await self.get_servers(episode_id)
        sub_type = "2" if dub else "1"
        server_id = servers.get(sub_type)
        if not server_id:
            raise ProviderError(f"No {'dub' if dub else 'sub'} server found for episode")

        sources_url = f"{self.AJAX_URL}/v2/episode/sources?id={server_id}"
        data = await self._ajax(sources_url)
        embed_link = data.get("link", "")
        if not embed_link:
            raise ProviderError("No embed link found from HiAnime servers")

        streams = await MegacloudExtractor.extract(embed_link, quality)
        cache.set(cache_key, streams, ttl=600)
        return streams


ProviderRegistry.register(HiAnimeProvider)
