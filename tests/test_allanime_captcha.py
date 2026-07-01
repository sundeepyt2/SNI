"""Unit tests for AllAnime captcha detection + XAN-port helpers.

These tests mock httpx.AsyncClient so we can verify the provider correctly
classifies GraphQL errors / non-JSON responses as CaptchaRequiredError, and
that decode_url / clock.json parsing match the XAN TypeScript behavior.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sni.exceptions import CaptchaRequiredError, ProviderError
from sni.providers.allanime import (
    AllAnimeProvider,
    decode_url,
    _build_cf_worker_url,
)
from sni.providers.cache import cache as provider_cache


@pytest.fixture(autouse=True)
def _clear_provider_cache():
    """Clear the module-level TTL cache before each test so cached results
    from a previous test (e.g. an empty list for 'naruto') don't short-circuit
    the test we're about to run."""
    provider_cache.clear()
    yield
    provider_cache.clear()


def _make_response(status_code=200, json_body=None, text="", content_type="application/json", headers=None):
    """Build a fake httpx.Response-like object."""
    resp = MagicMock()
    resp.status_code = status_code
    base_headers = {"content-type": content_type}
    if headers:
        base_headers.update(headers)
    resp.headers = base_headers
    resp.text = text
    if json_body is not None:
        resp.json = MagicMock(return_value=json_body)
    return resp


# --------------------------------------------------------------------------
# decode_url (XAN decodeUrl port)
# --------------------------------------------------------------------------

def test_decode_url_passthrough_for_plain_url():
    assert decode_url("https://example.com/stream.mp4") == "https://example.com/stream.mp4"


def test_decode_url_xor_form():
    # "--" + hex, XOR each byte with 56
    # 'A' (0x41) XOR 0x38 (56) = 0x79 = 'y'  -> hex is "41"
    # 'B' (0x42) XOR 0x38     = 0x7a = 'z'  -> hex is "42"
    assert decode_url("--4142") == "yz"


def test_decode_url_ap_form():
    # "ap/" + hex, plain hex decode
    # "hi" = 0x68 0x69 -> hex "6869"
    assert decode_url("ap/6869") == "hi"


def test_decode_url_empty():
    assert decode_url("") == ""


def test_decode_url_bad_hex_returns_original():
    # Invalid hex should return the original string, not raise
    assert decode_url("--zz") == "--zz"
    assert decode_url("ap/zz") == "ap/zz"


# --------------------------------------------------------------------------
# CF Worker URL builder
# --------------------------------------------------------------------------

def test_build_cf_worker_url_basic():
    out = _build_cf_worker_url("https://x.example.workers.dev", "https://api.allanime.day/api?x=1")
    assert "url=https%3A%2F%2Fapi.allanime.day%2Fapi%3Fx%3D1" in out
    assert out.startswith("https://x.example.workers.dev/?")


def test_build_cf_worker_url_with_headers():
    out = _build_cf_worker_url(
        "https://x.example.workers.dev",
        "https://api.allanime.day/api",
        extra_headers={"Referer": "https://youtu-chan.com", "Origin": "https://youtu-chan.com"},
    )
    assert "h_Referer=https%3A%2F%2Fyoutu-chan.com" in out
    assert "h_Origin=https%3A%2F%2Fyoutu-chan.com" in out


# --------------------------------------------------------------------------
# Captcha detection in the new split-endpoint code paths
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_graphql_raises_captcha_on_html_response():
    """If /api/graphql returns a Cloudflare HTML wall, the provider must
    raise CaptchaRequiredError instead of crashing on .json()."""
    prov = AllAnimeProvider(cookies="", cf_worker_url="")
    fake_resp = _make_response(
        status_code=403,
        text="<html><title>Just a moment...</title></html>",
        content_type="text/html",
    )

    with patch("sni.providers.allanime.httpx.AsyncClient") as mock_client_cls:
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client.post = AsyncMock(return_value=fake_resp)
        mock_client_cls.return_value = client

        with pytest.raises(CaptchaRequiredError):
            await prov.search("naruto")


@pytest.mark.asyncio
async def test_post_graphql_raises_captcha_on_need_captcha_error():
    """A GraphQL response with a NEED_CAPTCHA error must raise
    CaptchaRequiredError."""
    prov = AllAnimeProvider(cookies="", cf_worker_url="")
    fake_resp = _make_response(
        json_body={"errors": [{"message": "NEED_CAPTCHA"}], "data": None}
    )

    with patch("sni.providers.allanime.httpx.AsyncClient") as mock_client_cls:
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client.post = AsyncMock(return_value=fake_resp)
        mock_client_cls.return_value = client

        with pytest.raises(CaptchaRequiredError) as exc_info:
            await prov.search("naruto")
        assert "NEED_CAPTCHA" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_persisted_raises_captcha_on_html_response():
    """If /api returns a Cloudflare wall on the GET persisted query, the
    provider must raise CaptchaRequiredError."""
    prov = AllAnimeProvider(cookies="", cf_worker_url="")
    fake_resp = _make_response(
        status_code=503,
        text="<html>cf-mitigated challenge</html>",
        content_type="text/html",
    )

    with patch("sni.providers.allanime.httpx.AsyncClient") as mock_client_cls:
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client.get = AsyncMock(return_value=fake_resp)
        mock_client_cls.return_value = client

        with pytest.raises(CaptchaRequiredError):
            await prov.get_streams("showId:1", quality="1080", dub=False)


@pytest.mark.asyncio
async def test_get_persisted_falls_back_to_cf_worker_on_captcha():
    """When the direct /api GET returns a captcha wall AND a CF Worker URL is
    configured, the provider should retry through the Worker and succeed."""
    prov = AllAnimeProvider(cookies="", cf_worker_url="https://xan-proxy.example.workers.dev")

    # Direct response = captcha wall
    direct_resp = _make_response(
        status_code=403,
        text="<html>Just a moment...</html>",
        content_type="text/html",
    )
    # CF Worker response = valid JSON with episode data
    cf_resp = _make_response(
        json_body={
            "data": {
                "episode": {
                    "sourceUrls": [
                        {
                            "sourceName": "Yt-mp4",
                            "sourceUrl": "https://tools.fast4speed.rsvp/media/x/sub/1",
                            "priority": 1,
                            "type": "mp4",
                        }
                    ]
                }
            }
        }
    )

    with patch("sni.providers.allanime.httpx.AsyncClient") as mock_client_cls:
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        # First call to .get() returns direct_resp (captcha), second returns cf_resp
        client.get = AsyncMock(side_effect=[direct_resp, cf_resp])
        mock_client_cls.return_value = client

        streams = await prov.get_streams("showId:1", quality="1080", dub=False)
        assert len(streams) == 1
        assert "tools.fast4speed.rsvp" in streams[0].url


@pytest.mark.asyncio
async def test_benign_cannot_set_property_error_is_swallowed():
    """The known-benign 'Cannot set property' GraphQL error should be ignored."""
    prov = AllAnimeProvider(cookies="", cf_worker_url="")
    fake_resp = _make_response(
        json_body={
            "errors": [{"message": "Cannot set property X of undefined"}],
            "data": {"shows": {"edges": []}},
        }
    )

    with patch("sni.providers.allanime.httpx.AsyncClient") as mock_client_cls:
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client.post = AsyncMock(return_value=fake_resp)
        mock_client_cls.return_value = client

        # Should NOT raise — benign error swallowed, empty result returned.
        results = await prov.search("naruto")
        assert results == []


@pytest.mark.asyncio
async def test_other_graphql_error_raises_provider_error():
    """Other (non-captcha, non-benign) GraphQL errors should raise generic
    ProviderError, NOT CaptchaRequiredError."""
    prov = AllAnimeProvider(cookies="", cf_worker_url="")
    fake_resp = _make_response(
        json_body={"errors": [{"message": "Something else broke"}], "data": None}
    )

    with patch("sni.providers.allanime.httpx.AsyncClient") as mock_client_cls:
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client.post = AsyncMock(return_value=fake_resp)
        mock_client_cls.return_value = client

        with pytest.raises(ProviderError) as exc_info:
            await prov.search("naruto")
        assert not isinstance(exc_info.value, CaptchaRequiredError)


# --------------------------------------------------------------------------
# Clock.json parsing
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clock_json_picks_highest_matching_resolution():
    """The clock.json extractor should prefer links whose resolutionStr
    contains the requested quality."""
    prov = AllAnimeProvider(cookies="", cf_worker_url="")

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.headers = {"content-type": "application/json"}
    fake_resp.json = MagicMock(return_value={
        "links": [
            {"link": "https://cdn.example.com/360.m3u8", "resolutionStr": "360p"},
            {"link": "https://cdn.example.com/1080.m3u8", "resolutionStr": "1080p"},
            {"link": "https://cdn.example.com/720.m3u8", "resolutionStr": "720p"},
        ]
    })

    with patch("sni.providers.allanime.httpx.AsyncClient") as mock_client_cls:
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client.get = AsyncMock(return_value=fake_resp)
        mock_client_cls.return_value = client

        stream = await prov._fetch_clock_json("/apivtwo/clock", quality="1080")
        assert stream is not None
        assert "1080" in stream.url
        assert "1080" in stream.quality


@pytest.mark.asyncio
async def test_clock_json_returns_none_on_404():
    """A 404 from clock.json (with no CF Worker) should return None."""
    prov = AllAnimeProvider(cookies="", cf_worker_url="")
    fake_resp = _make_response(status_code=404, text="not found", content_type="text/plain")

    with patch("sni.providers.allanime.httpx.AsyncClient") as mock_client_cls:
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client.get = AsyncMock(return_value=fake_resp)
        mock_client_cls.return_value = client

        stream = await prov._fetch_clock_json("/apivtwo/clock", quality="1080")
        assert stream is None
