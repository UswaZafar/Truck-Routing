"""One pooled, keep-alive HTTP client shared by all provider clients (httpx.Client is thread-safe)."""

from functools import lru_cache

import httpx
from django.conf import settings

USER_AGENT = "weather-aware-truck-routing/1.0 (hiring assessment demo)"


@lru_cache(maxsize=1)
def get_http_client() -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(settings.HTTP_TIMEOUT_SECONDS, connect=5.0),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )
