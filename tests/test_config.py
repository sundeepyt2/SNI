import tempfile
from pathlib import Path

from sni.config import Config


def test_config_defaults():
    cfg = Config()
    assert cfg.default_provider == "hianime"
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
        assert cfg.default_provider == "hianime"


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
