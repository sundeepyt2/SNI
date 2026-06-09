import time
from typing import Any, Dict, Optional


class TTLCache:
    def __init__(self, ttl: int = 300):
        self._ttl = ttl
        self._data: Dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        if key not in self._data:
            return None
        expires, value = self._data[key]
        if time.time() > expires:
            del self._data[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self._data[key] = (time.time() + (ttl or self._ttl), value)

    def delete(self, key: str) -> None:
        self._data.pop(key, None)

    def clear(self) -> None:
        self._data.clear()


cache = TTLCache(ttl=300)
