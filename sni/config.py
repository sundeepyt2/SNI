"""SNI configuration — simple TOML config."""

import os
import platform
from pathlib import Path
from typing import Optional

try:
    import tomllib as tomli
except ModuleNotFoundError:
    import tomli
import tomli_w
from pydantic import BaseModel

if platform.system() == "Windows":
    DEFAULT_CONFIG_PATH = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "sni" / "config.toml"
else:
    DEFAULT_CONFIG_PATH = Path.home() / ".config" / "sni" / "config.toml"


class Config(BaseModel):
    # Player
    player: str = "mpv"
    quality: str = "1080"
    use_ipc: bool = True

    # AllAnime (optional captcha bypass)
    allanime_cf_worker_url: str = ""

    # UI
    selector: str = "fzf"
    icons: bool = True

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        path = path or DEFAULT_CONFIG_PATH
        if not path.exists():
            return cls()
        try:
            with open(path, "rb") as f:
                data = tomli.load(f)
            flat = {}
            for section in data.values():
                if isinstance(section, dict):
                    flat.update(section)
            return cls(**flat)
        except Exception:
            return cls()

    def save(self, path: Optional[Path] = None) -> None:
        path = path or DEFAULT_CONFIG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        # Keys MUST match the model field names so Config.load() roundtrips
        # correctly. The load() method flattens all sections into kwargs.
        data = {
            "player": {
                "player": self.player,
                "quality": self.quality,
                "use_ipc": self.use_ipc,
            },
            "allanime": {
                "allanime_cf_worker_url": self.allanime_cf_worker_url,
            },
            "ui": {
                "selector": self.selector,
                "icons": self.icons,
            },
        }
        with open(path, "wb") as f:
            tomli_w.dump(data, f)

    def get_cf_worker_url(self) -> str:
        return (self.allanime_cf_worker_url or "").rstrip("/")
