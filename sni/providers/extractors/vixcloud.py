import json
import re
from typing import List

import httpx

from sni.exceptions import StreamError
from sni.providers.base import Stream


class VixcloudExtractor:
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

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

            sources_match = re.search(
                r"(?:var\s+)?sources\s*=\s*(\[.*?\]);", html, re.DOTALL
            )
            if not sources_match:
                sources_match = re.search(
                    r'file\s*:\s*["\']([^"\']+)["\']', html
                )
                if sources_match:
                    url = sources_match.group(1)
                    return [Stream(url=url, quality=quality)]
                raise StreamError("Could not find sources in Vixcloud embed")

            sources_data = json.loads(sources_match.group(1))
            streams = []
            for item in sources_data:
                url = item.get("file") or item.get("url", "")
                label = item.get("label") or item.get("quality", quality)
                if not url:
                    continue
                streams.append(Stream(url=url, quality=label))

            if not streams:
                raise StreamError("No streams found in Vixcloud embed")

            streams.sort(
                key=lambda s: int(s.quality.rstrip("p").rstrip("P")),
                reverse=True,
            )
            idx = min(q_idx, len(streams) - 1)
            return [streams[idx]]
