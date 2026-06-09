import json
from datetime import datetime
from pathlib import Path
from typing import Optional

HISTORY_PATH = Path.home() / ".config" / "sni" / "history.json"


class WatchHistory:
    def __init__(self, path: Path = HISTORY_PATH):
        self.path = path
        self._data: dict = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {"entries": [], "continue": {}}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2))

    def add_entry(
        self, anime_title: str, anime_id: str, provider: str,
        episode_num: int, episode_id: str,
    ):
        key = f"{provider}:{anime_id}"
        entry = {
            "anime_title": anime_title,
            "anime_id": anime_id,
            "provider": provider,
            "episode_num": episode_num,
            "episode_id": episode_id,
            "watched_at": datetime.now().isoformat(),
        }
        self._data["entries"].append(entry)
        self._data["continue"][key] = {
            "anime_title": anime_title,
            "anime_id": anime_id,
            "provider": provider,
            "last_episode": episode_num,
            "last_episode_id": episode_id,
            "watched_at": datetime.now().isoformat(),
        }
        self._save()

    def get_continue(self) -> list[dict]:
        entries = list(self._data["continue"].values())
        entries.sort(key=lambda e: e.get("watched_at", ""), reverse=True)
        return entries

    def remove_continue(self, anime_id: str, provider: str):
        key = f"{provider}:{anime_id}"
        self._data["continue"].pop(key, None)
        self._save()

    def get_continue_entry(self, anime_id: str, provider: str) -> Optional[dict]:
        key = f"{provider}:{anime_id}"
        return self._data["continue"].get(key)
