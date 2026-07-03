"""Watch history — track what you've watched and resume from where you left off."""

import json
import os
import time
from pathlib import Path
from typing import Optional


def _history_path() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", Path.home())) / "sni" / "history.json"
    return Path.home() / ".config" / "sni" / "history.json"


class WatchHistory:
    """Simple JSON-based watch history."""

    def __init__(self):
        self.path = _history_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                with open(self.path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {"entries": []}

    def _save(self):
        try:
            with open(self.path, "w") as f:
                json.dump(self._data, f, indent=2)
        except OSError:
            pass

    def add(self, anime_id: int, title: str, episode: int, total: int, dub: bool = False):
        """Record that we watched an episode."""
        entry = {
            "anime_id": anime_id,
            "title": title,
            "episode": episode,
            "total": total,
            "dub": dub,
            "timestamp": time.time(),
        }
        # Remove old entry for same anime+dub
        self._data["entries"] = [
            e for e in self._data["entries"]
            if not (e["anime_id"] == anime_id and e.get("dub") == dub)
        ]
        self._data["entries"].insert(0, entry)
        self._data["entries"] = self._data["entries"][:100]  # keep last 100
        self._save()

    def get_continue(self) -> list[dict]:
        """Get anime to continue watching (sorted by most recent)."""
        return self._data["entries"]

    def get_last_episode(self, anime_id: int, dub: bool = False) -> Optional[int]:
        """Get the last watched episode for an anime."""
        for e in self._data["entries"]:
            if e["anime_id"] == anime_id and e.get("dub") == dub:
                return e["episode"]
        return None

    def clear(self):
        self._data = {"entries": []}
        self._save()
