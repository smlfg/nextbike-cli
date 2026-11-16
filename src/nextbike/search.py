from __future__ import annotations

import difflib
from typing import Any, Callable, TypeVar

from .errors import CliError
from .normalize import normalize

T = TypeVar("T")


def city_matches(cities: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """Alle Städte mit exaktem Namen, Präfix oder Teilstring, bestpassend zuerst."""
    needle = normalize(query)
    if not needle:
        return sorted(cities, key=lambda city: normalize(city["name"]))
    ranked: list[tuple[int, str, dict[str, Any]]] = []
    for city in cities:
        name = normalize(city["name"])
        if name == needle:
            rank = 0
        elif name.startswith(needle):
            rank = 1
        elif needle in name:
            rank = 2
        else:
            continue
        ranked.append((rank, name, city))
    if not ranked:
        lookup = {normalize(city["name"]): city for city in cities}
        for suggestion in difflib.get_close_matches(
            needle, list(lookup), n=10, cutoff=0.75
        ):
            ranked.append((3, suggestion, lookup[suggestion]))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in ranked]


def resolve_city(
    cities: list[dict[str, Any]],
    query: str,
    choose: Callable[[str, list[dict[str, Any]], Callable[[dict[str, Any]], str]], T],
) -> dict[str, Any]:
    """Löst einen Stadtnamen auf; Mehrdeutigkeit geht an ``choose``."""
    matches = city_matches(cities, query)
    if not matches:
        raise CliError(
            "STADT_NICHT_GEFUNDEN",
            f"Stadt „{query}“ nicht gefunden.",
            f"Nutze nextbike staedte {query}.",
            1,
        )
    exact = [city for city in matches if normalize(city["name"]) == normalize(query)]
    if len(exact) == 1:
        return exact[0]
    if exact:
        return choose("Stadt", exact, city_summary)
    unique_partial = [
        city for city in matches if normalize(query) in normalize(city["name"])
    ]
    if len(unique_partial) == 1:
        return unique_partial[0]
    if len(matches) == 1:
        return matches[0]
    return choose("Stadt", matches, city_summary)


def city_summary(city: dict[str, Any]) -> str:
    return f"{city['name']} (UID {city['uid']})"


def station_matches(
    places: list[dict[str, Any]], query: str
) -> list[dict[str, Any]]:
    """Stationen nach Name; freistehende Räder sind keine Stationen."""
    needle = normalize(query)
    stations = [place for place in places if not place.get("bike")]
    exact = [place for place in stations if normalize(place.get("name")) == needle]
    if exact:
        return exact
    partial = [
        place for place in stations if needle and needle in normalize(place.get("name"))
    ]
    if partial:
        return partial
    lookup = {normalize(place.get("name")): place for place in stations}
    result = []
    for suggestion in difflib.get_close_matches(
        needle, list(lookup), n=10, cutoff=0.75
    ):
        result.append(lookup[suggestion])
    return result


def resolve_station(
    places: list[dict[str, Any]],
    query: str,
    choose: Callable[[str, list[dict[str, Any]], Callable[[dict[str, Any]], str]], T],
) -> dict[str, Any]:
    text = str(query).strip()
    if text.isdigit():
        number = int(text)
        matches = [
            place for place in places if _as_int(place.get("number")) == number
        ]
        if not matches:
            raise CliError(
                "STATION_NICHT_GEFUNDEN",
                f"Station {number} nicht gefunden.",
                "Nutze nextbike stationen STADT.",
                1,
            )
        matches.sort(key=lambda place: bool(place.get("bike")))
        return matches[0]
    matches = station_matches(places, text)
    if not matches:
        raise CliError(
            "STATION_NICHT_GEFUNDEN",
            f"Station „{text}“ nicht gefunden.",
            "Nutze nextbike stationen STADT SUCHBEGRIFF.",
            1,
        )
    exact = [
        place for place in matches if normalize(place.get("name")) == normalize(text)
    ]
    if len(exact) == 1:
        return exact[0]
    if exact:
        return choose("Station", exact, station_summary)
    if len(matches) == 1:
        return matches[0]
    return choose("Station", matches, station_summary)


def station_summary(place: dict[str, Any]) -> str:
    return f"{place.get('name')} ({place.get('number')})"


def _as_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
