from sni.exceptions import (
    CaptchaRequiredError,
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


def test_captcha_required_is_provider_error():
    """CaptchaRequiredError must be catchable as ProviderError so the
    existing exception handlers in cli.py still cover it."""
    assert issubclass(CaptchaRequiredError, ProviderError)


def test_captcha_required_has_actionable_hint():
    """The error must carry a non-empty hint that mentions cookies."""
    err = CaptchaRequiredError("NEED_CAPTCHA")
    assert "cookie" in err.hint.lower()
    # The str() form should also surface the hint so logs are useful.
    assert "cookie" in str(err).lower()
