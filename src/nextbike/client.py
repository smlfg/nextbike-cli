from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

import httpx

from . import __version__
from .errors import CliError, source_error
from .store import cache_dir, read_json, write_json_atomic

DEFAULT_BASE_URL = "https://maps2.nextbike.net/maps"
CITIES_TTL = 24 * 60 * 60
CITY_TTL = 60
TIMEOUT = 15.0
USER_AGENT = (
    f"nextbike-cli/{__version__} "
    "(+https://github.com/smlfg/nextbike-cli)"
)


def base_url() -> str:
    import os
    from urllib.parse import urlsplit

    value = (os.environ.get("NEXTBIKE_BASE_URL") or DEFAULT_BASE_URL).strip()
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise source_error(
            "NEXTBIKE_BASE_URL ist keine gültige http(s)-Basis-URL.",
            "Setze NEXTBIKE_BASE_URL zum Beispiel auf https://maps2.nextbike.net/maps.",
        )
    return value


def parse_cities(payload: object) -> list[dict[str, Any]]:
    """Liest countries[].cities[] aus der Städteliste."""
    if not isinstance(payload, dict):
        raise source_error("Die Städteliste hat ein unerwartetes Format.")
    countries = payload.get("countries")
    if not isinstance(countries, list):
        raise source_error("Die Städteliste enthält keine Länderliste.")
    cities: list[dict[str, Any]] = []
    for country in countries:
        if not isinstance(country, dict):
            continue
        for city in country.get("cities") or []:
            if not isinstance(city, dict):
                continue
            try:
                uid = int(city["uid"])
                name = str(city["name"])
            except (KeyError, TypeError, ValueError):
                continue
            try:
                num_places = int(city.get("num_places") or 0)
            except (TypeError, ValueError):
                num_places = 0
            cities.append(
                {
                    "uid": uid,
                    "name": name,
                    "num_places": num_places,
                    "lat": _optional_float(city.get("lat")),
                    "lng": _optional_float(city.get("lng")),
                }
            )
    if not cities:
        raise source_error("Die Städteliste ist leer.")
    return cities


def parse_city(payload: object) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Liest Stadt und places[] aus einer Stadtantwort."""
    if not isinstance(payload, dict):
        raise source_error("Die Stadtantwort hat ein unerwartetes Format.")
    countries = payload.get("countries")
    if not isinstance(countries, list):
        raise source_error("Die Stadtantwort enthält keine Länderliste.")
    if not countries:
        raise CliError(
            "KEINE_DATEN",
            "Die Quelle liefert für diese Stadt keine Daten.",
            "Prüfe die Stadt mit nextbike staedte.",
            1,
        )
    city = None
    for country in countries:
        if not isinstance(country, dict):
            continue
        entries = country.get("cities")
        if isinstance(entries, list) and entries:
            city = entries[0]
            break
    if not isinstance(city, dict):
        raise CliError(
            "KEINE_DATEN",
            "Die Quelle liefert für diese Stadt keine Daten.",
            "Prüfe die Stadt mit nextbike staedte.",
            1,
        )
    try:
        uid = int(city["uid"])
        name = str(city["name"])
    except (KeyError, TypeError, ValueError):
        raise source_error("Die Stadtantwort enthält keine gültige Stadt.") from None
    places = city.get("places")
    if places is None:
        places = []
    if not isinstance(places, list):
        raise source_error("Die Stadtantwort enthält keine gültige Stationsliste.")
    clean_places = [place for place in places if isinstance(place, dict)]
    return (
        {"uid": uid, "name": name, "lat": city.get("lat"), "lng": city.get("lng")},
        clean_places,
    )


def _optional_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    import math

    radius = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return int(round(2 * radius * math.asin(math.sqrt(a))))


def _key_hash(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


class Api:
    def __init__(self, base: str | None = None) -> None:
        self.base = (base or base_url()).rstrip("/")
        self.cache_dir = cache_dir()
        self.key = _key_hash(self.base)

    def _cache_path(self, name: str, ttl: int) -> Path:
        return self.cache_dir / f"{name}-{self.key}.json"

    def _load_cache(self, path: Path, ttl: int) -> object | None:
        data = read_json(path)
        if not isinstance(data, dict):
            return None
        fetched_at = data.get("fetched_at")
        if not isinstance(fetched_at, (int, float)):
            return None
        if time.time() - float(fetched_at) > ttl:
            return None
        return data.get("payload")

    def _save_cache(self, path: Path, payload: object) -> None:
        try:
            write_json_atomic(path, {"fetched_at": time.time(), "payload": payload})
        except OSError:
            pass

    def _request(self, params: dict[str, str]) -> object:
        url = f"{self.base}/nextbike-live.json"
        try:
            response = httpx.get(
                url,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT,
                follow_redirects=True,
                trust_env=False,
            )
        except httpx.HTTPError as exc:
            raise source_error(
                f"Die nextbike-Quelle ist nicht erreichbar ({type(exc).__name__})."
            ) from None
        if response.status_code != 200:
            raise source_error(
                f"Die nextbike-Quelle antwortet mit HTTP {response.status_code}."
            )
        try:
            return response.json()
        except ValueError:
            raise source_error("Die nextbike-Quelle liefert kein gültiges JSON.") from None

    def cities(self) -> list[dict[str, Any]]:
        path = self._cache_path("staedte", CITIES_TTL)
        payload = self._load_cache(path, CITIES_TTL)
        if payload is None:
            payload = self._request({"list_cities": "1"})
            self._save_cache(path, payload)
        return parse_cities(payload)

    def city(self, uid: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        path = self._cache_path(f"stadt-{uid}", CITY_TTL)
        payload = self._load_cache(path, CITY_TTL)
        if payload is None:
            payload = self._request({"city": str(uid)})
            self._save_cache(path, payload)
        return parse_city(payload)
