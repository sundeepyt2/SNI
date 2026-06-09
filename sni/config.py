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

from sni.exceptions import ConfigError

if platform.system() == "Windows":
    appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    DEFAULT_CONFIG_PATH = appdata / "sni" / "config.toml"
else:
    DEFAULT_CONFIG_PATH = Path.home() / ".config" / "sni" / "config.toml"


class Config(BaseModel):
    default_provider: str = "hianime"
    selector: str = "fzf"
    preview: str = "full"
    icons: bool = True

    player: str = "mpv"
    quality: str = "1080"
    translation_type: str = "sub"
    auto_next: bool = True
    use_ipc: bool = True

    show_description: bool = True
    show_score: bool = True
    show_genres: bool = True

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
        except Exception as e:
            raise ConfigError(f"Failed to load config from {path}: {e}")

    def save(self, path: Optional[Path] = None) -> None:
        path = path or DEFAULT_CONFIG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "general": {
                "default_provider": self.default_provider,
                "selector": self.selector,
                "preview": self.preview,
                "icons": self.icons,
            },
            "stream": {
                "player": self.player,
                "quality": self.quality,
                "translation_type": self.translation_type,
                "auto_next": self.auto_next,
                "use_ipc": self.use_ipc,
            },
            "ui": {
                "show_description": self.show_description,
                "show_score": self.show_score,
                "show_genres": self.show_genres,
            },
        }
        try:
            with open(path, "wb") as f:
                tomli_w.dump(data, f)
        except Exception as e:
            raise ConfigError(f"Failed to save config to {path}: {e}")
