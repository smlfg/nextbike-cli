# UX-Spec: nextbike

nextbike zeigt die Live-Verfügbarkeit von Leihrädern im Terminal: Stadt per Name finden, Stationen per Stichwort suchen, freie Räder und Stellplätze sehen, Stationen in der Nähe von Koordinaten finden, ein Rad per Nummer nachschlagen und eine Station beobachten. Das Tool ist in v1 rein lesend; Ausleihe und Login sind nicht Teil der UX. Deshalb gibt es keine schreibende Aktion, keine `ux-formsteps` und keinen Login. UX09 entfällt.

## Meta

```ux-meta
{"tool": "nextbike",
 "install": "pipx install git+https://github.com/smlfg/nextbike-cli",
 "base_url_env": "NEXTBIKE_BASE_URL",
 "env": {},
 "credential_env": []}
```

`NEXTBIKE_BASE_URL` überschreibt die Basis-URL `https://maps2.nextbike.net/maps` und wird im UX-Gate auf den Fake-Server gesetzt. Es gibt keine Zugangsdaten: die nextbike-Karte ist öffentlich, Ausleihe läuft ausschließlich über die App.

## Sitzungen

Jede Sitzung ist eine Nutzer-Aufgabe und so abtippbar, wie ein Mensch sie im Terminal eingibt. `$` ist ein Befehl, `>` eine Eingabe, `<` eine erwartete Ausgabe und `!` der erwartete Exit-Code. Die Installation wird von der Harness durch eine lokale Installation in ein frisches venv ersetzt.

### Installation und Städte finden

Nach der Installation findet ein Mensch die Stadt per Namen. Die Ausgabe nennt UID und Stationszahl, damit die nächsten Befehle ohne Nachschlagen funktionieren.

```ux-session
$ pipx install git+https://github.com/smlfg/nextbike-cli
$ nextbike staedte Mannheim
< Städte zu „Mannheim“ (2 Treffer):
< Mannheim (UID 195, 112 Stationen)
< Roche - Mannheim (UID 860, 41 Stationen)
! exit 0
```

### Stationen per Stichwort suchen

Der Suchbegriff ist positional, die Stadt steht als Name davor. Treffer zeigen Stationsnummer, Namen, ausleihbare Räder und freie Stellplätze.

```ux-session
$ nextbike stationen Mannheim Lindenhof
< Stationen in Mannheim zu „Lindenhof“ (6 Treffer):
< 25026 · Lindenhof - Jugendherberge · 3 ausleihbar, 3 Stellplätze frei
< 25028 · Lindenhof - Johanniskirche · 1 ausleihbar, 2 Stellplätze frei
< 25066 · Lindenhof - Meeräckerplatz · 15 ausleihbar, 0 Stellplätze frei
< 25067 · Lindenhof - Hanns-Glückstein-Park · 14 ausleihbar, 0 Stellplätze frei
< 25089 · Lindenhof / NTR · 0 ausleihbar, 0 Stellplätze frei
< 25096 · Lindenhofplatz / HBF Süd · 0 ausleihbar, 0 Stellplätze frei
! exit 0
```

### Station im Detail anzeigen

Der Stationsname ist positional. Die Stadt lässt sich mit `--stadt` setzen; ohne Angabe gilt die Standardstadt aus der Config. Die Detailansicht zeigt Koordinaten, Rad- und Stellplatz-Zahlen, Radtypen und die konkreten Radnummern.

```ux-session
$ nextbike station "Lindenhof - Jugendherberge" --stadt Mannheim
< Lindenhof - Jugendherberge (Station 25026)
< Mannheim · 49.477082, 8.463662
< Räder: 3 (3 ausleihbar) · Stellplätze frei: 3 von 6
< Radtypen: 196 (3)
< Radnummern: 430037, 430852, 430059
! exit 0
```

### Rad per Nummer finden

Ein Mensch kennt die Radnummer aus der App oder vom Rahmen und will wissen, wo das Rad steht. Die Ausgabe nennt Station, Stadt, Typ, Zustand und bei Pedelecs den Akkustand.

```ux-session
$ nextbike rad 431211 --stadt Mannheim
< Rad 431211 · Lindenhof - Meeräckerplatz (25066)
< Mannheim · Typ 179 · Zustand ok
< Akku: 100 % (ca. 60 km)
! exit 0
```

### Stationen in der Nähe

Koordinaten werden als `LAT,LNG` übergeben, der Radius in Metern ist optional. Die Ausgabe ist nach Entfernung sortiert und zeigt pro Station die ausleihbaren Räder und freien Stellplätze.

```ux-session
$ nextbike nah 49.4771,8.4637 --stadt Mannheim --radius 1200
< Stationen im Umkreis von 1200 m um 49.4771, 8.4637 (Mannheim):
< 3 m · Lindenhof - Jugendherberge (25026) · 3 ausleihbar, 3 Stellplätze frei
< 308 m · Lindenhofplatz / HBF Süd (25096) · 0 ausleihbar, 0 Stellplätze frei
< 431 m · Lindenhof - Johanniskirche (25028) · 1 ausleihbar, 2 Stellplätze frei
< 529 m · Lindenhof / NTR (25089) · 0 ausleihbar, 0 Stellplätze frei
< 694 m · Lindenhof - Hanns-Glückstein-Park (25067) · 14 ausleihbar, 0 Stellplätze frei
< 1021 m · Lindenhof - Meeräckerplatz (25066) · 15 ausleihbar, 0 Stellplätze frei
! exit 0
```

### Station beobachten

`watch` merkt sich den letzten Stand unter `~/.local/state/nextbike-cli` (Datei mit Rechten 0600) und vergleicht beim nächsten Aufruf. Der erste Aufruf speichert nur, der zweite meldet die Veränderung. Mit `--unter N` warnt der Befehl, wenn die Zahl der ausleihbaren Räder unter die Schwelle fällt.

```ux-session
$ nextbike watch "Lindenhof - Jugendherberge" --stadt Mannheim
< Lindenhof - Jugendherberge (25026): 3 Räder verfügbar
< Erster Aufruf – Stand gespeichert.
$ nextbike watch "Lindenhof - Jugendherberge" --stadt Mannheim
< Lindenhof - Jugendherberge (25026): 3 Räder verfügbar
< Unverändert seit letztem Aufruf.
! exit 0
```

## Lesende Routen

Alle Sitzungen brauchen nur zwei GET-Routen. `list_cities=1` liefert die Städteliste (24 h gecacht), `city=195` liefert die Stationen und Räder einer Stadt (60 s gecacht). Die Antworten sind echte, gekürzte Live-Antworten vom 16.11.2026; Kontaktdaten der Betreiber wurden weggelassen.

```ux-routes
[{"method":"GET","path":"/nextbike-live.json","query_contains":"list_cities=1","response":"tests/fixtures/ux/staedte.json","status":200,"content_type":"application/json; charset=utf-8"},
 {"method":"GET","path":"/nextbike-live.json","query_contains":"city=195","response":"tests/fixtures/ux/mannheim.json","status":200,"content_type":"application/json; charset=utf-8"}]
```

## Live-Erkundung

- Basis: `https://maps2.nextbike.net/maps`, `api.nextbike.net` leitet per 301 dorthin um.
- `GET /nextbike-live.json?list_cities=1` liefert `countries[].cities[]` mit `uid`, `name`, `num_places` (591 Städte, ca. 570 KB). Es gibt keine serverseitige Suche; der Suchbegriff wird clientseitig gefiltert.
- `GET /nextbike-live.json?city=195` liefert `countries[0].cities[0].places[]` mit `uid`, `lat`, `lng`, `name`, `number`, `bikes`, `bikes_available_to_rent`, `bike_racks`, `free_racks`, `maintenance`, `active_place`, `bike` (true = freistehendes Rad), `bike_numbers[]`, `bike_types{typ: anzahl}`, `bike_list[]`.
- Unbekannte `city`-UID liefert HTTP 200 mit `{"countries":[]}`. `city=mannheim` (Name statt UID) liefert HTTP 400. Ohne `city` werden alle Städte inklusive Stationen geliefert (ca. 28 MB), deshalb immer eine UID senden.
- Sonderfälle in den Daten: Stationen ohne Räder (`bikes: 0`), Stationen mit Rädern, aber ohne ausleihbare Räder (`bikes_available_to_rent: 0`), Stationen mit `maintenance: true`, freistehende Räder (`bike: true`, `number: 0`, Name `BIKE …`) und Pedelecs mit `pedelec_battery`/`battery_pack`.
- Mehrere Treffer entstehen bei Stadtnamen (z. B. „Mannheim“ und „Roche - Mannheim“) und bei Stichworten. Im TTY nummerierte Auswahl, ohne TTY Liste plus Exit 2.
