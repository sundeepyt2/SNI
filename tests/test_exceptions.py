from sni.exceptions import (
    ConfigError,
    ProviderError,
    ProviderHealthError,
    ProviderNotFoundError,
    SNIError,
    StreamError,
)


def test_sni_error():
    e = SNIError("test")
    assert str(e) == "test"


def test_provider_error_subclass():
    assert issubclass(ProviderError, SNIError)


def test_provider_not_found():
    assert issubclass(ProviderNotFoundError, ProviderError)


def test_provider_health_error():
    assert issubclass(ProviderHealthError, ProviderError)


def test_config_error_subclass():
    assert issubclass(ConfigError, SNIError)


def test_stream_error_subclass():
    assert issubclass(StreamError, SNIError)
