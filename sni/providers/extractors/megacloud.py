import json
import re
from typing import List

import httpx

from sni.exceptions import StreamError
from sni.providers.base import Stream


class MegacloudExtractor:
    API_URL = "https://megacloud.tv"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    @classmethod
    def _decrypt(cls, encrypted: str, key: str) -> str:
        result = []
        for i, ch in enumerate(encrypted):
            k = ord(key[i % len(key)])
            result.append(chr(ord(ch) ^ k))
        return "".join(result)

    @classmethod
    async def extract(
        cls, embed_url: str, quality: str = "1080"
    ) -> List[Stream]:
        quality_map = {"360": 0, "480": 1, "720": 2, "1080": 3}
        q_idx = quality_map.get(quality, 3)

        async with httpx.AsyncClient(
            headers={"User-Agent": cls.USER_AGENT},
            follow_redirects=True,
            timeout=30,
        ) as client:
            resp = await client.get(embed_url)
            resp.raise_for_status()
            html = resp.text

            rc_key = re.search(r"rcKey\s*=\s*['\"]([^'\"]+)['\"]", html)
            if not rc_key:
                raise StreamError("Could not find rcKey in Megacloud embed")
            rc_key = rc_key.group(1)

            sources_match = re.search(
                r"(?:var\s+)?sources\s*=\s*(\[.*?\])\s*;", html, re.DOTALL
            )
            if not sources_match:
                sources_match = re.search(
                    r'sources:\s*(\[.*?\])', html, re.DOTALL
                )
            if not sources_match:
                raise StreamError("Could not find sources in Megacloud embed")
            sources_raw = sources_match.group(1)
            sources_data = json.loads(sources_raw)

            streams = []
            for item in sources_data:
                enc_url = item.get("encUrl", item.get("src", ""))
                if not enc_url:
                    continue
                decrypted = cls._decrypt(enc_url, rc_key)
                if decrypted.startswith("http"):
                    streams.append(Stream(
                        url=decrypted,
                        quality=item.get("quality", item.get("label", quality)),
                    ))

            if not streams:
                raise StreamError("No streams could be decrypted from Megacloud")

            streams.sort(
                key=lambda s: int(s.quality.rstrip("p")),
                reverse=True,
            )
            idx = min(q_idx, len(streams) - 1)
            return [streams[idx]]
