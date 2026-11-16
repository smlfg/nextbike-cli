from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

from . import __version__, store
from .client import Api, haversine_m
from .errors import CliError, usage
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
