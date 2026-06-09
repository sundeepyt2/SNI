from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AnimeResult:
    id: str
    title: str
    year: Optional[int] = None
    score: Optional[float] = None
    genres: List[str] = field(default_factory=list)
    description: Optional[str] = None
    episodes: Optional[int] = None
    image: Optional[str] = None


@dataclass
class Episode:
    id: str
    number: int
    title: Optional[str] = None
    image: Optional[str] = None


@dataclass
class Stream:
    url: str
    quality: str
    audio_lang: str = "ja"
    sub_lang: Optional[str] = None
    headers: dict[str, str] = field(default_factory=dict)


class Provider(ABC):
    name: str = ""
    domain: str = ""
    supports_sub: bool = True
    supports_dub: bool = False

    @abstractmethod
    async def search(self, query: str) -> List[AnimeResult]:
        ...

    @abstractmethod
    async def get_episodes(self, anime_id: str) -> List[Episode]:
        ...

    @abstractmethod
    async def get_streams(
        self, episode_id: str, quality: str = "1080", dub: bool = False
    ) -> List[Stream]:
        ...

    async def check_health(self) -> bool:
        try:
            results = await self.search("one piece")
            return len(results) > 0
        except Exception:
            return False
