# Anforderungen: nextbike-cli

## Zweck

`nextbike` beantwortet im Terminal die Frage „Gibt es gerade ein Leihrad an meiner
Station?“ für die öffentliche nextbike-Karte. Das Werkzeug findet Städte per Name,
sucht Stationen per Stichwort, zeigt freie Räder und freie Stellplätze, findet
Stationen in der Nähe von Koordinaten, schlägt ein Rad per Nummer nach und
beobachtet eine Station zwischen zwei Aufrufen. Es ist rein lesend, braucht
keinen Login und keine App.

Zielgruppe: Pendler, Studierende, Agenten und Menschen, die schnell eine
verlässliche Antwort ohne Browser brauchen.

## Nutzer-Aufgaben

| Aufgabe | Eingabe | Ergebnis |
|---|---|---|
| Stadt finden | Stadtname, auch teilweise oder mit Tippfehler | UID, Name und Stationszahl der Treffer |
| Station suchen | Stadtname + Stichwort | Stationsnummer, Name, ausleihbare Räder, freie Stellplätze |
| Station verstehen | Stationsname oder -nummer + Stadt | Koordinaten, Rad-/Stellplatzzahlen, Radtypen, konkrete Radnummern, Akkustände |
| Rad wiederfinden | Radnummer + Stadt | Station, Stadt, Typ, Zustand, bei Pedelecs der Akkustand |
| Nähe erkunden | `LAT,LNG`, optional Stadt und Radius | nach Entfernung sortierte Stationen mit Verfügbarkeit |
| Station beobachten | Stationsname + Stadt, optional Schwelle | Zustand beim ersten Aufruf, Veränderung oder Warnung beim nächsten Aufruf |
| Standardstadt setzen | Stadtname | gespeicherte Standardstadt für spätere Aufrufe ohne `--stadt` |

## Nachfrage

Belegt am 16.11.2026:

- GitHub-Suche „nextbike mcp“: 0 Treffer; kein eigenständiges nextbike-CLI
  gefunden.
- Interesse an der Schnittstelle: `cybre-finn/nextbike-api-reverse-engineering`
  (★37), `syssi/nextbike` (★26, aktiv 2026-08), `nextbike/api-doc` (★20),
  `kiliankoe/Nextbike` (★9), `MMM-nextbike` (★8).
- Laufende Analytics-Projekte, u. a. `janicksturm/bike-sharing-analytics-mannheim`
  mit Issues 11/2026.
- Lücke: Es gibt keinen Terminal- oder Agenten-Zugriff auf die Live-Verfügbarkeit,
  obwohl die Daten öffentlich und ohne Schlüssel erreichbar sind.

## Datenquelle

- Basis-URL: `https://maps2.nextbike.net/maps` (Standard). `api.nextbike.net`
  leitet per HTTP 301 dorthin um; Redirects werden verfolgt.
- `GET /nextbike-live.json?list_cities=1` liefert `countries[].cities[]` mit
  `uid`, `name`, `num_places`, `lat`, `lng`. Es gibt keine serverseitige Suche;
  gefiltert wird clientseitig.
- `GET /nextbike-live.json?city=<uid>` liefert
  `countries[0].cities[0].places[]` mit `uid`, `lat`, `lng`, `name`, `number`,
  `bikes`, `bikes_available_to_rent`, `bike_racks`, `free_racks`,
  `maintenance`, `active_place`, `bike`, `bike_numbers[]`, `bike_types{}`,
  `bike_list[]` (inkl. `bike_type`, `state`, `pedelec_battery`,
  `battery_pack{percentage, estimated_range_km}`).
- Ein unbekannter `city`-Wert liefert HTTP 200 mit `{"countries":[]}`; ein
  Stadtname statt UID liefert HTTP 400. Ohne `city` werden ca. 28 MB geliefert,
  deshalb wird immer eine UID gesendet.
- Höflichkeit: eigener User-Agent mit Repo-URL, Timeouts, keine parallelen
  Massenabfragen. Städteliste 24 h gecacht, Live-Daten einer Stadt 60 s.
- `NEXTBIKE_BASE_URL` überschreibt die Basis-URL (Fake-Server, Tests).

## Funktionsumfang (v1)

- `staedte [SUCHE]`: Städte suchen oder auflisten.
- `stationen STADT [SUCHBEGRIFF] [--min-raeder N] [--nur-frei]`: Stationen einer
  Stadt filtern.
- `station NAME|NUMMER [--stadt STADT]`: Detailansicht einer Station.
- `nah LAT,LNG [--stadt STADT] [--radius M]`: Stationen im Umkreis, nach
  Entfernung sortiert.
- `rad NUMMER [--stadt STADT]`: Rad per Nummer finden.
- `watch NAME [--stadt STADT] [--unter N]`: letzte Verfügbarkeit speichern und
  beim nächsten Aufruf vergleichen.
- `config stadt [STADT]`: Standardstadt anzeigen oder setzen.

Alle Befehle geben im Terminal lesbaren Text aus. Mit `--json` oder wenn stdout
kein TTY ist, steht genau ein JSON-Objekt auf stdout. Fehler nennen den nächsten
Schritt und erzeugen keinen Traceback.

## Grenzen und Nicht-Ziele

- Inoffiziell: Das Werkzeug nutzt eine öffentlich erreichbare JSON-Schnittstelle
  der nextbike-Karte, keine dokumentierte oder zugesicherte API. Änderungen der
  Quelle können das Werkzeug brechen.
- Nur lesend: Live getestet wurden ausschließlich GET-Anfragen an öffentliche
  Seiten am 16.11.2026. Es gibt keine Ausleihe, keine Reservierung, keine
  Stornierung und keinen Login.
- Keine Garantie auf Vollständigkeit oder Aktualität der nextbike-Daten. Das
  Tool zeigt an, was die Quelle liefert, und erfindet keine Werte.
- Keine personenbezogenen Daten, keine Konten, keine Secrets. Betreiberkontakte
  aus der Quelle werden nicht ausgegeben.
- Nicht Teil von v1: Push-Benachrichtigungen, dauerhaft laufender Watch-Daemon,
  Kartenrendering, Routing, MCP-Server.

## Abnahmekriterien

- `python3 tests/harness/ux_check.py . --spec-only` endet mit Exit 0.
- Jede der sechs UX-Sitzungen aus `docs/UX.md` hat mindestens einen
  Akzeptanztest unter `tests/acceptance/`.
- Die Akzeptanztests starten das Tool als Subprozess gegen
  `tests/harness/fake_server.py` mit den `ux-routes`. Sie dürfen bis zum Bau rot
  sein.
- `README.md` beginnt mit einem Schnellstart, dessen Befehle wörtlich aus den
  UX-Sitzungen stammen.
- `--help` und `--version` enden mit Exit 0; Usage-Fehler mit Exit 2; Netz- und
  Quellenfehler mit Exit 3; fachliche „nicht gefunden“-Fälle mit Exit 1.
- Keine Tracebacks bei Fehlern, Strg+C oder EOF.
