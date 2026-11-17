from __future__ import annotations

import json
from pathlib import Path

import pytest

from nextbike import client
from nextbike.client import Api, haversine_m, parse_cities, parse_city
from nextbike.normalize import normalize
from nextbike.search import city_matches, resolve_station, station_matches

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "ux"


def load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_normalize_umlaute_und_ss() -> None:
    assert normalize("München") == normalize("Munchen")
    assert normalize("GROSSSTADT") == normalize("Großstadt")
    assert normalize("  Lindenhof   / NTR ") == "lindenhof / ntr"


def test_parse_cities_fixture() -> None:
    cities = parse_cities(load("staedte.json"))
    assert len(cities) == 6
    mannheim = next(city for city in cities if city["uid"] == 195)
    assert mannheim["name"] == "Mannheim"
    assert mannheim["num_places"] == 112


def test_parse_city_fixture() -> None:
    city, places = parse_city(load("mannheim.json"))
    assert city["uid"] == 195
    assert city["name"] == "Mannheim"
    assert len(places) == 9
    lindenhof = next(place for place in places if place["number"] == 25026)
    assert lindenhof["bikes_available_to_rent"] == 3
    assert lindenhof["bike_types"] == {"196": 3}


def test_city_matches_sortiert_exakt_vor_teilstring() -> None:
    cities = parse_cities(load("staedte.json"))
    names = [city["name"] for city in city_matches(cities, "Mannheim")]
    assert names == ["Mannheim", "Roche - Mannheim"]


def test_station_matches_ignoriert_freistehende_raeder() -> None:
    _, places = parse_city(load("mannheim.json"))
    places = places + [
        {
            "name": "BIKE 123",
            "number": 0,
            "bike": True,
            "bikes_available_to_rent": 1,
            "free_racks": 0,
        }
    ]
    matches = station_matches(places, "Lindenhof")
    assert len(matches) == 6
    assert all(not place["bike"] for place in matches)


def test_resolve_station_nummer() -> None:
    _, places = parse_city(load("mannheim.json"))

    def choose(*_args, **_kwargs):
        raise AssertionError("keine Auswahl erwartet")

    station = resolve_station(places, "25026", choose)
    assert station["name"] == "Lindenhof - Jugendherberge"


def test_station_tippfehler_ignoriert_namenspraefix() -> None:
    _, places = parse_city(load("mannheim.json"))
    matches = station_matches(places, "Jugendherbrge")
    assert [place["number"] for place in matches] == [25026]

    matches = station_matches(places, "Meerackerplaz")
    assert [place["number"] for place in matches] == [25066]


def test_station_tippfehler_kurzer_praefix_ist_mehrdeutig() -> None:
    _, places = parse_city(load("mannheim.json"))
    matches = station_matches(places, "Lindenhopf")
    assert len(matches) >= 2
    assert all("Lindenhof" in place["name"] for place in matches)


def test_station_tippfehler_ohne_treffer() -> None:
    _, places = parse_city(load("mannheim.json"))
    assert station_matches(places, "Gibt Es Nicht") == []


def test_haversine_fixture() -> None:
    assert haversine_m(49.4771, 8.4637, 49.477082, 8.463662) == 3


def test_api_cache_verhindert_zweiten_request(monkeypatch, tmp_path) -> None:
    calls: list[dict[str, str]] = []

    class Response:
        status_code = 200

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    def fake_get(url, params, **kwargs):
        calls.append(params)
        return Response(load("staedte.json"))

    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("NEXTBIKE_BASE_URL", "http://example.invalid")
    monkeypatch.setattr(client.httpx, "get", fake_get)

    api = Api()
    first = api.cities()
    second = api.cities()
    assert len(first) == len(second) == 6
    assert calls == [{"list_cities": "1"}]


def test_parse_cities_fehlerhaftes_schema() -> None:
    with pytest.raises(Exception) as info:
        parse_cities({"countries": []})
    assert getattr(info.value, "exit_code", None) == 3


def test_ungueltige_basis_url_ist_quellenfehler(monkeypatch) -> None:
    monkeypatch.setenv("NEXTBIKE_BASE_URL", "keine-url")
    with pytest.raises(Exception) as info:
        Api()
    assert getattr(info.value, "exit_code", None) == 3


def test_main_faengt_strg_c_ohne_traceback(monkeypatch, capsys) -> None:
    from nextbike import cli

    def interrupt(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_run", interrupt)
    assert cli.main([]) == 130
    assert "Traceback" not in capsys.readouterr().err


def test_main_faengt_eof_ohne_traceback(monkeypatch, capsys) -> None:
    from nextbike import cli

    def eof(*_args, **_kwargs):
        raise EOFError

    monkeypatch.setattr(cli, "_run", eof)
    assert cli.main([]) == 2
    assert "Traceback" not in capsys.readouterr().err
