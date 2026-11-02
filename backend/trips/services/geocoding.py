"""Place search: Photon first, then Open-Meteo geocoding if Photon is unreachable.

Photon (photon.komoot.io) is a free demo server that often blocks or times out from cloud
host IPs (e.g. Render). Open-Meteo's geocoding API is keyless and more reliable from those
networks, so we fall back to it instead of returning a hard 502.
"""

from __future__ import annotations

import hashlib
import logging

import httpx
from django.conf import settings
from django.core.cache import cache

from ..exceptions import UpstreamError
from .http import get_http_client

GEOCODE_CACHE_SECONDS = 24 * 60 * 60
MAX_RESULTS = 5

logger = logging.getLogger(__name__)


def _label(props: dict) -> str:
    name = props.get("name") or " ".join(filter(None, [props.get("housenumber"), props.get("street")]))
    parts = [name, props.get("city"), props.get("state"), props.get("country")]
    seen: list[str] = []
    for part in parts:
        if part and part not in seen:
            seen.append(part)
    return ", ".join(seen)


def _open_meteo_label(row: dict) -> str:
    parts = [row.get("name"), row.get("admin1"), row.get("country")]
    seen: list[str] = []
    for part in parts:
        if part and part not in seen:
            seen.append(part)
    return ", ".join(seen)


class GeocodingClient:
    def __init__(
        self,
        http: httpx.Client | None = None,
        base_url: str | None = None,
        fallback_url: str | None = None,
    ):
        self.http = http or get_http_client()
        self.base_url = (base_url or settings.PHOTON_BASE_URL).rstrip("/")
        self.fallback_url = (fallback_url or settings.OPEN_METEO_GEOCODE_BASE_URL).rstrip("/")

    def search(self, query: str, limit: int = MAX_RESULTS) -> list[dict]:
        query = " ".join(query.split())
        key = f"geocode:{limit}:" + hashlib.sha1(query.lower().encode()).hexdigest()
        cached = cache.get(key)
        if cached is not None:
            return cached

        results, photon_error = self._search_photon(query, limit)
        if results is None:
            logger.warning("Photon geocode failed (%s); trying Open-Meteo", photon_error)
            results = self._search_open_meteo(query, limit)

        cache.set(key, results, GEOCODE_CACHE_SECONDS)
        return results

    def resolve(self, query: str) -> dict | None:
        """Best match for free text, or None when nothing matches."""
        results = self.search(query, limit=1)
        return results[0] if results else None

    def _search_photon(self, query: str, limit: int) -> tuple[list[dict] | None, str | None]:
        """Return (results, None) on success, (None, reason) when this provider should be skipped."""
        try:
            response = self.http.get(
                f"{self.base_url}/api", params={"q": query, "limit": limit, "lang": "en"}
            )
        except httpx.HTTPError as exc:
            return None, str(exc) or exc.__class__.__name__
        if response.status_code == 429:
            raise UpstreamError("Geocoding rate limit reached. Please retry shortly.", status_code=503)
        if response.status_code != 200:
            return None, f"HTTP {response.status_code}"

        results = []
        for feature in response.json().get("features", []):
            lng, lat = feature["geometry"]["coordinates"][:2]
            label = _label(feature.get("properties", {}))
            if label and all(r["label"] != label for r in results):
                results.append({"label": label, "lat": round(lat, 6), "lng": round(lng, 6)})
        return results, None

    def _search_open_meteo(self, query: str, limit: int) -> list[dict]:
        try:
            response = self.http.get(
                f"{self.fallback_url}/v1/search",
                params={"name": query, "count": limit, "language": "en", "format": "json"},
            )
        except httpx.HTTPError as exc:
            raise UpstreamError("Geocoding service is unreachable.") from exc
        if response.status_code == 429:
            raise UpstreamError("Geocoding rate limit reached. Please retry shortly.", status_code=503)
        if response.status_code != 200:
            raise UpstreamError(f"Geocoding service error ({response.status_code}).")

        results = []
        for row in response.json().get("results") or []:
            label = _open_meteo_label(row)
            lat, lng = row.get("latitude"), row.get("longitude")
            if label and lat is not None and lng is not None and all(r["label"] != label for r in results):
                results.append({"label": label, "lat": round(float(lat), 6), "lng": round(float(lng), 6)})
        return results
