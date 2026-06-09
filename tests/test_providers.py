import pytest

from sni.providers.base import Provider
from sni.providers.registry import ProviderRegistry


class MockProvider(Provider):
    name = "mock"
    domain = "mock.test"
    supports_sub = True
    supports_dub = True

    async def search(self, query):
        return []

    async def get_episodes(self, anime_id):
        return []

    async def get_streams(self, episode_id, quality="1080", dub=False):
        return []


def test_registry_register():
    ProviderRegistry.register(MockProvider)
    cls = ProviderRegistry.get("mock")
    assert cls is MockProvider


def test_registry_get_unknown():
    cls = ProviderRegistry.get("nonexistent")
    assert cls is None


def test_registry_list():
    names = ProviderRegistry.list()
    assert "mock" in names


def test_registry_get_all():
    all_providers = ProviderRegistry.get_all()
    assert "mock" in all_providers


def test_get_fallback_order():
    order = ProviderRegistry.get_fallback_order("mock")
    assert order[0] == "mock"


@pytest.mark.asyncio
async def test_health_check_all():
    result = await ProviderRegistry.health_check_all()
    assert isinstance(result, dict)
