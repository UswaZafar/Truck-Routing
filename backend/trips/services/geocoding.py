"""Place search via Photon (OpenStreetMap data, keyless, built for type-ahead search)."""

from __future__ import annotations

import hashlib

import httpx
from django.conf import settings
from django.core.cache import cache

from ..exceptions import UpstreamError
from .http import get_http_client

GEOCODE_CACHE_SECONDS = 24 * 60 * 60
MAX_RESULTS = 5


def _label(props: dict) -> str:
    name = props.get("name") or " ".join(filter(None, [props.get("housenumber"), props.get("street")]))
    parts = [name, props.get("city"), props.get("state"), props.get("country")]
    seen: list[str] = []
    for part in parts:
        if part and part not in seen:
            seen.append(part)
    return ", ".join(seen)


class GeocodingClient:
    def __init__(self, http: httpx.Client | None = None, base_url: str | None = None):
        self.http = http or get_http_client()
        self.base_url = (base_url or settings.PHOTON_BASE_URL).rstrip("/")

    def search(self, query: str, limit: int = MAX_RESULTS) -> list[dict]:
        query = " ".join(query.split())
        key = f"geocode:{limit}:" + hashlib.sha1(query.lower().encode()).hexdigest()
        cached = cache.get(key)
        if cached is not None:
            return cached
        try:
            response = self.http.get(f"{self.base_url}/api", params={"q": query, "limit": limit, "lang": "en"})
        except httpx.HTTPError as exc:
            raise UpstreamError("Geocoding service is unreachable.") from exc
        if response.status_code == 429:
            raise UpstreamError("Geocoding rate limit reached. Please retry shortly.", status_code=503)
        if response.status_code != 200:
            raise UpstreamError(f"Geocoding service error ({response.status_code}).")

        results = []
        for feature in response.json().get("features", []):
            lng, lat = feature["geometry"]["coordinates"][:2]
            label = _label(feature.get("properties", {}))
            if label and all(r["label"] != label for r in results):
                results.append({"label": label, "lat": round(lat, 6), "lng": round(lng, 6)})
        cache.set(key, results, GEOCODE_CACHE_SECONDS)
        return results

    def resolve(self, query: str) -> dict | None:
        """Best match for free text, or None when nothing matches."""
        results = self.search(query, limit=1)
        return results[0] if results else None
