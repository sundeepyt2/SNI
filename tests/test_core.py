"""Basic tests for SNI v2.0."""
from sni.config import Config
from sni.exceptions import SNIError, StreamError, PlayerError
from sni.allanime import decode_url, _decrypt_tobeparsed


def test_config_defaults():
    cfg = Config()
    assert cfg.player == "mpv"
    assert cfg.quality == "1080"


def test_config_save_load(tmp_path):
    path = tmp_path / "config.toml"
    cfg = Config(quality="720")
    cfg.save(path)
    loaded = Config.load(path)
    assert loaded.quality == "720"


def test_decode_url_xor():
    # "--" prefix = hex + XOR 56
    # 'A' (0x41) XOR 0x38 = 0x79 = 'y' -> hex "41"
    assert decode_url("--41") == "y"


def test_decode_url_ap():
    # "ap/" prefix = plain hex decode
    # "hi" = 0x68 0x69 -> hex "6869"
    assert decode_url("ap/6869") == "hi"


def test_decode_url_passthrough():
    assert decode_url("https://example.com/video.mp4") == "https://example.com/video.mp4"


def test_exceptions_hierarchy():
    assert issubclass(StreamError, SNIError)
    assert issubclass(PlayerError, SNIError)
