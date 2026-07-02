"""AllAnime provider — ported from XAN's TypeScript implementation.

Key differences from the previous SNI version (which kept hitting
``NEED_CAPTCHA``):

1. **Two endpoints** instead of one:
   - ``POST https://api.allanime.day/api/graphql`` for regular GraphQL
     queries (search, show-by-id).
   - ``GET https://api.allanime.day/api?variables=...&extensions=...`` for
     the persisted episode-source query.
   The single-endpoint POST-everything approach SNI used previously is the
   pattern Cloudflare's edge flags as suspicious. XAN's split avoids it
   without needing cf_clearance cookies.

2. **Optional Cloudflare Worker fallback.** When the user's IP is
   captcha-walled, the request is retried through a user-deployed CF Worker
   (see XAN/cf-worker/worker.js). Set ``allanime_cf_worker_url`` in config.

3. **Source URL decoding** (``--`` XOR 56, ``ap/`` hex) — XAN exposes
   source URLs that are encoded; we now decode them before dispatching.

4. **clock.json extractor** for S-mp4 / Luf-mp4 / Default / Sak / Wixmp /
   SS-Hls / S1-mp4 / S2-mp4 / S3-mp4 sources, plus an HTML embed scraper
   for mp4upload / filemoon / vidnest / vizcloud / mycloud.
"""

import base64
import json
import re
from hashlib import sha256
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from Crypto.Cipher import AES
from Crypto.Util import Counter

from sni.exceptions import CaptchaRequiredError, ProviderError, StreamError
from sni.providers.base import AnimeResult, Episode, Provider, Stream
from sni.providers.cache import cache
from sni.providers.extractors.megacloud import MegacloudExtractor
from sni.providers.extractors.vixcloud import VixcloudExtractor
from sni.providers.registry import ProviderRegistry

AES_KEY = sha256(b"Xot36i3lK3:v1").digest()
EPISODE_QUERY_HASH = "d405d0edd690624b66baba3068e0edc3ac90f1597d898a1ec8db4e5c43c00fec"

# Substrings in AllAnime GraphQL error messages that indicate a captcha /
# Cloudflare challenge rather than a transient API error.
CAPTCHA_MARKERS = ("need_captcha", "captcha", "challenge", "cloudflare", "forbidden")

# Browser-like UA matching the one XAN uses. AllAnime's edge treats browser
# UAs more leniently than the generic python-httpx UA.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) "
    "Gecko/20100101 Firefox/150.0"
)
REFERER = "https://youtu-chan.com"
ORIGIN = "https://youtu-chan.com"

REQUEST_TIMEOUT = 15.0
CLOCK_TIMEOUT = 20.0

# Regex used by the embed scraper to pull HLS / MP4 URLs out of HTML pages.
# Mirrors XAN's scrapeEmbedPage regexes.
_ASSET_EXT = re.compile(r"\.(css|js|png|jpe?g|gif|svg|woff2?|ttf|ico|webp|json|map)(\?|$)", re.I)
_HLS_RE = re.compile(r"https?://[^\"'\s<>]+\.m3u8[^\"'\s<>]*", re.I)
_MP4_RE = re.compile(r"https?://[^\"'\s<>]+\.mp4(?:\?[^\"'\s<>]*)?(?=[\"'\s<>]|$)", re.I)


def _decrypt_tobeparsed(blob_b64: str) -> Any:
    """Decrypt the AES-256-CTR ``tobeparsed`` blob returned by AllAnime.

    Layout (per XAN's TS port):
      byte 0       : version flag (0x01) — skipped
      bytes 1..13  : 12-byte IV
      counter      : IV ++ b"\\x00\\x00\\x00\\x02"  (16-byte CTR block, starts at 2)
      bytes 13..-16: ciphertext
      last 16 bytes: MAC (ignored in CTR mode)
    """
    blob = base64.b64decode(blob_b64)
    if len(blob) < 32:
        return None
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


def decode_url(raw: str) -> str:
    """Decode an AllAnime ``sourceUrl`` value.

    Three forms observed in the wild (mirrors XAN's decodeUrl):
      - ``"--<hex>"``  → hex-decode then XOR every byte with 56
      - ``"ap/<hex>"`` → plain hex-decode
      - anything else  → returned as-is (already a URL)
    """
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


def _build_cf_worker_url(
    worker_url: str,
    target: str,
    extra_headers: Optional[Dict[str, str]] = None,
) -> str:
    """Wrap an upstream URL with the CF Worker proxy URL (XAN's protocol).

    Worker expects: ``<worker>/?url=<encoded>&h_<Header>=<value>...``
    """
    params = {"url": target}
    for k, v in (extra_headers or {}).items():
        params[f"h_{k}"] = v
    return f"{worker_url}/?{urlencode(params)}"


def _is_captcha_response(resp: httpx.Response) -> bool:
    """Heuristic: response is a Cloudflare/captcha wall rather than JSON."""
    if resp.status_code >= 400:
        return True
    ct = resp.headers.get("content-type", "").lower()
    if "json" not in ct:
        return True
    # Sometimes CF serves a 200 with a "Just a moment..." HTML stub and a
    # JSON-ish content-type. Cheap text check catches it.
    body_start = resp.text[:300].lower()
    return "just a moment" in body_start or "cf-mitigated" in resp.headers


class AllAnimeProvider(Provider):
    name = "allanime"
    domain = "allanime.day"
    supports_sub = True
    supports_dub = True

    # AllAnime API mirrors. When the primary api.allanime.day captcha-walls
    # the user's IP, SNI automatically retries the same request against each
    # mirror in order. Mirrors are tried BEFORE the CF Worker fallback because
    # they require zero setup from the user.
    #
    # Format: (api_graphql_url, api_url, allanime_base_url)
    API_MIRRORS = [
        # Primary — most reliable when not captcha-walled
        ("https://api.allanime.day/api/graphql",
         "https://api.allanime.day/api",
         "https://allanime.day"),
        # Mirror 1 — allmanga.to (sister site, shared backend)
        ("https://api.allmanga.to/api/graphql",
         "https://api.allmanga.to/api",
         "https://allmanga.to"),
    ]

    ALLANIME_BASE = "https://allanime.day"
    REFERER = REFERER
    ORIGIN = ORIGIN

    def __init__(self, cookies: str = "", cf_worker_url: str = ""):
        self.cookies_str = cookies
        self._cookies: Dict[str, str] = {}
        if cookies:
            for part in cookies.split(";"):
                part = part.strip()
                if "=" in part:
                    k, v = part.split("=", 1)
                    self._cookies[k.strip()] = v.strip()
        self.cf_worker_url = (cf_worker_url or "").rstrip("/")
        # Tracks which mirror actually worked, so we can reuse it on subsequent
        # calls instead of trying the primary every time.
        self._working_mirror_idx: Optional[int] = None

    def _mirror(self, idx: int) -> tuple:
        return self.API_MIRRORS[idx]

    def _base_headers(self, *, json_body: bool = False) -> Dict[str, str]:
        h = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Referer": self.REFERER,
            "Origin": self.ORIGIN,
        }
        if json_body:
            h["Content-Type"] = "application/json"
        return h

    async def _post_graphql(self, query: str, variables: dict) -> dict:
        """POST a regular GraphQL query to /api/graphql.

        Tries each API mirror in order. If a mirror has previously worked
        during this session, that mirror is tried first (faster). On the
        first captcha from a mirror, SNI silently moves to the next mirror.
        Only when ALL mirrors fail does it raise CaptchaRequiredError.
        """
        payload = {"query": query, "variables": variables}
        headers = self._base_headers(json_body=True)

        # Build the list of mirror indices to try, starting with the
        # previously-working one (if any) so we don't repeat failures.
        order = list(range(len(self.API_MIRRORS)))
        if self._working_mirror_idx is not None:
            order.remove(self._working_mirror_idx)
            order.insert(0, self._working_mirror_idx)

        last_error: Optional[Exception] = None
        for idx in order:
            graphql_url, _api_url, _base_url = self._mirror(idx)
            async with httpx.AsyncClient(
                headers=headers,
                cookies=self._cookies,
                follow_redirects=True,
                timeout=REQUEST_TIMEOUT,
            ) as client:
                try:
                    resp = await client.post(graphql_url, json=payload)
                except (httpx.HTTPError, httpx.TimeoutException) as e:
                    # Network error — try next mirror
                    last_error = e
                    continue

                if _is_captcha_response(resp):
                    # This mirror is captcha-walled — try the next one
                    last_error = CaptchaRequiredError(
                        f"AllAnime mirror {idx} ({graphql_url}) returned "
                        f"HTTP {resp.status_code}",
                    )
                    continue

                try:
                    raw = resp.json()
                except (ValueError, json.JSONDecodeError):
                    last_error = ProviderError(
                        f"Mirror {idx} returned non-JSON: {resp.text[:200]}",
                    )
                    continue

                try:
                    self._check_graphql_errors(raw)
                except CaptchaRequiredError as e:
                    last_error = e
                    continue

                # Success — remember this mirror for next time
                self._working_mirror_idx = idx
                return raw

        # All mirrors failed
        raise last_error or CaptchaRequiredError(
            "All AllAnime API mirrors failed for /api/graphql",
        )

    async def _get_persisted(self, variables: dict) -> dict:
        """GET /api?variables=...&extensions=persistedQuery...

        Tries each API mirror in order (same as _post_graphql), then falls
        back to the CF Worker if configured. CaptchaRequiredError is raised
        only when all mirrors AND the CF Worker fail.
        """
        extensions = {"persistedQuery": {"version": 1, "sha256Hash": EPISODE_QUERY_HASH}}
        params = {
            "variables": json.dumps(variables),
            "extensions": json.dumps(extensions),
        }

        order = list(range(len(self.API_MIRRORS)))
        if self._working_mirror_idx is not None:
            order.remove(self._working_mirror_idx)
            order.insert(0, self._working_mirror_idx)

        last_error: Optional[Exception] = None
        for idx in order:
            _gql_url, api_url, _base_url = self._mirror(idx)
            direct_url = f"{api_url}?{urlencode(params)}"

            async with httpx.AsyncClient(
                headers=self._base_headers(),
                cookies=self._cookies,
                follow_redirects=True,
                timeout=REQUEST_TIMEOUT,
            ) as client:
                try:
                    resp = await client.get(direct_url)
                except (httpx.HTTPError, httpx.TimeoutException) as e:
                    last_error = e
                    continue

                if _is_captcha_response(resp):
                    # Try CF Worker fallback for this mirror (only the
                    # persisted-query GET can go through a CF Worker — the
                    # GraphQL POST can't because Workers are GET-only).
                    if self.cf_worker_url:
                        wrapped = _build_cf_worker_url(
                            self.cf_worker_url, direct_url,
                            extra_headers={"Referer": self.REFERER, "Origin": self.ORIGIN},
                        )
                        try:
                            cf_resp = await client.get(wrapped)
                            cf_ct = cf_resp.headers.get("content-type", "").lower()
                            if cf_resp.status_code < 400 and "json" in cf_ct:
                                raw = cf_resp.json()
                                self._check_graphql_errors(raw)
                                self._working_mirror_idx = idx
                                return raw
                        except (httpx.HTTPError, json.JSONDecodeError):
                            pass
                    last_error = CaptchaRequiredError(
                        f"AllAnime mirror {idx} ({api_url}) returned "
                        f"HTTP {resp.status_code}",
                    )
                    continue

                try:
                    raw = resp.json()
                except (ValueError, json.JSONDecodeError):
                    last_error = ProviderError(
                        f"Mirror {idx} returned non-JSON: {resp.text[:200]}",
                    )
                    continue

                try:
                    self._check_graphql_errors(raw)
                except CaptchaRequiredError as e:
                    last_error = e
                    continue

                self._working_mirror_idx = idx
                return raw

        raise last_error or CaptchaRequiredError(
            "All AllAnime API mirrors failed for /api persisted query",
        )

    def _check_graphql_errors(self, raw: dict) -> None:
        """Inspect a parsed GraphQL response for errors, raising the right
        SNI exception type."""
        data = raw.get("data") or {}
        tobeparsed = data.get("tobeparsed")
        if tobeparsed:
            decrypted = _decrypt_tobeparsed(tobeparsed)
            if decrypted is not None:
                raw["data"] = decrypted

        errors = raw.get("errors")
        if not errors:
            return
        msgs = [e.get("message", "") for e in errors]
        if msgs and all("Cannot set property" in m for m in msgs):
            # Known-benign upstream noise; safe to ignore.
            return
        joined = ", ".join(msgs).lower()
        if any(marker in joined for marker in CAPTCHA_MARKERS):
            raise CaptchaRequiredError(f"AllAnime API error: {', '.join(msgs)}")
        raise ProviderError(f"AllAnime API error: {', '.join(msgs)}")

    # ------------------------------------------------------------------ #
    # Provider interface
    # ------------------------------------------------------------------ #

    async def search(self, query: str) -> List[AnimeResult]:
        cache_key = f"allanime:search:{query.lower()}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        # XAN-style compact GraphQL query — same fields, less whitespace,
        # which helps avoid Cloudflare's "looks like a bot" heuristics.
        gql = (
            "query($s:SearchInput,$limit:Int){"
            "shows(search:$s,limit:$limit){"
            "edges{_id name availableEpisodes thumbnail}}}"
        )
        variables = {"s": {"query": query}, "limit": 40}
        data = await self._post_graphql(gql, variables)
        results = []
        for edge in (data.get("data") or {}).get("shows", {}).get("edges", []):
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

        gql = "query($id:String!){show(_id:$id){_id name availableEpisodesDetail}}"
        variables = {"id": anime_id}
        data = await self._post_graphql(gql, variables)
        detail = (data.get("data") or {}).get("show", {}).get("availableEpisodesDetail", {})
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
            "episodeString": ep_num,
            "translationType": mode,
        }
        data = await self._get_persisted(variables)
        episode_data = (data.get("data") or {}).get("episode")
        if not episode_data:
            if dub:
                raise ProviderError("Dub not available for this episode.")
            raise ProviderError("Episode not available.")

        sources = episode_data.get("sourceUrls", [])
        if not sources:
            raise ProviderError("No stream sources found.")

        # XAN-style priority: Yt-mp4 > Default/Sak/Wixmp/Luf-mp4/S-mp4 family >
        # Mp4 > Fm-Hls/Vn-Hls > Viz/MyCloud > everything else
        def priority(src: dict) -> int:
            n = (src.get("sourceName") or "").lower()
            declared = src.get("priority", 0) or 0
            if "yt-mp4" in n:
                return 1000 + declared
            if any(
                k in n
                for k in (
                    "default", "sak", "wixmp", "luf-mp4", "s-mp4",
                    "sl-mp4", "ss-hls", "s1-mp4", "s2-mp4", "s3-mp4",
                )
            ):
                return 500 + declared
            if n == "mp4":
                return 300 + declared
            if "fm-hls" in n or "vn-hls" in n:
                return 200 + declared
            if "viz" in n or "mycloud" in n:
                return 150 + declared
            return declared

        sorted_sources = sorted(sources, key=priority, reverse=True)

        # Try each source; return the first one that yields a playable Stream.
        # XAN runs these in parallel batches of 4, but for a CLI one good
        # stream is enough — sequential is simpler and avoids hammering.
        for src in sorted_sources:
            raw_url = src.get("sourceUrl", "")
            src_name = src.get("sourceName", "")
            try:
                stream = await self._extract_source(raw_url, src_name, quality)
            except Exception:
                # Don't let one broken source kill the whole episode.
                stream = None
            if stream:
                cache.set(cache_key, [stream], ttl=600)
                return [stream]

        raise ProviderError("No stream sources available.")

    # ------------------------------------------------------------------ #
    # Source extraction (XAN port)
    # ------------------------------------------------------------------ #

    async def _extract_source(
        self, raw_url: str, source_name: str, quality: str
    ) -> Optional[Stream]:
        """Extract a playable Stream from a (possibly-encoded) sourceUrl.

        Mirrors XAN's extractSource() dispatch logic.
        """
        url = decode_url(raw_url)
        name = (source_name or "").lower()

        # Yt-mp4 — direct MP4, may need Authorization / Referer headers
        if "yt-mp4" in name:
            if not url.startswith("http"):
                return None
            stream = Stream(url=url, quality=quality)
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            if "Authorization" in qs:
                stream.headers["Authorization"] = qs["Authorization"][0]
            stream.headers["Referer"] = self.REFERER
            stream.headers["Origin"] = self.ORIGIN
            return stream

        # clock.json family — S-mp4, Luf-mp4, Default, Sak, Wixmp, etc.
        if (
            any(k in name for k in (
                "default", "sak", "wixmp", "luf-mp4", "s-mp4",
                "sl-mp4", "ss-hls", "s1-mp4", "s2-mp4", "s3-mp4",
            ))
            or url.startswith("/apivtwo/")
        ):
            return await self._fetch_clock_json(url, quality)

        # mp4upload — scrape the embed page for direct .mp4 URLs
        if name == "mp4" or "mp4upload.com" in url.lower():
            return await self._scrape_embed(url, source_name, quality)

        # filemoon / vidnest / bysekoze — scrape for .m3u8 / .mp4
        if (
            "fm-hls" in name or "vn-hls" in name
            or "filemoon" in url.lower() or "vidnest" in url.lower()
            or "bysekoze" in url.lower()
        ):
            return await self._scrape_embed(url, source_name, quality)

        # vizcloud / mycloud — try the existing extractors first
        if "viz" in name or "mycloud" in name:
            if "vixcloud" in url.lower():
                try:
                    streams = await VixcloudExtractor.extract(url, quality)
                    if streams:
                        return streams[0]
                except StreamError:
                    pass
            # fall through to scraper as a backup
            return await self._scrape_embed(url, source_name, quality)

        # megacloud — use the existing extractor
        if "megacloud" in url.lower():
            try:
                streams = await MegacloudExtractor.extract(url, quality)
                if streams:
                    return streams[0]
            except StreamError:
                pass
            return None

        # Ok.ru / StreamWish / Uni — iframe-style, no special headers needed
        if ("ok" in name and "ok.ru" in url.lower()) or "streamwish.to" in url.lower():
            return Stream(url=url, quality=quality)

        # Generic fallback — assume direct playable URL
        if url.startswith("http"):
            stream = Stream(url=url, quality=quality)
            stream.headers["Referer"] = self.REFERER
            stream.headers["Origin"] = self.ORIGIN
            return stream

        return None

    async def _fetch_clock_json(
        self, path: str, quality: str
    ) -> Optional[Stream]:
        """Fetch ``/apivtwo/clock.json`` for clock-family sources.

        AllAnime's clock.json endpoint returns a list of direct stream URLs
        (HLS or MP4) with resolution labels. We pick the highest-priority one.
        """
        full_path = path.replace("/clock", "/clock.json")
        # Use the working mirror's base URL (or primary if none worked yet)
        if self._working_mirror_idx is not None:
            _g, _a, base_url = self._mirror(self._working_mirror_idx)
        else:
            base_url = self.ALLANIME_BASE
        full_url = (
            full_path if full_path.startswith("http")
            else f"{base_url}{full_path}"
        )

        async with httpx.AsyncClient(
            headers={
                "User-Agent": USER_AGENT,
                "Referer": self.REFERER,
                "Accept": "application/json, */*",
            },
            follow_redirects=True,
            timeout=CLOCK_TIMEOUT,
        ) as client:
            try:
                resp = await client.get(full_url)
            except httpx.HTTPError:
                # CF Worker fallback (if configured)
                if self.cf_worker_url:
                    wrapped = _build_cf_worker_url(
                        self.cf_worker_url, full_url,
                        extra_headers={"Referer": self.REFERER},
                    )
                    try:
                        resp = await client.get(wrapped)
                    except httpx.HTTPError:
                        return None
                else:
                    return None

            if resp.status_code >= 400:
                if self.cf_worker_url:
                    wrapped = _build_cf_worker_url(
                        self.cf_worker_url, full_url,
                        extra_headers={"Referer": self.REFERER},
                    )
                    try:
                        resp = await client.get(wrapped)
                    except httpx.HTTPError:
                        return None
                else:
                    return None

            try:
                obj = resp.json()
            except json.JSONDecodeError:
                return None

        links = obj.get("links") or obj.get("sources") or []
        if not isinstance(links, list) or not links:
            return None

        # Pick the link whose resolutionStr best matches the requested quality.
        # If no exact match, pick the first link (highest priority by AllAnime's ordering).
        best: Optional[dict] = None
        best_score = -1
        for link in links:
            if not isinstance(link, dict):
                continue
            link_url = (
                link.get("link") or link.get("src") or link.get("url")
            )
            if not link_url:
                continue
            res = (
                link.get("resolutionStr")
                or link.get("quality")
                or link.get("label")
                or ""
            )
            # Higher = better. Exact match to requested quality wins; otherwise
            # prefer numeric resolution values.
            score = 0
            try:
                score = int(re.search(r"\d+", res).group()) if re.search(r"\d+", res) else 0
            except (AttributeError, ValueError):
                score = 0
            if res and quality and quality in res:
                score += 10000  # exact match wins
            if score > best_score:
                best_score = score
                best = link

        if not best:
            return None

        link_url = best.get("link") or best.get("src") or best.get("url")
        if not link_url:
            return None

        res = (
            best.get("resolutionStr")
            or best.get("quality")
            or best.get("label")
            or quality
        )
        stream = Stream(url=link_url, quality=str(res))
        stream.headers["Referer"] = self.REFERER
        stream.headers["Origin"] = self.ORIGIN
        return stream

    async def _scrape_embed(
        self, embed_url: str, source_name: str, quality: str
    ) -> Optional[Stream]:
        """Scrape an embed page for direct .m3u8 / .mp4 URLs.

        Used for mp4upload, filemoon, vidnest, vizcloud, mycloud — XAN does
        the same. Returns the first playable URL found (HLS preferred).
        """
        if not embed_url.startswith("http"):
            return None

        async with httpx.AsyncClient(
            headers={
                "User-Agent": USER_AGENT,
                "Referer": self.REFERER,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            follow_redirects=True,
            timeout=REQUEST_TIMEOUT,
        ) as client:
            try:
                resp = await client.get(embed_url)
            except httpx.HTTPError:
                return None

            if resp.status_code >= 400:
                return None

            html = resp.text

        # Unescape backslash-encoded URLs (common in JS embeds)
        def clean(u: str) -> str:
            return u.replace("\\/", "/").replace("\\u002F", "/").replace("&amp;", "&")

        # Prefer HLS (adaptive) over MP4
        for match in _HLS_RE.finditer(html):
            url = clean(match.group(0))
            if _ASSET_EXT.search(url):
                continue
            stream = Stream(url=url, quality=quality)
            stream.headers["Referer"] = self.REFERER
            stream.headers["Origin"] = self.ORIGIN
            return stream

        for match in _MP4_RE.finditer(html):
            url = clean(match.group(0))
            if _ASSET_EXT.search(url):
                continue
            stream = Stream(url=url, quality=quality)
            stream.headers["Referer"] = self.REFERER
            stream.headers["Origin"] = self.ORIGIN
            return stream

        return None


ProviderRegistry.register(AllAnimeProvider)
