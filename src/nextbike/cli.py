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
