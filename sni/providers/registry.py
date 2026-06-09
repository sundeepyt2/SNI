import asyncio
from typing import Dict, List, Optional, Tuple, Type

from sni.exceptions import ProviderNotFoundError
from sni.providers.base import AnimeResult, Provider


class ProviderRegistry:
    _providers: Dict[str, Type[Provider]] = {}

    @classmethod
    def register(cls, provider_cls: Type[Provider]) -> Type[Provider]:
        name = provider_cls.name
        if not name:
            raise ValueError("Provider must have a non-empty name")
        cls._providers[name.lower()] = provider_cls
        return provider_cls

    @classmethod
    def get(cls, name: str) -> Optional[Type[Provider]]:
        return cls._providers.get(name.lower())

    @classmethod
    def list(cls) -> List[str]:
        return list(cls._providers.keys())

    @classmethod
    def get_all(cls) -> Dict[str, Type[Provider]]:
        return dict(cls._providers)

    @classmethod
    async def health_check(cls, name: str) -> Tuple[str, bool]:
        provider_cls = cls.get(name)
        if not provider_cls:
            raise ProviderNotFoundError(f"Unknown provider: {name}")
        try:
            provider = provider_cls()
            ok = await provider.check_health()
            return name, ok
        except Exception:
            return name, False

    @classmethod
    async def health_check_all(cls) -> Dict[str, bool]:
        results = await asyncio.gather(
            *(cls.health_check(name) for name in cls.list()),
            return_exceptions=True,
        )
        status = {}
        for r in results:
            if isinstance(r, tuple):
                status[r[0]] = r[1]
            elif isinstance(r, Exception):
                status["unknown"] = False
        return status

    @classmethod
    def get_fallback_order(cls, preferred: Optional[str] = None) -> List[str]:
        names = cls.list()
        if preferred and preferred in names:
            names.remove(preferred)
            return [preferred] + names
        return names

    @classmethod
    async def search_all(
        cls, query: str, preferred: Optional[str] = None
    ) -> Dict[str, List[AnimeResult]]:
        order = cls.get_fallback_order(preferred)
        results: Dict[str, List[AnimeResult]] = {}
        for name in order:
            provider_cls = cls.get(name)
            if not provider_cls:
                continue
            try:
                provider = provider_cls()
                hits = await provider.search(query)
                results[name] = hits
            except Exception:
                results[name] = []
        return results
