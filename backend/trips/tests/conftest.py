import pytest
from django.core.cache import cache

from trips.services import geocoding, routing, weather

from .fakes import FakeProviders


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def providers(monkeypatch, settings):
    """Swap every provider's HTTP client for in-process fakes."""
    settings.OSRM_BASE_URL = "https://osrm.test"
    settings.PHOTON_BASE_URL = "https://photon.test"
    settings.OPEN_METEO_GEOCODE_BASE_URL = "https://geocoding-api.open-meteo.test"
    settings.OPEN_METEO_BASE_URL = "https://api.open-meteo.test"
    settings.OPEN_METEO_API_KEY = ""
    fake = FakeProviders()
    client = fake.client()
    for module in (routing, weather, geocoding):
        monkeypatch.setattr(module, "get_http_client", lambda: client)
    return fake
