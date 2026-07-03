"""AniList GraphQL API client — search, metadata, episode counts.

AniList is a public anime database API. It's:
- Free, no auth required
- No captcha, no Cloudflare walls
- 100% reliable
- Gives proper English titles, episode counts, scores, cover images

This replaces the old SNI's AllAnime-based search, which was unreliable.
"""

from dataclasses import dataclass
from typing import List, Optional

import httpx

ANILIST_API = "https://graphql.anilist.co"
TIMEOUT = 15.0


@dataclass
class AnimeResult:
    id: int  # AniList ID
    title: str  # English or Romaji title
    romaji: Optional[str] = None
    episodes: Optional[int] = None  # total episode count
    score: Optional[float] = None
    image: Optional[str] = None
    description: Optional[str] = None


async def search_anime(query: str, limit: int = 20) -> List[AnimeResult]:
    """Search for anime by title. Returns AniList results with full metadata."""
    gql = """
    query ($search: String, $limit: Int) {
      Page(perPage: $limit) {
        media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
          id
          title { romaji english }
          episodes
          averageScore
          coverImage { large }
          description
        }
      }
    }
    """
    variables = {"search": query, "limit": limit}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            ANILIST_API,
            json={"query": gql, "variables": variables},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()

    media_list = data.get("data", {}).get("Page", {}).get("media", [])
    results = []
    for m in media_list:
        titles = m.get("title", {})
        english = titles.get("english")
        romaji = titles.get("romaji")
        results.append(AnimeResult(
            id=m["id"],
            title=english or romaji or "Unknown",
            romaji=romaji,
            episodes=m.get("episodes"),
            score=m.get("averageScore"),
            image=m.get("coverImage", {}).get("large"),
            description=m.get("description", ""),
        ))
    return results


async def get_anime(anilist_id: int) -> Optional[AnimeResult]:
    """Get a single anime by its AniList ID."""
    gql = """
    query ($id: Int) {
      Media(id: $id, type: ANIME) {
        id
        title { romaji english }
        episodes
        averageScore
        coverImage { large }
        description
      }
    }
    """
    variables = {"id": anilist_id}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            ANILIST_API,
            json={"query": gql, "variables": variables},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()

    m = data.get("data", {}).get("Media")
    if not m:
        return None
    titles = m.get("title", {})
    return AnimeResult(
        id=m["id"],
        title=titles.get("english") or titles.get("romaji") or "Unknown",
        romaji=titles.get("romaji"),
        episodes=m.get("episodes"),
        score=m.get("averageScore"),
        image=m.get("coverImage", {}).get("large"),
        description=m.get("description", ""),
    )
