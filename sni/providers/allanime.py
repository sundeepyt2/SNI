import base64
import json
from hashlib import sha256
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import httpx
from Crypto.Cipher import AES
from Crypto.Util import Counter

from sni.exceptions import ProviderError, StreamError
from sni.providers.base import AnimeResult, Episode, Provider, Stream
from sni.providers.cache import cache
from sni.providers.extractors.megacloud import MegacloudExtractor
from sni.providers.extractors.vixcloud import VixcloudExtractor
from sni.providers.registry import ProviderRegistry

AES_KEY = sha256(b"Xot36i3lK3:v1").digest()
EPISODE_QUERY_HASH = "d405d0edd690624b66baba3068e0edc3ac90f1597d898a1ec8db4e5c43c00fec"


def _decrypt_tobeparsed(blob_b64: str) -> Any:
    blob = base64.b64decode(blob_b64)
    iv = blob[1:13]
    ctr_block = iv + b"\x00\x00\x00\x02"
    ctr = Counter.new(128, initial_value=int.from_bytes(ctr_block, "big"))
    cipher = AES.new(AES_KEY, AES.MODE_CTR, counter=ctr)
    ct_len = len(blob) - 13 - 16
    ciphertext = blob[13 : 13 + ct_len]
    decrypted = cipher.decrypt(ciphertext)
    try:
        return json.loads(decrypted)
    except json.JSONDecodeError:
        return decrypted.decode("utf-8", errors="replace")


class AllAnimeProvider(Provider):
    name = "allanime"
    domain = "allanime.day"
    supports_sub = True
    supports_dub = True

    API_URL = "https://api.allanime.day/api"
    REFERER = "https://youtu-chan.com"

    def __init__(self, cookies: str = ""):
        self.cookies_str = cookies
        self._cookies: Dict[str, str] = {}
        if cookies:
            for part in cookies.split(";"):
                part = part.strip()
                if "=" in part:
                    k, v = part.split("=", 1)
                    self._cookies[k.strip()] = v.strip()

    async def _graphql(self, query: str, variables: dict, use_persisted: bool = False) -> dict:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Content-Type": "application/json",
            "Origin": self.REFERER,
            "Referer": self.REFERER,
        }
        async with httpx.AsyncClient(
            headers=headers, cookies=self._cookies, follow_redirects=True, timeout=30
        ) as client:
            if use_persisted:
                payload = {
                    "variables": variables,
                    "extensions": {"persistedQuery": {"version": 1, "sha256Hash": EPISODE_QUERY_HASH}},
                }
            else:
                payload = {"query": query, "variables": variables}
            resp = await client.post(self.API_URL, json=payload)
            resp.raise_for_status()
            raw = resp.json()

            tobeparsed = raw.get("data", {}).get("tobeparsed")
            if tobeparsed:
                decrypted = _decrypt_tobeparsed(tobeparsed)
                raw["data"] = decrypted

            errors = raw.get("errors")
            if errors:
                msgs = [e.get("message", "") for e in errors]
                if msgs and all("Cannot set property" in m for m in msgs):
                    pass
                elif msgs:
                    raise ProviderError(f"AllAnime API error: {', '.join(msgs)}")
            return raw

    async def search(self, query: str) -> List[AnimeResult]:
        cache_key = f"allanime:search:{query.lower()}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        gql = """
        query($search: SearchInput, $limit: Int, $page: Int,
              $translationType: VaildTranslationTypeEnumType,
              $countryOrigin: VaildCountryOriginEnumType) {
            shows(search: $search, limit: $limit, page: $page,
                  translationType: $translationType,
                  countryOrigin: $countryOrigin) {
                edges {
                    _id
                    name
                    availableEpisodes
                    thumbnail
                }
            }
        }
        """
        variables = {
            "search": {"allowAdult": False, "allowUnknown": False, "query": query},
            "limit": 40,
            "page": 1,
            "translationType": "sub",
            "countryOrigin": "ALL",
        }
        data = await self._graphql(gql, variables)
        results = []
        for edge in data.get("data", {}).get("shows", {}).get("edges", []):
            eps = edge.get("availableEpisodes")
            if isinstance(eps, dict):
                eps = eps.get("sub", 0) or eps.get("raw", 0)
            results.append(
                AnimeResult(
                    id=edge.get("_id", ""),
                    title=edge.get("name", "Unknown"),
                    episodes=int(eps) if eps else None,
                    image=edge.get("thumbnail"),
                )
            )
        cache.set(cache_key, results, ttl=120)
        return results

    async def get_episodes(self, anime_id: str) -> List[Episode]:
        cache_key = f"allanime:episodes:{anime_id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        gql = """
        query($showId: String!) {
            show(_id: $showId) {
                _id
                name
                availableEpisodesDetail
            }
        }
        """
        variables = {"showId": anime_id}
        data = await self._graphql(gql, variables)
        detail = data.get("data", {}).get("show", {}).get("availableEpisodesDetail", {})
        ep_nums = detail.get("sub", [])
        episodes = []
        for ep_str in ep_nums:
            try:
                ep_num = int(ep_str)
            except (ValueError, TypeError):
                continue
            episodes.append(Episode(id=f"{anime_id}:{ep_num}", number=ep_num))
        episodes.sort(key=lambda e: e.number)

        cache.set(cache_key, episodes, ttl=300)
        return episodes

    async def get_streams(
        self, episode_id: str, quality: str = "1080", dub: bool = False
    ) -> List[Stream]:
        cache_key = f"allanime:streams:{episode_id}:{quality}:{dub}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        if ":" in episode_id:
            show_id, ep_num = episode_id.rsplit(":", 1)
        else:
            show_id = episode_id
            ep_num = "1"

        mode = "dub" if dub else "sub"
        variables = {
            "showId": show_id,
            "translationType": mode,
            "episodeString": ep_num,
        }

        data = await self._graphql("", variables, use_persisted=True)
        episode_data = data.get("data", {}).get("episode")
        if not episode_data:
            if dub:
                raise ProviderError("Dub not available for this episode.")
            raise ProviderError("Episode not available.")

        sources = episode_data.get("sourceUrls", [])
        if not sources:
            raise ProviderError("No stream sources found.")

        sources.sort(key=lambda s: -(s.get("priority", 0) or 0))

        for src in sources:
            url = src.get("sourceUrl", "")
            src_name = src.get("sourceName", "")

            stream = await self._extract_source(url, src_name, quality)
            if stream:
                cache.set(cache_key, [stream], ttl=600)
                return [stream]

        raise ProviderError("No stream sources available.")

    @staticmethod
    async def _extract_source(url: str, source_name: str, quality: str) -> Optional[Stream]:
        source_lower = source_name.lower()
        url_lower = url.lower()

        if "mp4upload" in url_lower:
            return None

        if source_name == "Yt-mp4":
            headers = {}
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            if "Authorization" in qs:
                headers["Authorization"] = qs["Authorization"][0]
            stream = Stream(url=url, quality=quality)
            stream.headers.update(headers)
            if "tools.fast4speed.rsvp" in url_lower:
                stream.headers["Origin"] = "https://allanime.day"
                stream.headers["Referer"] = "https://allanime.day/"
            return stream

        if source_name in ("S-mp4", "Luf-Mp4"):
            return None

        if "megacloud" in url_lower:
            try:
                streams = await MegacloudExtractor.extract(url, quality)
                if streams:
                    return streams[0]
            except StreamError:
                pass

        if "vixcloud" in url_lower:
            try:
                streams = await VixcloudExtractor.extract(url, quality)
                if streams:
                    return streams[0]
            except StreamError:
                pass

        return None


ProviderRegistry.register(AllAnimeProvider)
