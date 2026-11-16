from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

from . import __version__, store
from .client import Api, haversine_m
from .errors import CliError, usage
from .normalize import normalize
from .search import city_matches, resolve_city, resolve_station

DEFAULT_CITY_HINT = (
    "Nutze nextbike config stadt STADT oder --stadt STADT."
)


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise usage(message)


def _non_negative_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("muss eine ganze Zahl sein") from None
    if number < 0:
        raise argparse.ArgumentTypeError("muss >= 0 sein")
    return number


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("muss eine ganze Zahl sein") from None
    if number < 1:
        raise argparse.ArgumentTypeError("muss >= 1 sein")
    return number


def _add_json_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="genau ein JSON-Objekt ausgeben",
    )


def _build_parser() -> Parser:
    parser = Parser(
        prog="nextbike",
        description=(
            "Live-Verfügbarkeit von nextbike-Leihrädern: Städte, Stationen, "
            "Räder und Nähe. Rein lesend, ohne Login."
        ),
    )
    parser.add_argument(
        "--json", action="store_true", help="genau ein JSON-Objekt ausgeben"
    )
    parser.add_argument(
        "--version", action="version", version=f"nextbike {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command", metavar="BEFEHL")

    staedte = subparsers.add_parser(
        "staedte", help="Städte suchen oder auflisten"
    )
    staedte.add_argument("suche", nargs="?", help="Teil des Stadtnamens")
    _add_json_option(staedte)
    staedte.set_defaults(func=cmd_staedte)

    stationen = subparsers.add_parser(
        "stationen", help="Stationen einer Stadt suchen"
    )
    stationen.add_argument("stadt", help="Stadtname")
    stationen.add_argument("suchbegriff", nargs="?", help="Teil des Stationsnamens")
    stationen.add_argument(
        "--min-raeder",
        type=_non_negative_int,
        default=None,
        metavar="N",
        help="nur Stationen mit mindestens N ausleihbaren Rädern",
    )
    stationen.add_argument(
        "--nur-frei",
        action="store_true",
        help="nur Stationen mit mindestens einem ausleihbaren Rad",
    )
    _add_json_option(stationen)
    stationen.set_defaults(func=cmd_stationen)

    station = subparsers.add_parser(
        "station", help="Details einer Station anzeigen"
    )
    station.add_argument("name", help="Stationsname oder Stationsnummer")
    station.add_argument("--stadt", help="Stadtname")
    _add_json_option(station)
    station.set_defaults(func=cmd_station)

    nah = subparsers.add_parser(
        "nah", help="Stationen im Umkreis von Koordinaten finden"
    )
    nah.add_argument("koordinaten", help="LAT,LNG")
    nah.add_argument("--stadt", help="Stadtname")
    nah.add_argument(
        "--radius",
        type=_positive_int,
        default=1000,
        metavar="M",
        help="Radius in Metern (Standard 1000)",
    )
    _add_json_option(nah)
    nah.set_defaults(func=cmd_nah)

    rad = subparsers.add_parser("rad", help="Rad per Nummer finden")
    rad.add_argument("nummer", help="Radnummer")
    rad.add_argument("--stadt", help="Stadtname")
    _add_json_option(rad)
    rad.set_defaults(func=cmd_rad)

    watch = subparsers.add_parser(
        "watch", help="Verfügbarkeit einer Station beobachten"
    )
    watch.add_argument("name", help="Stationsname oder Stationsnummer")
    watch.add_argument("--stadt", help="Stadtname")
    watch.add_argument(
        "--unter",
        type=_non_negative_int,
        default=None,
        metavar="N",
        help="warnen, wenn weniger als N Räder ausleihbar sind",
    )
    _add_json_option(watch)
    watch.set_defaults(func=cmd_watch)

    return parser


def _json_mode(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "json", False)) or not sys.stdout.isatty()


def _emit(
    json_mode: bool, text_lines: list[str], payload: dict[str, Any]
) -> None:
    if json_mode:
        json.dump(payload, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        for line in text_lines:
            print(line)


def _choose(
    label: str,
    items: list[dict[str, Any]],
    render: Callable[[dict[str, Any]], str],
) -> Any:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise CliError(
            "MEHRDEUTIG",
            f"{label} ist mehrdeutig.",
            "Präzisiere den Namen oder nutze --json für die Kandidatenliste.",
            2,
            [render(item) for item in items],
        )
    for index, item in enumerate(items, start=1):
        print(f"{index}. {render(item)}", file=sys.stderr)
    while True:
        print(f"Auswahl [1-{len(items)}]: ", end="", file=sys.stderr, flush=True)
        line = sys.stdin.readline()
        if not line:
            raise usage(
                "Keine Auswahl getroffen.",
                "Wähle eine Nummer oder präzisiere den Namen.",
            )
        choice = line.strip()
        if choice.isdigit() and 1 <= int(choice) <= len(items):
            return items[int(choice) - 1]
        print("Bitte eine gültige Nummer eingeben.", file=sys.stderr)


def _load_config() -> dict[str, Any]:
    data = store.read_json(store.config_path())
    return data if isinstance(data, dict) else {}


def _save_config(data: dict[str, Any]) -> None:
    store.write_json_atomic(store.config_path(), data)


def _resolve_city(api: Api, query: str) -> dict[str, Any]:
    return resolve_city(api.cities(), query, _choose)


def _city_for_args(api: Api, args: argparse.Namespace) -> dict[str, Any]:
    explicit = getattr(args, "stadt", None)
    if explicit:
        return _resolve_city(api, explicit)
    config = _load_config()
    saved = config.get("stadt")
    if isinstance(saved, dict) and "uid" in saved and "name" in saved:
        try:
            return {
                "uid": int(saved["uid"]),
                "name": str(saved["name"]),
                "num_places": int(saved.get("num_places") or 0),
            }
        except (TypeError, ValueError):
            pass
    raise usage(
        "Keine Standardstadt gesetzt.",
        DEFAULT_CITY_HINT,
    )


def _station_payload(place: dict[str, Any]) -> dict[str, Any]:
    return {
        "nummer": _as_int(place.get("number")),
        "name": place.get("name"),
        "ausleihbar": _as_int(place.get("bikes_available_to_rent")) or 0,
        "freie_stellplaetze": _as_int(place.get("free_racks")) or 0,
    }


def _as_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _format_coord(value: object) -> str:
    try:
        text = f"{float(value):.6f}"
    except (TypeError, ValueError):
        return str(value)
    return text.rstrip("0").rstrip(".")


def cmd_staedte(args: argparse.Namespace, api: Api, json_mode: bool) -> int:
    cities = api.cities()
    query = args.suche
    if query:
        matches = city_matches(cities, query)
    else:
        matches = sorted(cities, key=lambda city: city["name"].casefold())
    if query and not matches:
        _emit(
            json_mode,
            [
                f"Keine Stadt zu „{query}“ gefunden.",
                "Nutze nextbike staedte ohne Suchbegriff für alle Städte.",
            ],
            {"staedte": [], "suche": query},
        )
        return 0
    payload = {
        "staedte": [
            {
                "uid": city["uid"],
                "name": city["name"],
                "num_places": city["num_places"],
            }
            for city in matches
        ],
        "suche": query,
    }
    title = (
        f"Städte zu „{query}“ ({len(matches)} Treffer):"
        if query
        else f"Städte ({len(matches)} Treffer):"
    )
    lines = [title]
    for city in matches:
        lines.append(
            f"{city['name']} (UID {city['uid']}, {city['num_places']} Stationen)"
        )
    _emit(json_mode, lines, payload)
    return 0


def cmd_stationen(args: argparse.Namespace, api: Api, json_mode: bool) -> int:
    city = _resolve_city(api, args.stadt)
    data_city, places = api.city(city["uid"])
    city = {**city, "name": data_city.get("name", city["name"])}
    need = normalize(args.suchbegriff) if args.suchbegriff else ""
    matches: list[dict[str, Any]] = []
    for place in places:
        if place.get("bike"):
            continue
        available = _as_int(place.get("bikes_available_to_rent")) or 0
        if need and need not in normalize(place.get("name")):
            continue
        if args.min_raeder is not None and available < args.min_raeder:
            continue
        if args.nur_frei and available <= 0:
            continue
        matches.append(place)
    payload = {
        "stadt": {"uid": city["uid"], "name": city["name"]},
        "suche": args.suchbegriff,
        "stationen": [_station_payload(place) for place in matches],
    }
    if not matches:
        query = args.suchbegriff
        lines = [
            (
                f"Keine Stationen in {city['name']} zu „{query}“ gefunden."
                if query
                else f"Keine Stationen in {city['name']} gefunden."
            ),
            "Lockere die Filter oder nutze nextbike stationen STADT ohne Suchbegriff.",
        ]
        _emit(json_mode, lines, payload)
        return 0
    title = (
        f"Stationen in {city['name']} zu „{args.suchbegriff}“ "
        f"({len(matches)} Treffer):"
        if args.suchbegriff
        else f"Stationen in {city['name']} ({len(matches)} Treffer):"
    )
    lines = [title]
    for place in matches:
        lines.append(
            f"{place.get('number')} · {place.get('name')} · "
            f"{_as_int(place.get('bikes_available_to_rent')) or 0} ausleihbar, "
            f"{_as_int(place.get('free_racks')) or 0} Stellplätze frei"
        )
    _emit(json_mode, lines, payload)
    return 0


def _radtypen(place: dict[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    raw = place.get("bike_types")
    if isinstance(raw, dict):
        for typ, count in raw.items():
            try:
                result[str(typ)] = int(count)
            except (TypeError, ValueError):
                continue
    return dict(sorted(result.items(), key=lambda item: int(item[0])))


def _radnummern(place: dict[str, Any]) -> list[int]:
    numbers: list[int] = []
    raw = place.get("bike_numbers")
    if not isinstance(raw, list):
        raw = []
        for bike in place.get("bike_list") or []:
            if isinstance(bike, dict):
                raw.append(bike.get("number"))
    for number in raw:
        try:
            numbers.append(int(number))
        except (TypeError, ValueError):
            continue
    return numbers


def _city_ref(city: dict[str, Any]) -> dict[str, Any]:
    return {"uid": city["uid"], "name": city["name"]}


def cmd_station(args: argparse.Namespace, api: Api, json_mode: bool) -> int:
    city = _city_for_args(api, args)
    data_city, places = api.city(city["uid"])
    city = {**city, "name": data_city.get("name", city["name"])}
    place = resolve_station(places, args.name, _choose)
    number = _as_int(place.get("number"))
    available = _as_int(place.get("bikes_available_to_rent")) or 0
    bikes = _as_int(place.get("bikes")) or 0
    free_racks = _as_int(place.get("free_racks")) or 0
    racks = _as_int(place.get("bike_racks")) or 0
    radtypen = _radtypen(place)
    radnummern = _radnummern(place)
    maintenance = bool(place.get("maintenance"))
    active = _as_int(place.get("active_place"))
    payload = {
        "station": {
            "nummer": number,
            "name": place.get("name"),
            "stadt": _city_ref(city),
            "lat": _as_float(place.get("lat")),
            "lng": _as_float(place.get("lng")),
            "raeder": bikes,
            "ausleihbar": available,
            "stellplaetze": racks,
            "freie_stellplaetze": free_racks,
            "wartung": maintenance,
            "radtypen": radtypen,
            "radnummern": radnummern,
        }
    }
    types_text = ", ".join(
        f"{typ} ({count})" for typ, count in radtypen.items()
    ) or "–"
    numbers_text = ", ".join(str(number) for number in radnummern) or "–"
    lines = [
        f"{place.get('name')} (Station {number})",
        f"{city['name']} · {_format_coord(place.get('lat'))}, "
        f"{_format_coord(place.get('lng'))}",
        f"Räder: {bikes} ({available} ausleihbar) · "
        f"Stellplätze frei: {free_racks} von {racks}",
        f"Radtypen: {types_text}",
        f"Radnummern: {numbers_text}",
    ]
    if maintenance:
        lines.append("Wartung: ja")
    if active == 0:
        lines.append("Hinweis: Station ist deaktiviert")
    _emit(json_mode, lines, payload)
    return 0


def _as_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _parse_coordinates(text: str) -> tuple[float, float]:
    import math

    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 2 or not all(parts):
        raise usage(
            f"Koordinaten „{text}“ sind ungültig.",
            "Nutze LAT,LNG, zum Beispiel 49.4771,8.4637.",
        )
    try:
        lat, lng = float(parts[0]), float(parts[1])
    except ValueError:
        raise usage(
            f"Koordinaten „{text}“ sind ungültig.",
            "Nutze LAT,LNG, zum Beispiel 49.4771,8.4637.",
        ) from None
    if not (math.isfinite(lat) and math.isfinite(lng)) or not (
        -90 <= lat <= 90 and -180 <= lng <= 180
    ):
        raise usage(
            f"Koordinaten „{text}“ liegen außerhalb des gültigen Bereichs.",
            "Breite -90..90 und Länge -180..180 angeben.",
        )
    return lat, lng


def _city_for_near(
    api: Api, args: argparse.Namespace, lat: float, lng: float
) -> dict[str, Any]:
    if getattr(args, "stadt", None):
        return _resolve_city(api, args.stadt)
    config = _load_config()
    saved = config.get("stadt")
    if isinstance(saved, dict) and "uid" in saved and "name" in saved:
        try:
            return {
                "uid": int(saved["uid"]),
                "name": str(saved["name"]),
                "num_places": int(saved.get("num_places") or 0),
            }
        except (TypeError, ValueError):
            pass
    cities = [
        city
        for city in api.cities()
        if _as_float(city.get("lat")) is not None
        and _as_float(city.get("lng")) is not None
    ]
    if not cities:
        raise CliError(
            "KEINE_DATEN",
            "Keine Stadt mit Mittelpunkt gefunden.",
            "Nutze --stadt STADT.",
            1,
        )
    return min(
        cities,
        key=lambda city: haversine_m(
            lat,
            lng,
            _as_float(city.get("lat")) or 0.0,
            _as_float(city.get("lng")) or 0.0,
        ),
    )


def cmd_nah(args: argparse.Namespace, api: Api, json_mode: bool) -> int:
    lat, lng = _parse_coordinates(args.koordinaten)
    city = _city_for_near(api, args, lat, lng)
    data_city, places = api.city(city["uid"])
    city = {**city, "name": data_city.get("name", city["name"])}
    found: list[tuple[int, dict[str, Any]]] = []
    for place in places:
        if place.get("bike"):
            continue
        place_lat = _as_float(place.get("lat"))
        place_lng = _as_float(place.get("lng"))
        if place_lat is None or place_lng is None:
            continue
        distance = haversine_m(lat, lng, place_lat, place_lng)
        if distance <= args.radius:
            found.append((distance, place))
    found.sort(key=lambda item: (item[0], normalize(item[1].get("name"))))
    payload = {
        "mittelpunkt": {"lat": lat, "lng": lng},
        "radius_m": args.radius,
        "stadt": _city_ref(city),
        "stationen": [
            {
                "entfernung_m": distance,
                **_station_payload(place),
            }
            for distance, place in found
        ],
    }
    if not found:
        _emit(
            json_mode,
            [
                f"Keine Station im Umkreis von {args.radius} m um "
                f"{_format_coord(lat)}, {_format_coord(lng)} gefunden.",
                "Erhöhe den Radius mit --radius.",
            ],
            payload,
        )
        return 0
    lines = [
        f"Stationen im Umkreis von {args.radius} m um "
        f"{_format_coord(lat)}, {_format_coord(lng)} ({city['name']}):"
    ]
    for distance, place in found:
        lines.append(
            f"{distance} m · {place.get('name')} ({place.get('number')}) · "
            f"{_as_int(place.get('bikes_available_to_rent')) or 0} ausleihbar, "
            f"{_as_int(place.get('free_racks')) or 0} Stellplätze frei"
        )
    _emit(json_mode, lines, payload)
    return 0


def _battery(place: dict[str, Any], number: int) -> dict[str, Any] | None:
    info = next(
        (
            bike
            for bike in place.get("bike_list") or []
            if isinstance(bike, dict) and _as_int(bike.get("number")) == number
        ),
        {},
    )
    pack = info.get("battery_pack")
    percentage = None
    range_km = None
    if isinstance(pack, dict):
        percentage = _as_int(pack.get("percentage"))
        range_km = _as_int(pack.get("estimated_range_km"))
    if percentage is None:
        percentage = _as_int(info.get("pedelec_battery"))
    if percentage is None and range_km is None:
        return None
    return {"prozent": percentage, "reichweite_km": range_km}


def cmd_rad(args: argparse.Namespace, api: Api, json_mode: bool) -> int:
    try:
        target = int(str(args.nummer).strip())
    except ValueError:
        raise usage(
            f"Radnummer „{args.nummer}“ ist keine Zahl.",
            "Nutze nextbike rad 431211 --stadt Mannheim.",
        ) from None
    city = _city_for_args(api, args)
    data_city, places = api.city(city["uid"])
    city = {**city, "name": data_city.get("name", city["name"])}
    place = None
    bike_info: dict[str, Any] = {}
    for candidate in places:
        if target in _radnummern(candidate):
            place = candidate
            bike_info = next(
                (
                    bike
                    for bike in candidate.get("bike_list") or []
                    if isinstance(bike, dict)
                    and _as_int(bike.get("number")) == target
                ),
                {},
            )
            break
    if place is None:
        raise CliError(
            "RAD_NICHT_GEFUNDEN",
            f"Rad {target} nicht in {city['name']} gefunden.",
            "Prüfe --stadt oder nutze nextbike stationen STADT.",
            1,
        )
    number = _as_int(place.get("number"))
    freestanding = bool(place.get("bike"))
    typ = bike_info.get("bike_type")
    zustand = bike_info.get("state") or "unbekannt"
    akku = _battery(place, target)
    station_ref: dict[str, Any] = {"name": place.get("name")}
    if not freestanding:
        station_ref["nummer"] = number
    payload: dict[str, Any] = {
        "radnummer": target,
        "stadt": _city_ref(city),
        "station": station_ref,
        "typ": str(typ) if typ is not None else "unbekannt",
        "zustand": zustand,
    }
    if akku is not None:
        payload["akku"] = akku
    if freestanding:
        lines = [f"Rad {target} · {place.get('name')}"]
    else:
        lines = [f"Rad {target} · {place.get('name')} ({number})"]
    lines.append(
        f"{city['name']} · Typ {payload['typ']} · Zustand {zustand}"
    )
    if akku is not None:
        percentage = akku.get("prozent")
        range_km = akku.get("reichweite_km")
        if percentage is not None and range_km is not None:
            lines.append(f"Akku: {percentage} % (ca. {range_km} km)")
        elif percentage is not None:
            lines.append(f"Akku: {percentage} %")
        elif range_km is not None:
            lines.append(f"Akku: ca. {range_km} km")
    _emit(json_mode, lines, payload)
    return 0


def _watch_key(city: dict[str, Any], number: int | None) -> str:
    return f"{city['uid']}:{number}"


def cmd_watch(args: argparse.Namespace, api: Api, json_mode: bool) -> int:
    city = _city_for_args(api, args)
    data_city, places = api.city(city["uid"])
    city = {**city, "name": data_city.get("name", city["name"])}
    place = resolve_station(places, args.name, _choose)
    number = _as_int(place.get("number"))
    available = _as_int(place.get("bikes_available_to_rent")) or 0
    key = _watch_key(city, number)
    path = store.state_path()
    raw = store.read_json(path)
    if path.exists() and not isinstance(raw, dict):
        print(
            "Hinweis: Watch-Stand ist unlesbar und wird neu angelegt.",
            file=sys.stderr,
        )
        raw = {}
    state = raw if isinstance(raw, dict) else {}
    previous_entry = state.get(key)
    previous = None
    if isinstance(previous_entry, dict):
        previous = _as_int(previous_entry.get("verfuegbar"))
    first_call = previous is None
    changed = previous is not None and previous != available
    warning = args.unter is not None and available < args.unter
    state[key] = {
        "verfuegbar": available,
        "name": place.get("name"),
        "stadt": _city_ref(city),
        "nummer": number,
    }
    try:
        store.write_json_atomic(path, state)
    except OSError:
        print(
            "Hinweis: Watch-Stand konnte nicht gespeichert werden.",
            file=sys.stderr,
        )
    payload = {
        "station": {
            "nummer": number,
            "name": place.get("name"),
            "stadt": _city_ref(city),
        },
        "verfuegbar": available,
        "vorher": previous,
        "veraendert": changed,
        "erster_aufruf": first_call,
        "schwelle": args.unter,
        "warnung": warning,
    }
    lines = [f"{place.get('name')} ({number}): {available} Räder verfügbar"]
    if first_call:
        lines.append("Erster Aufruf – Stand gespeichert.")
    elif changed:
        lines.append(
            f"Verändert seit letztem Aufruf: {previous} → {available} ausleihbar."
        )
    else:
        lines.append("Unverändert seit letztem Aufruf.")
    if warning:
        lines.append(
            f"Warnung: {available} ausleihbar, unter Schwelle {args.unter}."
        )
    _emit(json_mode, lines, payload)
    return 0


def _report_error(error: CliError, json_mode: bool) -> int:
    if json_mode:
        payload: dict[str, Any] = {
            "fehler": {
                "code": error.slug,
                "nachricht": error.message,
                "naechster_schritt": error.next_step or "",
            }
        }
        if error.kandidaten:
            payload["fehler"]["kandidaten"] = error.kandidaten
        json.dump(payload, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        print(str(error), file=sys.stderr)
        for candidate in error.kandidaten:
            print(f"- {candidate}", file=sys.stderr)
    return error.exit_code


def _run(argv: list[str], json_requested: bool) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    json_mode = bool(json_requested) or bool(getattr(args, "json", False))
    json_mode = json_mode or not sys.stdout.isatty()
    if not getattr(args, "command", None):
        raise usage(
            "Kein Befehl angegeben.",
            "Nutze nextbike --help für die verfügbaren Befehle.",
        )
    api = Api()
    return int(args.func(args, api, json_mode))


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    json_requested = "--json" in arguments
    try:
        return _run(arguments, json_requested)
    except CliError as error:
        return _report_error(error, json_requested or not sys.stdout.isatty())
    except KeyboardInterrupt:
        print("Abgebrochen.", file=sys.stderr)
        return 130
    except BrokenPipeError:
        return 0
    except EOFError:
        print("Abgebrochen: keine Eingabe.", file=sys.stderr)
        return 2
    except SystemExit as exit_request:
        code = exit_request.code
        return int(code) if isinstance(code, int) else 1
    except Exception as error:  # noqa: BLE001 - bewusst ohne Traceback
        if json_requested or not sys.stdout.isatty():
            json.dump(
                {
                    "fehler": {
                        "code": "UNERWARTET",
                        "nachricht": f"Unerwarteter Fehler ({type(error).__name__}).",
                        "naechster_schritt": "Nutze nextbike --help.",
                    }
                },
                sys.stdout,
                ensure_ascii=False,
            )
            sys.stdout.write("\n")
        else:
            print(
                f"Unerwarteter Fehler ({type(error).__name__}). "
                "Nutze nextbike --help.",
                file=sys.stderr,
            )
        return 1
