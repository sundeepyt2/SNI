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
    DEFAULT_COOKIES_PATH = appdata / "sni" / "allanime_cookies.txt"
else:
    DEFAULT_CONFIG_PATH = Path.home() / ".config" / "sni" / "config.toml"
    DEFAULT_COOKIES_PATH = Path.home() / ".config" / "sni" / "allanime_cookies.txt"


class Config(BaseModel):
    default_provider: str = "allanime"
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

    # Provider-specific credentials. ``allanime_cookies`` is loaded from this
    # field OR from DEFAULT_COOKIES_PATH (file takes precedence when non-empty).
    allanime_cookies: str = ""

    # Optional Cloudflare Worker URL used as a fallback when the AllAnime API
    # blocks the user's IP (NEED_CAPTCHA / Cloudflare wall). Users deploy the
    # worker from the XAN repo (cf-worker/worker.js) and paste the URL here.
    # Example: "https://my-xan-proxy.some-user.workers.dev"
    allanime_cf_worker_url: str = ""

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
            "providers": {
                "allanime_cookies": self.allanime_cookies,
                "allanime_cf_worker_url": self.allanime_cf_worker_url,
            },
        }
        try:
            with open(path, "wb") as f:
                tomli_w.dump(data, f)
        except Exception as e:
            raise ConfigError(f"Failed to save config to {path}: {e}")

    def get_allanime_cookies(self) -> str:
        """Resolve AllAnime cookies, preferring the cookies file over config.

        Order of precedence:
          1. ``~/.config/sni/allanime_cookies.txt`` (if non-empty) — easier to
             update without re-quoting a TOML string.
          2. ``Config.allanime_cookies`` field (set via wizard or ``--update``).
        """
        try:
            if DEFAULT_COOKIES_PATH.exists():
                file_cookies = DEFAULT_COOKIES_PATH.read_text(encoding="utf-8").strip()
                if file_cookies:
                    return file_cookies
        except OSError:
            pass
        return self.allanime_cookies or ""

    def get_allanime_cf_worker_url(self) -> str:
        """Return the Cloudflare Worker URL (stripped of trailing slash) or ''.

        Optional — only used when AllAnime's API blocks the user's IP with a
        Cloudflare wall / NEED_CAPTCHA. The Worker proxies the request using
        Cloudflare's own IPs, which AllAnime's edge usually doesn't challenge.
        """
        url = (self.allanime_cf_worker_url or "").strip()
        return url.rstrip("/")
