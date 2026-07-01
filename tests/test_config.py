import tempfile
from pathlib import Path

from sni.config import Config


def test_config_defaults():
    cfg = Config()
    assert cfg.default_provider == "allanime"
    assert cfg.quality == "1080"
    assert cfg.player == "mpv"
    assert cfg.selector == "fzf"


def test_config_load_save():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.toml"
        cfg = Config(default_provider="animepahe", quality="720")
        cfg.save(path)
        assert path.exists()

        loaded = Config.load(path)
        assert loaded.default_provider == "animepahe"
        assert loaded.quality == "720"


def test_config_load_nonexistent():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "nope.toml"
        cfg = Config.load(path)
    assert cfg.default_provider == "allanime"


def test_config_roundtrip_all_fields():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.toml"
        cfg = Config(
            default_provider="allanime",
            selector="builtin",
            preview="minimal",
            icons=False,
            player="vlc",
            quality="480",
            translation_type="dub",
            auto_next=False,
            use_ipc=False,
        )
        cfg.save(path)
        loaded = Config.load(path)
        assert loaded.default_provider == "allanime"
        assert loaded.selector == "builtin"
        assert loaded.icons is False
        assert loaded.player == "vlc"
        assert loaded.quality == "480"
        assert loaded.translation_type == "dub"
        assert loaded.auto_next is False
        assert loaded.use_ipc is False


def test_allanime_cookies_roundtrip():
    """allanime_cookies must survive save/load."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.toml"
        cfg = Config(allanime_cookies="k1=v1; k2=v2")
        cfg.save(path)
        loaded = Config.load(path)
        assert loaded.allanime_cookies == "k1=v1; k2=v2"
        assert loaded.get_allanime_cookies() == "k1=v1; k2=v2"


def test_get_allanime_cookies_falls_back_to_file(tmp_path, monkeypatch):
    """If the cookies file exists and is non-empty, it takes precedence over
    the config field."""
    from sni.config import DEFAULT_COOKIES_PATH
    cookies_file = tmp_path / "allanime_cookies.txt"
    cookies_file.write_text("from_file=abc", encoding="utf-8")
    monkeypatch.setattr("sni.config.DEFAULT_COOKIES_PATH", cookies_file)

    cfg = Config(allanime_cookies="from_config=xyz")
    assert cfg.get_allanime_cookies() == "from_file=abc"


def test_get_allanime_cookies_ignores_empty_file(tmp_path, monkeypatch):
    """An empty cookies file must not shadow a non-empty config value."""
    cookies_file = tmp_path / "allanime_cookies.txt"
    cookies_file.write_text("   \n", encoding="utf-8")
    monkeypatch.setattr("sni.config.DEFAULT_COOKIES_PATH", cookies_file)

    cfg = Config(allanime_cookies="from_config=xyz")
    assert cfg.get_allanime_cookies() == "from_config=xyz"


def test_allanime_cf_worker_url_roundtrip():
    """allanime_cf_worker_url must survive save/load."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.toml"
        cfg = Config(allanime_cf_worker_url="https://xan-proxy.example.workers.dev/")
        cfg.save(path)
        loaded = Config.load(path)
        # Getter should strip the trailing slash
        assert loaded.get_allanime_cf_worker_url() == "https://xan-proxy.example.workers.dev"


def test_allanime_cf_worker_url_empty_by_default():
    cfg = Config()
    assert cfg.get_allanime_cf_worker_url() == ""
