"""AllAnime stream extraction — get playable stream URLs for anime episodes.

Uses the XAN endpoint pattern:
- POST /api/graphql for search + episode list
- GET /api?...&extensions=persistedQuery for stream sources

Fallback chain: direct → proxy.cors.sh → CF Worker (if configured)
"""

import base64
import json
import re
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from Crypto.Cipher import AES
from Crypto.Util import Counter

from sni.exceptions import StreamError

# ─── Constants ────────────────────────────────────────────────────────────

AES_KEY = sha256(b"Xot36i3lK3:v1").digest()
EPISODE_QUERY_HASH = "d405d0edd690624b66baba3068e0edc3ac90f1597d898a1ec8db4e5c43c00fec"

GRAPHQL_URL = "https://api.allanime.day/api/graphql"
API_URL = "https://api.allanime.day/api"
BASE_URL = "https://allanime.day"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0"
REFERER = "https://youtu-chan.com"
ORIGIN = "https://youtu-chan.com"
TIMEOUT = 30.0

# proxy.cors.sh is a free public CORS proxy that supports POST + JSON.
# Used as automatic fallback when direct request fails (no user config needed).
PUBLIC_PROXY = "https://proxy.cors.sh/{url}"

# Regex for scraping embed pages (mp4upload, filemoon, etc.)
_MP4_RE = re.compile(r"https?://[^\"'\s<>]+\.mp4(?:\?[^\"'\s<>]*)?(?=[\"'\s<>]|$)", re.I)
_HLS_RE = re.compile(r"https?://[^\"'\s<>]+\.m3u8[^\"'\s<>]*", re.I)
_ASSET_RE = re.compile(r"\.(css|js|png|jpe?g|gif|svg|woff2?|ttf|ico|webp|json|map)(\?|$)", re.I)


# ─── Data classes ─────────────────────────────────────────────────────────

@dataclass
class Episode:
    number: int
    id: str  # AllAnime episode ID (showId:epNum)


@dataclass
class Stream:
    url: str
    quality: str = "1080"
    headers: Dict[str, str] = field(default_factory=dict)


# ─── Helpers ──────────────────────────────────────────────────────────────

def _decrypt_tobeparsed(blob_b64: str):
    """Decrypt AllAnime's AES-256-CTR tobeparsed blob."""
    blob = base64.b64decode(blob_b64)
    if len(blob) < 32:
        return None
    iv = blob[1:13]
    ctr_block = iv + b"\x00\x00\x00\x02"
    ctr = Counter.new(128, initial_value=int.from_bytes(ctr_block, "big"))
    cipher = AES.new(AES_KEY, AES.MODE_CTR, counter=ctr)
    ct = blob[13:-16]
    decrypted = cipher.decrypt(ct)
    try:
        return json.loads(decrypted)
    except json.JSONDecodeError:
        return None


def decode_url(raw: str) -> str:
    """Decode AllAnime sourceUrl encoding (-- XOR 56, ap/ hex, or plain)."""
    if not raw:
        return raw
    if raw.startswith("--"):
        try:
            data = bytes.fromhex(raw[2:])
            return bytes(b ^ 56 for b in data).decode("utf-8", errors="replace")
        except ValueError:
            return raw
    if raw.startswith("ap/"):
        try:
            return bytes.fromhex(raw[3:]).decode("utf-8", errors="replace")
        except ValueError:
            return raw
    return raw


def _is_captcha(resp: httpx.Response) -> bool:
    """Check if response is a Cloudflare/captcha wall."""
    if resp.status_code >= 400:
        return True
    ct = resp.headers.get("content-type", "").lower()
    if "json" not in ct:
        return True
    body = resp.text[:300].lower()
    return "just a moment" in body or "cf-mitigated" in resp.headers


def _wrap_worker_url(worker_url: str, target: str, extra_headers: Optional[Dict] = None) -> str:
    """Build a CF Worker proxy URL."""
    params = {"url": target}
    for k, v in (extra_headers or {}).items():
        params[f"h_{k}"] = v
    return f"{worker_url}/?{urlencode(params)}"


def _origin_for(url: str) -> str:
    """Extract scheme://host from a URL."""
    try:
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}"
    except Exception:
        return url


# ─── AllAnime client ──────────────────────────────────────────────────────

class AllAnimeClient:
    """Simplified AllAnime client with automatic fallback."""

    def __init__(self, cf_worker_url: str = ""):
        self.cf_worker_url = (cf_worker_url or "").rstrip("/")
        self._worker_disabled = False
        self._use_proxy = False  # set True if direct fails

    def _headers(self, json_body: bool = False) -> Dict[str, str]:
        h = {"User-Agent": UA, "Accept": "application/json", "Referer": REFERER, "Origin": ORIGIN}
        if json_body:
            h["Content-Type"] = "application/json"
        return h

    async def _post_graphql(self, query: str, variables: dict) -> dict:
        """POST to /api/graphql with fallback: direct → proxy.cors.sh → worker."""
        payload = {"query": query, "variables": variables}

        # Build fallback chain
        urls = [("direct", GRAPHQL_URL)]
        urls.append(("proxy", PUBLIC_PROXY.format(url=GRAPHQL_URL)))
        if self.cf_worker_url and not self._worker_disabled:
            urls.append(("worker", _wrap_worker_url(
                self.cf_worker_url, GRAPHQL_URL,
                {"Referer": REFERER, "Origin": ORIGIN},
            )))

        for kind, url in urls:
            try:
                async with httpx.AsyncClient(
                    headers=self._headers(json_body=True),
                    follow_redirects=True,
                    timeout=TIMEOUT,
                ) as client:
                    resp = await client.post(url, json=payload)

                    if kind == "worker" and resp.status_code >= 500:
                        self._worker_disabled = True
                        continue
                    if _is_captcha(resp):
                        continue

                    raw = resp.json()
                    # Handle tobeparsed
                    data = raw.get("data") or {}
                    if data.get("tobeparsed"):
                        decrypted = _decrypt_tobeparsed(data["tobeparsed"])
                        if decrypted is not None:
                            raw["data"] = decrypted

                    # Check GraphQL errors
                    errors = raw.get("errors")
                    if errors:
                        msgs = [e.get("message", "") for e in errors]
                        if not all("Cannot set property" in m for m in msgs):
                            continue

                    return raw
            except (httpx.HTTPError, httpx.TimeoutException, json.JSONDecodeError):
                continue

        raise StreamError(
            "Could not connect to AllAnime. This is a NETWORK issue, not a captcha.\n"
            "Possible causes:\n"
            "  1. Your internet is down or unstable\n"
            "  2. Your ISP/firewall blocks api.allanime.day or proxy.cors.sh\n"
            "  3. You're on a restrictive network (school/work/country firewall)\n\n"
            "Try:\n"
            "  - Try a different network (mobile hotspot, VPN)\n"
            "  - If on a VPN, try WITHOUT it\n"
            "  - Try again in a few minutes"
        )

    async def _get_persisted(self, variables: dict) -> dict:
        """GET /api?...&extensions=persistedQuery with fallback."""
        extensions = {"persistedQuery": {"version": 1, "sha256Hash": EPISODE_QUERY_HASH}}
        params = {"variables": json.dumps(variables), "extensions": json.dumps(extensions)}
        direct_url = f"{API_URL}?{urlencode(params)}"

        urls = [("direct", direct_url)]
        urls.append(("proxy", PUBLIC_PROXY.format(url=direct_url)))
        if self.cf_worker_url and not self._worker_disabled:
            urls.append(("worker", _wrap_worker_url(
                self.cf_worker_url, direct_url,
                {"Referer": REFERER, "Origin": ORIGIN},
            )))

        for kind, url in urls:
            try:
                async with httpx.AsyncClient(
                    headers=self._headers(),
                    follow_redirects=True,
                    timeout=TIMEOUT,
                ) as client:
                    resp = await client.get(url)

                    if kind == "worker" and resp.status_code >= 500:
                        self._worker_disabled = True
                        continue
                    if _is_captcha(resp):
                        continue

                    raw = resp.json()
                    data = raw.get("data") or {}
                    if data.get("tobeparsed"):
                        decrypted = _decrypt_tobeparsed(data["tobeparsed"])
                        if decrypted is not None:
                            raw["data"] = decrypted

                    errors = raw.get("errors")
                    if errors:
                        msgs = [e.get("message", "") for e in errors]
                        if not all("Cannot set property" in m for m in msgs):
                            continue

                    return raw
            except (httpx.HTTPError, httpx.TimeoutException, json.JSONDecodeError):
                continue

        raise StreamError(
            "Could not connect to AllAnime for episode sources.\n"
            "Try a different network (mobile hotspot, VPN) or try again later."
        )

    # ─── Public API ───────────────────────────────────────────────────────

    async def search(self, query: str, limit: int = 20) -> List[dict]:
        """Search AllAnime by title. Returns list of {id, name, episodes}."""
        gql = "query($s:SearchInput,$limit:Int){shows(search:$s,limit:$limit){edges{_id name availableEpisodes}}}"
        variables = {"s": {"query": query}, "limit": limit}
        data = await self._post_graphql(gql, variables)
        edges = (data.get("data") or {}).get("shows", {}).get("edges", [])
        return [
            {
                "id": e.get("_id", ""),
                "name": e.get("name", "Unknown"),
                "episodes": (e.get("availableEpisodes") or {}).get("sub", 0),
            }
            for e in edges
        ]

    async def get_episodes(self, show_id: str, dub: bool = False) -> List[Episode]:
        """Get episode list for an AllAnime show.

        When dub=True, returns dubbed episode numbers instead of subbed.
        """
        gql = "query($id:String!){show(_id:$id){availableEpisodesDetail}}"
        variables = {"id": show_id}
        data = await self._post_graphql(gql, variables)
        detail = (data.get("data") or {}).get("show", {}).get("availableEpisodesDetail", {})
        # Use "dub" key for dub mode, "sub" for sub mode
        key = "dub" if dub else "sub"
        ep_nums = detail.get(key, [])
        # If dub list is empty but user wants dub, fall back to sub list
        # (the stream API will report "dub not available" if truly absent)
        if not ep_nums and dub:
            ep_nums = detail.get("sub", [])
        episodes = []
        for ep_str in ep_nums:
            try:
                num = int(ep_str)
                episodes.append(Episode(number=num, id=f"{show_id}:{num}"))
            except (ValueError, TypeError):
                continue
        episodes.sort(key=lambda e: e.number)
        return episodes

    async def get_streams(self, episode_id: str, quality: str = "1080", dub: bool = False) -> Optional[Stream]:
        """Get a playable stream for an episode.

        Tries sources in priority order:
        1. Yt-mp4 (direct MP4 from tools.fast4speed.rsvp) — most reliable
        2. S-mp4 (clock.json) — usually works
        3. Mp4 (mp4upload) — scrape embed page
        """
        show_id, ep_num = episode_id.rsplit(":", 1)
        mode = "dub" if dub else "sub"
        variables = {"showId": show_id, "episodeString": ep_num, "translationType": mode}
        data = await self._get_persisted(variables)

        episode_data = (data.get("data") or {}).get("episode")
        if not episode_data:
            raise StreamError(f"Episode not available{' (dub)' if dub else ''}.")

        sources = episode_data.get("sourceUrls", [])
        if not sources:
            raise StreamError("No stream sources found for this episode.")

        # Sort by priority: Yt-mp4 > S-mp4 > Mp4 > others
        def priority(src):
            n = (src.get("sourceName") or "").lower()
            p = src.get("priority", 0) or 0
            if "yt-mp4" in n:
                return 1000 + p
            if any(k in n for k in ("default", "sak", "wixmp", "luf-mp4", "s-mp4", "sl-mp4", "ss-hls")):
                return 500 + p
            if n == "mp4":
                return 300 + p
            return p

        sorted_sources = sorted(sources, key=priority, reverse=True)

        for src in sorted_sources:
            raw_url = src.get("sourceUrl", "")
            name = src.get("sourceName", "")
            stream = await self._extract_source(raw_url, name, quality)
            if stream:
                return stream

        raise StreamError("No playable stream found. Try a different episode or anime.")

    async def _extract_source(self, raw_url: str, source_name: str, quality: str) -> Optional[Stream]:
        """Extract a playable Stream from a sourceUrl."""
        url = decode_url(raw_url)
        name = (source_name or "").lower()

        # Yt-mp4 — direct MP4, most reliable
        if "yt-mp4" in name:
            if not url.startswith("http"):
                return None
            stream = Stream(url=url, quality=quality)
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            if "Authorization" in qs:
                stream.headers["Authorization"] = qs["Authorization"][0]
            stream.headers["Referer"] = REFERER
            stream.headers["Origin"] = ORIGIN
            # Wrap through CF Worker if configured (bypasses IP-based 403)
            if self.cf_worker_url and not self._worker_disabled:
                stream.url = _wrap_worker_url(
                    self.cf_worker_url, url,
                    {"Referer": REFERER, "Origin": ORIGIN},
                )
                stream.headers = {}
            return stream

        # clock.json family (S-mp4, Default, Sak, Wixmp, Luf-mp4, etc.)
        if any(k in name for k in ("default", "sak", "wixmp", "luf-mp4", "s-mp4", "sl-mp4", "ss-hls")):
            return await self._fetch_clock_json(url, quality)

        # mp4upload — scrape embed page
        if name == "mp4" or "mp4upload.com" in url.lower():
            return await self._scrape_embed(url, quality)

        # filemoon / vidnest / bysekoze — scrape embed page
        if any(k in name for k in ("fm-hls", "vn-hls")) or any(
            k in url.lower() for k in ("filemoon", "vidnest", "bysekoze")
        ):
            return await self._scrape_embed(url, quality)

        # Generic fallback
        if url.startswith("http"):
            stream = Stream(url=url, quality=quality)
            stream.headers["Referer"] = REFERER
            stream.headers["Origin"] = ORIGIN
            return stream

        return None

    async def _fetch_clock_json(self, path: str, quality: str) -> Optional[Stream]:
        """Fetch clock.json for S-mp4 / Default / Sak / Wixmp sources."""
        full_path = path.replace("/clock", "/clock.json")
        full_url = full_path if full_path.startswith("http") else f"{BASE_URL}{full_path}"

        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": UA, "Referer": REFERER, "Accept": "application/json"},
                follow_redirects=True,
                timeout=TIMEOUT,
            ) as client:
                resp = await client.get(full_url)
                if resp.status_code >= 400:
                    return None
                obj = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError):
            return None

        links = obj.get("links") or obj.get("sources") or []
        if not isinstance(links, list) or not links:
            return None

        # Pick best quality link
        best = None
        best_score = -1
        for link in links:
            if not isinstance(link, dict):
                continue
            link_url = link.get("link") or link.get("src") or link.get("url")
            if not link_url:
                continue
            res = link.get("resolutionStr") or link.get("quality") or link.get("label") or ""
            score = 0
            nums = re.findall(r"\d+", res)
            if nums:
                score = int(nums[0])
            if quality and quality in res:
                score += 10000
            if score > best_score:
                best_score = score
                best = link

        if not best:
            return None

        link_url = best.get("link") or best.get("src") or best.get("url")
        if not link_url:
            return None

        res = best.get("resolutionStr") or best.get("quality") or best.get("label") or quality
        stream = Stream(url=link_url, quality=str(res))
        stream.headers["Referer"] = REFERER
        stream.headers["Origin"] = ORIGIN
        # Wrap through CF Worker if configured
        if self.cf_worker_url and not self._worker_disabled:
            stream.url = _wrap_worker_url(
                self.cf_worker_url, link_url,
                {"Referer": REFERER, "Origin": ORIGIN},
            )
            stream.headers = {}
        return stream

    async def _scrape_embed(self, embed_url: str, quality: str) -> Optional[Stream]:
        """Scrape an embed page (mp4upload, filemoon, etc.) for direct video URL."""
        if not embed_url.startswith("http"):
            return None

        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": UA, "Referer": REFERER, "Accept": "text/html"},
                follow_redirects=True,
                timeout=TIMEOUT,
            ) as client:
                resp = await client.get(embed_url)
                if resp.status_code >= 400:
                    return None
                html = resp.text
                effective_url = str(resp.url)  # after redirects
        except httpx.HTTPError:
            return None

        def clean(u: str) -> str:
            return u.replace("\\/", "/").replace("\\u002F", "/").replace("&amp;", "&")

        # Try HLS first, then MP4
        for regex in (_HLS_RE, _MP4_RE):
            for match in regex.finditer(html):
                url = clean(match.group(0))
                if _ASSET_RE.search(url):
                    continue
                stream = Stream(url=url, quality=quality)
                # Use the embed URL (after redirects) as Referer — this is what
                # mp4upload and other CDNs check. Wrong Referer = 403 Forbidden.
                stream.headers["Referer"] = effective_url
                stream.headers["Origin"] = _origin_for(effective_url)
                # Wrap through CF Worker if configured
                if self.cf_worker_url and not self._worker_disabled:
                    stream.url = _wrap_worker_url(
                        self.cf_worker_url, url,
                        {"Referer": effective_url, "Origin": _origin_for(effective_url)},
                    )
                    stream.headers = {}
                return stream

        return None
